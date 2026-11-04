"""Reads and writes the journal's records, in terms of models rather than rows.

Nothing above this module writes SQL, and nothing in it knows about the store,
the network, or the screen, so it can be tested with nothing but a temporary file.
Every public method is a coroutine that runs on the database thread.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, fields, replace
from typing import Any, Iterable, Mapping, Optional, Sequence

from .database import Database
from .models import Attachment, Entry, EntryDraft, Place, Settings, parse_tags
from .protocol import WireAttachment, WireEntry, remote_wins

_ENTRY_COLUMNS = (
    "id, title, body, conditions, latitude, longitude, accuracy, place_name, created_at, updated_at, device, "
    "deleted_at, dirty"
)
_ATTACHMENT_COLUMNS = "id, entry_id, kind, path, mime_type, name, size, duration, created_at, remote_path, deleted_at"
_LIKE_SPECIALS = re.compile(r"([\\%_])")


@dataclass(frozen=True)
class Merge:
    """What merging a server version did: whether the screen changes, and the files of attachments it removed."""

    changed: bool = False
    orphaned: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchQuery:
    """What someone typed into the search field: words that must all appear, and ``#tags`` the entry must have."""

    terms: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether this matches everything."""
        return not (self.terms or self.tags)


def parse_search(text: str) -> SearchQuery:
    """Split a search into words and ``#tags``.

    Args:
        text: What someone typed, such as ``heron #birds``.

    Returns:
        The parsed query.
    """
    words = text.split()
    tags = parse_tags(" ".join(word for word in words if word.startswith("#")))
    terms = tuple(word.casefold() for word in words if not word.startswith("#"))
    return SearchQuery(terms=terms, tags=tags)


def _like(term: str) -> str:
    return f"%{_LIKE_SPECIALS.sub(r'\\\1', term)}%"


def _attachment(row: sqlite3.Row) -> Attachment:
    return Attachment(**dict(row))


def _place(row: sqlite3.Row) -> Optional[Place]:
    if row["latitude"] is None or row["longitude"] is None:
        return None
    return Place(row["latitude"], row["longitude"], row["accuracy"], row["place_name"])


def _hydrate(connection: sqlite3.Connection, rows: Sequence[sqlite3.Row]) -> tuple[Entry, ...]:
    """Build entries from their rows, fetching tags, attachments, and reminders in one query each."""
    if not rows:
        return ()
    ids = [row["id"] for row in rows]
    slots = ",".join("?" * len(ids))
    tags: dict[str, list[str]] = {}
    for row in connection.execute(
        f"SELECT entry_id, tag FROM entry_tags WHERE entry_id IN ({slots}) ORDER BY position", ids
    ):
        tags.setdefault(row["entry_id"], []).append(row["tag"])
    attachments: dict[str, list[Attachment]] = {}
    for row in connection.execute(
        f"SELECT {_ATTACHMENT_COLUMNS} FROM attachments "
        f"WHERE entry_id IN ({slots}) AND deleted_at IS NULL ORDER BY created_at, id",
        ids,
    ):
        attachments.setdefault(row["entry_id"], []).append(_attachment(row))
    reminders = {
        row["entry_id"]: row["fire_at"]
        for row in connection.execute(f"SELECT entry_id, fire_at FROM reminders WHERE entry_id IN ({slots})", ids)
    }
    return tuple(
        Entry(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            tags=tuple(tags.get(row["id"], ())),
            conditions=row["conditions"],
            place=_place(row),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            device=row["device"],
            deleted_at=row["deleted_at"],
            dirty=bool(row["dirty"]),
            attachments=tuple(attachments.get(row["id"], ())),
            remind_at=reminders.get(row["id"]),
        )
        for row in rows
    )


def _write_tags(connection: sqlite3.Connection, entry_id: str, tags: Iterable[str]) -> None:
    connection.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
    connection.executemany(
        "INSERT INTO entry_tags (entry_id, tag, position) VALUES (?, ?, ?)",
        [(entry_id, tag, position) for position, tag in enumerate(tags)],
    )


def _place_columns(place: Optional[Place]) -> tuple[Optional[float], Optional[float], Optional[float], str]:
    if place is None:
        return None, None, None, ""
    return place.latitude, place.longitude, place.accuracy, place.name


class Repository:
    """The journal's persistence.

    Args:
        database: The open file.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    # -- reading -------------------------------------------------------

    async def list_entries(self) -> tuple[Entry, ...]:
        """Return every live entry, newest first."""

        def read(connection: sqlite3.Connection) -> tuple[Entry, ...]:
            rows = connection.execute(
                f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE deleted_at IS NULL ORDER BY created_at DESC, id"
            ).fetchall()
            return _hydrate(connection, rows)

        return await self.database.run(read)

    async def get(self, entry_id: str) -> Optional[Entry]:
        """Return one entry, deleted or not, or ``None`` if it was never here."""

        def read(connection: sqlite3.Connection) -> Optional[Entry]:
            rows = connection.execute(f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE id = ?", (entry_id,)).fetchall()
            found = _hydrate(connection, rows)
            return found[0] if found else None

        return await self.database.run(read)

    async def search(self, query: SearchQuery) -> tuple[Entry, ...]:
        """Return the live entries matching ``query``, newest first.

        A word matches anywhere in the title, notes, place name, or tags, ignoring
        case. The journal fits in memory but its search belongs in the database,
        where it can't fall behind the rows it's searching.

        Args:
            query: From [`parse_search`][app.repository.parse_search].

        Returns:
            The matches.
        """

        def read(connection: sqlite3.Connection) -> tuple[Entry, ...]:
            clauses = ["deleted_at IS NULL"]
            parameters: list[str] = []
            for term in query.terms:
                clauses.append(
                    "(folded(title) LIKE ? ESCAPE '\\' OR folded(body) LIKE ? ESCAPE '\\' "
                    "OR folded(place_name) LIKE ? ESCAPE '\\' OR id IN "
                    "(SELECT entry_id FROM entry_tags WHERE tag LIKE ? ESCAPE '\\'))"
                )
                parameters.extend([_like(term)] * 4)
            for tag in query.tags:
                clauses.append("id IN (SELECT entry_id FROM entry_tags WHERE tag = ?)")
                parameters.append(tag)
            rows = connection.execute(
                f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE {' AND '.join(clauses)} ORDER BY created_at DESC, id",
                parameters,
            ).fetchall()
            return _hydrate(connection, rows)

        return await self.database.run(read)

    # -- editing -------------------------------------------------------

    async def create(self, entry_id: str, draft: EntryDraft, *, now: float, device: str) -> Entry:
        """Insert a new entry.

        Args:
            entry_id: Its ID.
            draft: The fields.
            now: When it was written.
            device: This device's ID.

        Returns:
            The saved entry.
        """

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute(
                    "INSERT INTO entries (id, title, body, conditions, latitude, longitude, accuracy, place_name, "
                    "created_at, updated_at, device, dirty) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (
                        entry_id,
                        draft.title,
                        draft.body,
                        draft.conditions,
                        *_place_columns(draft.place),
                        now,
                        now,
                        device,
                    ),
                )
                _write_tags(connection, entry_id, draft.tags)

        await self.database.run(write)
        return await self._require(entry_id)

    async def update(self, entry_id: str, draft: EntryDraft, *, now: float, device: str) -> Entry:
        """Replace an entry's fields and mark it for the next sync.

        Args:
            entry_id: The entry.
            draft: Its new fields.
            now: When the edit happened.
            device: This device's ID.

        Returns:
            The saved entry.

        Raises:
            LookupError: If there's no such entry.
        """

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute(
                    "UPDATE entries SET title = ?, body = ?, conditions = ?, latitude = ?, longitude = ?, "
                    "accuracy = ?, place_name = ?, updated_at = ?, device = ?, dirty = dirty + 1 WHERE id = ?",
                    (draft.title, draft.body, draft.conditions, *_place_columns(draft.place), now, device, entry_id),
                )
                _write_tags(connection, entry_id, draft.tags)

        await self.database.run(write)
        return await self._require(entry_id)

    async def delete(self, entry_id: str, *, now: float, device: str) -> None:
        """Delete an entry, leaving a tombstone so the deletion reaches other devices."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute(
                    "UPDATE entries SET deleted_at = ?, updated_at = ?, device = ?, dirty = dirty + 1 WHERE id = ?",
                    (now, now, device, entry_id),
                )
                connection.execute("DELETE FROM reminders WHERE entry_id = ?", (entry_id,))

        await self.database.run(write)

    async def _require(self, entry_id: str) -> Entry:
        entry = await self.get(entry_id)
        if entry is None:
            raise LookupError(f"No entry {entry_id!r}")
        return entry

    # -- attachments ---------------------------------------------------

    async def add_attachment(self, attachment: Attachment) -> None:
        """Record an attachment and mark its entry for the next sync."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute(
                    f"INSERT INTO attachments ({_ATTACHMENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        attachment.id,
                        attachment.entry_id,
                        attachment.kind,
                        attachment.path,
                        attachment.mime_type,
                        attachment.name,
                        attachment.size,
                        attachment.duration,
                        attachment.created_at,
                        attachment.remote_path,
                        attachment.deleted_at,
                    ),
                )
                connection.execute("UPDATE entries SET dirty = dirty + 1 WHERE id = ?", (attachment.entry_id,))

        await self.database.run(write)

    async def remove_attachment(self, attachment_id: str, *, now: float) -> Optional[str]:
        """Tombstone an attachment.

        Returns:
            Its file's relative path, for the caller to delete, or ``None`` if it
            has no file.
        """

        def write(connection: sqlite3.Connection) -> Optional[str]:
            row = connection.execute("SELECT entry_id, path FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
            if row is None:
                return None
            with connection:
                connection.execute(
                    "UPDATE attachments SET deleted_at = ?, path = '' WHERE id = ?", (now, attachment_id)
                )
                connection.execute("UPDATE entries SET dirty = dirty + 1 WHERE id = ?", (row["entry_id"],))
            return row["path"] or None

        return await self.database.run(write)

    async def mark_uploaded(self, attachment_id: str, remote_path: str) -> None:
        """Record where the server keeps an attachment, and tell other devices on the next sync."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute("UPDATE attachments SET remote_path = ? WHERE id = ?", (remote_path, attachment_id))
                connection.execute(
                    "UPDATE entries SET dirty = dirty + 1 WHERE id = (SELECT entry_id FROM attachments WHERE id = ?)",
                    (attachment_id,),
                )

        await self.database.run(write)

    async def mark_downloaded(self, attachment_id: str, path: str, size: int) -> None:
        """Record the local copy of another device's attachment."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute(
                    "UPDATE attachments SET path = ?, size = ? WHERE id = ?", (path, size, attachment_id)
                )

        await self.database.run(write)

    async def transfers_pending(self) -> tuple[tuple[Attachment, ...], tuple[Attachment, ...]]:
        """Return what still has to reach the server, and what still has to come from it."""

        def read(connection: sqlite3.Connection) -> tuple[tuple[Attachment, ...], tuple[Attachment, ...]]:
            rows = connection.execute(
                f"SELECT {_ATTACHMENT_COLUMNS} FROM attachments WHERE deleted_at IS NULL ORDER BY created_at"
            ).fetchall()
            attachments = [_attachment(row) for row in rows]
            return (
                tuple(item for item in attachments if item.needs_upload),
                tuple(item for item in attachments if item.needs_download),
            )

        return await self.database.run(read)

    # -- reminders -----------------------------------------------------

    async def set_reminder(self, entry_id: str, fire_at: float) -> None:
        """Remember when an entry's reminder fires."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute(
                    "INSERT INTO reminders (entry_id, fire_at) VALUES (?, ?) "
                    "ON CONFLICT (entry_id) DO UPDATE SET fire_at = excluded.fire_at",
                    (entry_id, fire_at),
                )

        await self.database.run(write)

    async def clear_reminder(self, entry_id: str) -> None:
        """Forget an entry's reminder."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute("DELETE FROM reminders WHERE entry_id = ?", (entry_id,))

        await self.database.run(write)

    async def clear_past_reminders(self, *, now: float) -> None:
        """Forget reminders that have fired. The system doesn't tell a closed app when they do."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute("DELETE FROM reminders WHERE fire_at <= ?", (now,))

        await self.database.run(write)

    # -- sync ----------------------------------------------------------

    async def dirty_wire_entries(self) -> tuple[WireEntry, ...]:
        """Return every version the server hasn't seen, tombstones included."""

        def read(connection: sqlite3.Connection) -> tuple[WireEntry, ...]:
            rows = connection.execute(f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE dirty > 0").fetchall()
            return tuple(_wire(connection, row) for row in rows)

        return await self.database.run(read)

    async def mark_synced(self, entry_id: str, change: int) -> None:
        """Clear an entry's dirty count, unless it changed again since the push being acknowledged.

        Args:
            entry_id: The entry.
            change: The dirty count the acknowledged push carried.
        """

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.execute("UPDATE entries SET dirty = 0 WHERE id = ? AND dirty = ?", (entry_id, change))

        await self.database.run(write)

    async def apply_remote(self, remote: WireEntry) -> Merge:
        """Merge a version from the server.

        The text fields are a last-writer-wins register: the newer ``updated_at``
        wins, with the device ID breaking a tie. Attachments merge by ID, so two
        people adding photos at once both keep them, and a removal is final.

        Args:
            remote: The server's version.

        Returns:
            What the merge changed.
        """

        def write(connection: sqlite3.Connection) -> Merge:
            with connection:
                local = connection.execute(
                    f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE id = ?", (remote.id,)
                ).fetchone()
                changed = _merge_fields(connection, local, remote)
                attachments_changed, orphaned = _merge_attachments(connection, remote)
                return Merge(changed or attachments_changed, orphaned)

        return await self.database.run(write)

    # -- settings ------------------------------------------------------

    async def load_settings(self) -> Settings:
        """Read the persisted options, with defaults for anything never set."""

        def read(connection: sqlite3.Connection) -> Settings:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()
            known = {item.name for item in fields(Settings)}
            stored = {row["key"]: json.loads(row["value"]) for row in rows if row["key"] in known}
            return replace(Settings(), **stored)

        return await self.database.run(read)

    async def save_settings(self, changes: Mapping[str, Any]) -> None:
        """Persist some options, leaving the others as they are."""

        def write(connection: sqlite3.Connection) -> None:
            with connection:
                connection.executemany(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    [(key, json.dumps(value)) for key, value in changes.items()],
                )

        await self.database.run(write)


def _wire(connection: sqlite3.Connection, row: sqlite3.Row) -> WireEntry:
    tags = connection.execute(
        "SELECT tag FROM entry_tags WHERE entry_id = ? ORDER BY position", (row["id"],)
    ).fetchall()
    attachments = connection.execute(
        f"SELECT {_ATTACHMENT_COLUMNS} FROM attachments WHERE entry_id = ? ORDER BY created_at, id", (row["id"],)
    ).fetchall()
    return WireEntry(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        tags=tuple(tag["tag"] for tag in tags),
        conditions=row["conditions"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        accuracy=row["accuracy"],
        place_name=row["place_name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        device=row["device"],
        deleted_at=row["deleted_at"],
        attachments=tuple(_wire_attachment(_attachment(item)) for item in attachments),
        change=row["dirty"],
    )


def _wire_attachment(attachment: Attachment) -> WireAttachment:
    return WireAttachment(
        id=attachment.id,
        kind=attachment.kind,
        mime_type=attachment.mime_type,
        name=attachment.name,
        size=attachment.size,
        duration=attachment.duration,
        created_at=attachment.created_at,
        remote_path=attachment.remote_path,
        deleted_at=attachment.deleted_at,
    )


def _merge_fields(connection: sqlite3.Connection, local: Optional[sqlite3.Row], remote: WireEntry) -> bool:
    if local is not None and not remote_wins(
        local_updated=local["updated_at"],
        local_device=local["device"],
        remote_updated=remote.updated_at,
        remote_device=remote.device,
    ):
        return False  # The local version stands, and it clears on the push that carries it.
    connection.execute(
        "INSERT INTO entries (id, title, body, conditions, latitude, longitude, accuracy, place_name, created_at, "
        "updated_at, device, deleted_at, dirty) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0) "
        "ON CONFLICT (id) DO UPDATE SET title = excluded.title, body = excluded.body, "
        "conditions = excluded.conditions, latitude = excluded.latitude, longitude = excluded.longitude, "
        "accuracy = excluded.accuracy, place_name = excluded.place_name, updated_at = excluded.updated_at, "
        "device = excluded.device, deleted_at = excluded.deleted_at, dirty = 0",
        (
            remote.id,
            remote.title,
            remote.body,
            remote.conditions,
            remote.latitude,
            remote.longitude,
            remote.accuracy,
            remote.place_name,
            remote.created_at,
            remote.updated_at,
            remote.device,
            remote.deleted_at,
        ),
    )
    _write_tags(connection, remote.id, remote.tags)
    return True


def _merge_attachments(connection: sqlite3.Connection, remote: WireEntry) -> tuple[bool, tuple[str, ...]]:
    changed = False
    orphaned: list[str] = []
    rows = connection.execute(
        "SELECT id, path, remote_path, deleted_at FROM attachments WHERE entry_id = ?", (remote.id,)
    ).fetchall()
    local = {row["id"]: row for row in rows}
    theirs = {item.id: item for item in remote.attachments}
    for item in remote.attachments:
        row = local.get(item.id)
        if row is None:
            connection.execute(
                f"INSERT INTO attachments ({_ATTACHMENT_COLUMNS}) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    remote.id,
                    item.kind,
                    item.mime_type,
                    item.name,
                    item.size,
                    item.duration,
                    item.created_at,
                    item.remote_path,
                    item.deleted_at,
                ),
            )
            changed = True
            continue
        if item.deleted_at is not None and row["deleted_at"] is None:
            connection.execute(
                "UPDATE attachments SET deleted_at = ?, path = '' WHERE id = ?", (item.deleted_at, item.id)
            )
            if row["path"]:
                orphaned.append(row["path"])
            changed = True
        if item.remote_path and not row["remote_path"]:
            connection.execute("UPDATE attachments SET remote_path = ? WHERE id = ?", (item.remote_path, item.id))
            changed = True
    # Something the server hasn't heard about keeps the entry queued, even when its text lost.
    if any(_ahead_of(row, theirs.get(row["id"])) for row in rows):
        connection.execute("UPDATE entries SET dirty = dirty + 1 WHERE id = ?", (remote.id,))
    return changed, tuple(orphaned)


def _ahead_of(local: sqlite3.Row, remote: Optional[WireAttachment]) -> bool:
    if remote is None:
        return True
    return bool(
        (local["remote_path"] and not remote.remote_path)
        or (local["deleted_at"] is not None and remote.deleted_at is None)
    )
