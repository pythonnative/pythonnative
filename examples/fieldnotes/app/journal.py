"""The journal: the app's state and every action that changes it.

Screens read [`Journal.store`][app.journal.Journal] with ``pn.use_store`` and call
these methods. Each action writes through the repository and then replaces the
store's snapshot, so the database stays the one source of truth and a screen can't
show something that wasn't saved.
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
import shutil
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Optional

import pythonnative as pn

from .database import Database
from .errorlog import ErrorLog
from .models import (
    Attachment,
    AttachmentKind,
    Entry,
    EntryDraft,
    Place,
    Settings,
    Snapshot,
)
from .protocol import WireEntry
from .repository import Repository, SearchQuery, parse_search

FREE_ATTACHMENTS = 3
"""How many attachments an entry can hold without Pro."""


class AttachmentLimitReached(Exception):
    """A free entry already has as many attachments as it can hold."""


def data_directory() -> Path:
    """Return the directory that holds the journal's database, files, and error log."""
    return pn.FileSystem.path("fieldnotes")


def extension_for(mime_type: str, source: str) -> str:
    """Pick a file extension for an attachment, preferring the one its type implies."""
    return mimetypes.guess_extension(mime_type.lower()) or os.path.splitext(source)[1].lower() or ".bin"


class Journal:
    """Owns the store and the database, and carries out actions on them."""

    def __init__(self) -> None:
        self.store = pn.Store(Snapshot(), name="fieldnotes")
        self.errors = ErrorLog(lambda: data_directory() / "errors.jsonl", on_change=self._errors_changed)
        self._repository: Optional[Repository] = None
        self._loaded: Optional["asyncio.Future[None]"] = None
        self._listeners: list[Callable[[], None]] = []

    @property
    def repository(self) -> Repository:
        """The repository, opening the file on first use.

        The file can't open earlier, because the data directory comes from the
        platform and the background task can start the app with no screen.
        """
        if self._repository is None:
            self._repository = Repository(Database(data_directory() / "journal.db"))
        return self._repository

    @property
    def snapshot(self) -> Snapshot:
        """The current state."""
        return self.store.get()

    def on_local_change(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Hear about each change a person made here. The sync client pushes on this.

        Args:
            listener: Called on the application thread after the write.

        Returns:
            A function that stops listening.
        """
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def announce_change(self) -> None:
        """Tell the listeners that something here changed that the server hasn't heard."""
        for listener in list(self._listeners):
            listener()

    def _errors_changed(self, count: int) -> None:
        self.publish(logged_errors=count)

    # -- loading -------------------------------------------------------

    async def load(self) -> None:
        """Read everything from disk once. Later calls wait for the first, or return at once.

        Raises:
            Exception: Whatever opening the database raised. It's also recorded in
                the store, and the next call tries again.
        """
        if self._loaded is None:
            self._loaded = asyncio.ensure_future(self._load())
        try:
            await asyncio.shield(self._loaded)
        except Exception:
            self._loaded = None
            raise

    async def _load(self) -> None:
        try:
            settings = await self.repository.load_settings()
            if not settings.device_id:
                settings = replace(settings, device_id=uuid.uuid4().hex)
                await self.repository.save_settings({"device_id": settings.device_id})
            await self.repository.clear_past_reminders(now=time.time())
            entries = await self.repository.list_entries()
        except Exception as error:
            message = f"Couldn't open the journal: {error}"
            self.store.update(lambda state: replace(state, loading=False, error=message))
            raise
        self.store.update(
            lambda state: replace(
                state,
                entries=entries,
                settings=settings,
                loading=False,
                error="",
                locked=settings.lock_enabled,
                logged_errors=self.errors.count(),
            )
        )

    async def refresh(self) -> None:
        """Replace the snapshot's entries with what the database holds now."""
        entries = await self.repository.list_entries()
        self.store.update(lambda state: replace(state, entries=entries))

    async def search(self, text: str) -> tuple[Entry, ...]:
        """Search the live entries.

        Args:
            text: What someone typed, with ``#tag`` for tags.

        Returns:
            The matches, newest first.
        """
        query: SearchQuery = parse_search(text)
        if query.is_empty:
            return self.snapshot.entries
        return await self.repository.search(query)

    # -- entries -------------------------------------------------------

    async def create_entry(self, draft: EntryDraft) -> Entry:
        """Save a new entry.

        Args:
            draft: Its fields.

        Returns:
            The saved entry.
        """
        now = time.time()
        entry = await self.repository.create(uuid.uuid4().hex, draft, now=now, device=self.snapshot.settings.device_id)
        await self.refresh()
        self.announce_change()
        return entry

    async def update_entry(self, entry_id: str, draft: EntryDraft) -> Entry:
        """Save an edit.

        Args:
            entry_id: The entry.
            draft: Its new fields.

        Returns:
            The saved entry.
        """
        entry = await self.repository.update(entry_id, draft, now=time.time(), device=self.snapshot.settings.device_id)
        await self.refresh()
        self.announce_change()
        return entry

    async def set_place(self, entry_id: str, place: Optional[Place]) -> None:
        """Set or clear where an entry was written."""
        entry = self.snapshot.find(entry_id)
        if entry is not None:
            await self.update_entry(entry_id, EntryDraft(entry.title, entry.body, entry.tags, entry.conditions, place))

    async def delete_entry(self, entry_id: str) -> None:
        """Delete an entry and its files. The sync server hears about it on the next push."""
        entry = self.snapshot.find(entry_id)
        await self.repository.delete(entry_id, now=time.time(), device=self.snapshot.settings.device_id)
        if entry is not None:
            for attachment in entry.attachments:
                await self.repository.remove_attachment(attachment.id, now=time.time())
                self._delete_file(attachment.path)
        await self.refresh()
        self.announce_change()

    async def merge_remote(self, remote: WireEntry) -> None:
        """Merge a version from the sync server, and show it if anything changed.

        Args:
            remote: The server's version.
        """
        merge = await self.repository.apply_remote(remote)
        for path in merge.orphaned:
            self._delete_file(path)
        if merge.changed:
            await self.refresh()

    # -- attachments ---------------------------------------------------

    def can_attach(self, entry: Entry) -> bool:
        """Return whether an entry has room for another attachment."""
        return self.snapshot.is_pro or len(entry.attachments) < FREE_ATTACHMENTS

    def file_path(self, attachment: Attachment) -> str:
        """Return an attachment's absolute path on this install."""
        return str(data_directory() / attachment.path)

    async def add_attachment(
        self,
        entry_id: str,
        kind: AttachmentKind,
        source: str,
        *,
        mime_type: str,
        name: str = "",
        duration: float = 0.0,
    ) -> Attachment:
        """Move a captured or picked file into the journal and attach it.

        Cameras, recorders, and pickers all hand over files in the cache directory,
        which the system can clear, so nothing stays attached to that copy.

        Args:
            entry_id: The entry.
            kind: What it is.
            source: The file's current path. It's moved, not copied.
            mime_type: The file's type.
            name: A name to show and to upload it under.
            duration: Seconds of audio or video.

        Returns:
            The new attachment.

        Raises:
            AttachmentLimitReached: If the entry is full and Pro isn't unlocked.
            LookupError: If the entry doesn't exist.
        """
        entry = self.snapshot.find(entry_id)
        if entry is None:
            raise LookupError(f"No entry {entry_id!r}")
        if not self.can_attach(entry):
            raise AttachmentLimitReached(f"This entry already has {FREE_ATTACHMENTS} attachments.")
        attachment_id = uuid.uuid4().hex
        extension = extension_for(mime_type, source)
        relative = f"attachments/{entry_id}/{attachment_id}{extension}"
        target = data_directory() / relative

        def store_file() -> int:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, target)
            return target.stat().st_size

        size = await asyncio.to_thread(store_file)
        attachment = Attachment(
            id=attachment_id,
            entry_id=entry_id,
            kind=kind,
            path=relative,
            mime_type=mime_type,
            name=name or f"{kind}-{attachment_id[:8]}{extension}",
            size=size,
            duration=duration,
            created_at=time.time(),
        )
        await self.repository.add_attachment(attachment)
        await self.refresh()
        self.announce_change()
        return attachment

    async def remove_attachment(self, attachment: Attachment) -> None:
        """Remove an attachment and delete its file."""
        path = await self.repository.remove_attachment(attachment.id, now=time.time())
        if path:
            self._delete_file(path)
        await self.refresh()
        self.announce_change()

    def _delete_file(self, relative: str) -> None:
        if relative:
            (data_directory() / relative).unlink(missing_ok=True)

    # -- reminders -----------------------------------------------------

    async def set_reminder(self, entry_id: str, fire_at: float) -> None:
        """Remember when an entry's reminder fires."""
        await self.repository.set_reminder(entry_id, fire_at)
        await self.refresh()

    async def clear_reminder(self, entry_id: str) -> None:
        """Forget an entry's reminder."""
        await self.repository.clear_reminder(entry_id)
        await self.refresh()

    # -- settings ------------------------------------------------------

    async def update_settings(self, **changes: Any) -> None:
        """Persist some options and apply them to the snapshot.

        Args:
            **changes: Fields of [`Settings`][app.models.Settings].
        """
        await self.repository.save_settings(changes)
        self.store.update(lambda state: replace(state, settings=replace(state.settings, **changes)))

    @property
    def settings(self) -> Settings:
        """The current options."""
        return self.snapshot.settings

    # -- other state ---------------------------------------------------

    def publish(self, **changes: Any) -> None:
        """Replace some fields of the snapshot.

        Args:
            **changes: Fields of [`Snapshot`][app.models.Snapshot].
        """
        self.store.update(lambda state: replace(state, **changes))

    def set_transfer(self, attachment_id: str, fraction: Optional[float]) -> None:
        """Publish an upload or download's progress, or remove it with ``None``."""

        def change(state: Snapshot) -> Snapshot:
            transfers: dict[str, float] = dict(state.transfers)
            if fraction is None:
                transfers.pop(attachment_id, None)
            else:
                transfers[attachment_id] = fraction
            return replace(state, transfers=transfers)

        self.store.update(change)


journal = Journal()
"""The one journal every screen, the sync client, and the background task share."""
