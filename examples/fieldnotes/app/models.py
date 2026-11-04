"""The journal's records. Every one is a frozen dataclass, so a change replaces it whole."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping, Optional

AttachmentKind = Literal["photo", "voice", "video"]
Appearance = Literal["system", "light", "dark"]
SyncPhase = Literal["offline", "connecting", "connected", "waiting"]
StorePhase = Literal["checking", "ready", "no_product", "unavailable", "failed"]

CONDITIONS = ("Clear", "Cloudy", "Rain", "Snow", "Wind")
"""The weather a field entry can record. Its first item is what a new entry starts with."""

_TAG_SPLIT = re.compile(r"[,\s]+")


def parse_tags(text: str) -> tuple[str, ...]:
    """Turn what someone typed into normalized tags: lowercase, no ``#``, no repeats, in order."""
    seen: dict[str, None] = {}
    for raw in _TAG_SPLIT.split(text):
        tag = raw.strip().lstrip("#").casefold()
        if tag:
            seen.setdefault(tag)
    return tuple(seen)


def format_day(timestamp: float) -> str:
    """Format a time the way the journal's rows show it, like ``Tue, Nov 3, 2026``."""
    moment = datetime.fromtimestamp(timestamp)
    return f"{moment:%a, %b} {moment.day}, {moment.year}"


def format_time(timestamp: float) -> str:
    """Format a time of day, like ``14:05``."""
    return f"{datetime.fromtimestamp(timestamp):%H:%M}"


def format_moment(timestamp: float) -> str:
    """Format a day and a time together."""
    return f"{format_day(timestamp)} at {format_time(timestamp)}"


def format_duration(seconds: float) -> str:
    """Format a length of audio or video as minutes and seconds, like ``2:07``."""
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def format_size(size: int) -> str:
    """Format a byte count for people."""
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def format_coordinate(latitude: float, longitude: float) -> str:
    """Format a position in degrees, like ``59.9139 N, 10.7522 E``."""
    north_south = "N" if latitude >= 0 else "S"
    east_west = "E" if longitude >= 0 else "W"
    return f"{abs(latitude):.4f} {north_south}, {abs(longitude):.4f} {east_west}"


@dataclass(frozen=True)
class Place:
    """Where an entry was written.

    Attributes:
        latitude: Degrees north.
        longitude: Degrees east.
        accuracy: Radius of the fix in meters, when the platform reports one.
        name: What the author calls this place, such as ``North ridge``.
    """

    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    name: str = ""

    @property
    def label(self) -> str:
        """The name when there is one, and the coordinates when there isn't."""
        return self.name or format_coordinate(self.latitude, self.longitude)


@dataclass(frozen=True)
class Attachment:
    """A photo, voice note, or video on an entry.

    Attributes:
        id: Stable across devices.
        entry_id: The entry it belongs to.
        kind: What it is.
        path: The file, relative to the journal's data directory, because an iOS
            app's absolute container path changes with each install. Empty while
            a copy from another device hasn't been downloaded yet.
        mime_type: The file's type.
        name: A name to show and to upload it under.
        size: Bytes.
        duration: Seconds of audio or video, or 0 for a photo.
        created_at: When it was added.
        remote_path: Where the sync server keeps it, once uploaded.
        deleted_at: When someone removed it. Sync needs the tombstone.
    """

    id: str
    entry_id: str
    kind: AttachmentKind
    path: str
    mime_type: str
    name: str
    size: int = 0
    duration: float = 0.0
    created_at: float = 0.0
    remote_path: str = ""
    deleted_at: Optional[float] = None

    @property
    def is_local(self) -> bool:
        """Whether this device has the file."""
        return bool(self.path)

    @property
    def needs_upload(self) -> bool:
        """Whether this device holds the only copy."""
        return self.is_local and not self.remote_path and self.deleted_at is None

    @property
    def needs_download(self) -> bool:
        """Whether another device's copy is waiting on the server."""
        return not self.is_local and bool(self.remote_path) and self.deleted_at is None


@dataclass(frozen=True)
class Entry:
    """One journal entry.

    Attributes:
        id: Stable across devices.
        title: A short title, which may be empty.
        body: The notes.
        tags: Normalized tags, in the order written.
        conditions: One of [`CONDITIONS`][app.models.CONDITIONS].
        place: Where it was written, if known.
        created_at: When it was first saved.
        updated_at: When its text last changed anywhere. Sync compares this.
        device: The device that made that change. It breaks ties.
        deleted_at: When someone deleted it. Sync needs the tombstone.
        dirty: Whether the sync server hasn't seen this version.
        attachments: The live attachments, oldest first.
        remind_at: When a reminder fires, if one is set.
    """

    id: str
    title: str = ""
    body: str = ""
    tags: tuple[str, ...] = ()
    conditions: str = CONDITIONS[0]
    place: Optional[Place] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    device: str = ""
    deleted_at: Optional[float] = None
    dirty: bool = True
    attachments: tuple[Attachment, ...] = ()
    remind_at: Optional[float] = None

    @property
    def display_title(self) -> str:
        """The title, the first line of the notes, or a stand-in, so a row is never blank."""
        if self.title.strip():
            return self.title.strip()
        first_line = self.body.strip().splitlines()[0] if self.body.strip() else ""
        return first_line[:60] or "Untitled entry"

    @property
    def excerpt(self) -> str:
        """The notes on one line, short enough for a row."""
        flat = " ".join(self.body.split())
        return flat if len(flat) <= 140 else f"{flat[:139]}..."

    def of_kind(self, kind: AttachmentKind) -> tuple[Attachment, ...]:
        """Return this entry's attachments of one kind."""
        return tuple(attachment for attachment in self.attachments if attachment.kind == kind)

    def attachment(self, attachment_id: str) -> Optional[Attachment]:
        """Return one attachment by ID."""
        return next((item for item in self.attachments if item.id == attachment_id), None)


@dataclass(frozen=True)
class EntryDraft:
    """What the editor hands the journal: the fields a person can change."""

    title: str = ""
    body: str = ""
    tags: tuple[str, ...] = ()
    conditions: str = CONDITIONS[0]
    place: Optional[Place] = None

    @property
    def is_empty(self) -> bool:
        """Whether there's nothing worth saving."""
        return not (self.title.strip() or self.body.strip())


@dataclass(frozen=True)
class Settings:
    """The options the app persists between launches.

    Attributes:
        server_url: The sync server's WebSocket URL, or empty to stay offline.
        lock_enabled: Whether the journal asks for biometrics to open.
        appearance: Follow the system, or force light or dark.
        background_sync: Whether the periodic sync task should be scheduled.
        pro_owned: The last known state of the Pro unlock. The store can't always
            be asked, and this has to survive a flight.
        device_id: Identifies this install to the sync server.
        sync_cursor: The newest server change this device has merged.
    """

    server_url: str = ""
    lock_enabled: bool = False
    appearance: Appearance = "system"
    background_sync: bool = True
    pro_owned: bool = False
    device_id: str = ""
    sync_cursor: int = 0


@dataclass(frozen=True)
class SyncStatus:
    """What the live connection is doing, for the settings screen and the journal's banner.

    Attributes:
        phase: ``offline`` means no server is set. ``connecting`` is one attempt.
            ``connected`` means the server said hello. ``waiting`` means an
            attempt failed and another is coming.
        detail: The last failure, in words.
        attempt: How many attempts in a row have failed.
        retry_in: Seconds until the next attempt, while waiting.
        last_synced: When the server last acknowledged this device's changes.
    """

    phase: SyncPhase = "offline"
    detail: str = ""
    attempt: int = 0
    retry_in: float = 0.0
    last_synced: Optional[float] = None


@dataclass(frozen=True)
class ProState:
    """The Pro unlock, as the store and this device understand it.

    Attributes:
        phase: Whether the store can sell it right now.
        display_price: The store's formatted price, when it's on sale.
        message: Why not, or the outcome of the last attempt.
        busy: Whether a purchase or restore is running.
    """

    phase: StorePhase = "checking"
    display_price: str = ""
    message: str = ""
    busy: bool = False


@dataclass(frozen=True)
class Snapshot:
    """Everything the screens read. The store replaces it whole on every change.

    Attributes:
        entries: Live entries, newest first.
        loading: Whether the first read from disk is still running.
        error: The last failed journal operation, in words.
        settings: The persisted options.
        sync: The live connection.
        pro: The Pro unlock.
        transfers: Fraction complete of each running upload or download, by attachment ID.
        transfer_error: Why the last upload or download stopped.
        logged_errors: How many errors the on-disk log holds.
        locked: Whether the lock screen covers the app.
        background_note: Why the background task isn't scheduled, if it isn't.
    """

    entries: tuple[Entry, ...] = ()
    loading: bool = True
    error: str = ""
    settings: Settings = field(default_factory=Settings)
    sync: SyncStatus = field(default_factory=SyncStatus)
    pro: ProState = field(default_factory=ProState)
    transfers: Mapping[str, float] = field(default_factory=dict)
    transfer_error: str = ""
    logged_errors: int = 0
    locked: bool = False
    background_note: str = ""

    def find(self, entry_id: str) -> Optional[Entry]:
        """Return one live entry by ID."""
        return next((entry for entry in self.entries if entry.id == entry_id), None)

    @property
    def is_pro(self) -> bool:
        """Whether attachments are unlimited."""
        return self.settings.pro_owned

    @property
    def tags(self) -> tuple[str, ...]:
        """Every tag in use, most used first, for the journal's filter row."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return tuple(sorted(counts, key=lambda tag: (-counts[tag], tag)))
