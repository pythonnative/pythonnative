"""The sync protocol: what crosses the WebSocket, and who wins a conflict.

Each side keeps its own copy of every entry. A client says hello with the newest
server change it has merged, called its cursor, and the server answers with
everything since then. After that, either side sends entries as they change:

| Message | Direction | Fields |
| --- | --- | --- |
| ``hello`` | Client to server | ``device``, ``cursor`` |
| ``welcome`` | Server to client | ``cursor``, ``changes`` |
| ``push`` | Client to server | ``entries`` |
| ``ack`` | Server to client | ``entries`` (``id``, ``change``), ``cursor`` |
| ``changed`` | Server to client | ``entry``, ``cursor`` |

``examples/fieldnotes/server.py`` is the other end. It stays a single standard
library script, so it has its own copy of these rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, cast
from urllib.parse import urlsplit, urlunsplit

PROTOCOL_VERSION = 1


class ProtocolError(Exception):
    """The server sent something this version doesn't understand."""


@dataclass(frozen=True)
class WireAttachment:
    """An attachment's metadata. The file itself travels over HTTP."""

    id: str
    kind: Literal["photo", "voice", "video"]
    mime_type: str
    name: str
    size: int
    duration: float
    created_at: float
    remote_path: str = ""
    deleted_at: Optional[float] = None

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form."""
        return {
            "id": self.id,
            "kind": self.kind,
            "mime_type": self.mime_type,
            "name": self.name,
            "size": self.size,
            "duration": self.duration,
            "created_at": self.created_at,
            "remote_path": self.remote_path,
            "deleted_at": self.deleted_at,
        }

    @staticmethod
    def from_json(value: Mapping[str, Any]) -> "WireAttachment":
        """Read the JSON form.

        Raises:
            ProtocolError: If a required field is missing or of the wrong type.
        """
        try:
            kind = str(value["kind"])
            if kind not in ("photo", "voice", "video"):
                raise ProtocolError(f"Unknown attachment kind {kind!r}")
            return WireAttachment(
                id=str(value["id"]),
                kind=cast(Literal["photo", "voice", "video"], kind),
                mime_type=str(value.get("mime_type") or "application/octet-stream"),
                name=str(value.get("name") or ""),
                size=int(value.get("size") or 0),
                duration=float(value.get("duration") or 0),
                created_at=float(value["created_at"]),
                remote_path=str(value.get("remote_path") or ""),
                deleted_at=_optional_float(value.get("deleted_at")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProtocolError(f"Bad attachment: {error}") from error


@dataclass(frozen=True)
class WireEntry:
    """An entry as it crosses the network: all of its fields, including its tombstones."""

    id: str
    title: str
    body: str
    tags: tuple[str, ...]
    conditions: str
    latitude: Optional[float]
    longitude: Optional[float]
    accuracy: Optional[float]
    place_name: str
    created_at: float
    updated_at: float
    device: str
    deleted_at: Optional[float] = None
    attachments: tuple[WireAttachment, ...] = ()
    change: int = 0
    """The sender's count of unsynced changes, which the server echoes in its ``ack``."""

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tags": list(self.tags),
            "conditions": self.conditions,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "place_name": self.place_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "device": self.device,
            "deleted_at": self.deleted_at,
            "attachments": [attachment.to_json() for attachment in self.attachments],
            "change": self.change,
        }

    @staticmethod
    def from_json(value: Mapping[str, Any]) -> "WireEntry":
        """Read the JSON form.

        Raises:
            ProtocolError: If a required field is missing or of the wrong type.
        """
        try:
            return WireEntry(
                id=str(value["id"]),
                title=str(value.get("title") or ""),
                body=str(value.get("body") or ""),
                tags=tuple(str(tag) for tag in value.get("tags") or ()),
                conditions=str(value.get("conditions") or ""),
                latitude=_optional_float(value.get("latitude")),
                longitude=_optional_float(value.get("longitude")),
                accuracy=_optional_float(value.get("accuracy")),
                place_name=str(value.get("place_name") or ""),
                created_at=float(value["created_at"]),
                updated_at=float(value["updated_at"]),
                device=str(value.get("device") or ""),
                deleted_at=_optional_float(value.get("deleted_at")),
                attachments=tuple(WireAttachment.from_json(item) for item in value.get("attachments") or ()),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProtocolError(f"Bad entry: {error}") from error


def _optional_float(value: Any) -> Optional[float]:
    return None if value is None else float(value)


def remote_wins(*, local_updated: float, local_device: str, remote_updated: float, remote_device: str) -> bool:
    """Decide whether a remote version replaces the local one.

    Newer wins. The device ID breaks an exact tie, so that two devices that saw
    the same two versions always keep the same one.

    Args:
        local_updated: When the local version was written.
        local_device: The device that wrote it.
        remote_updated: When the remote version was written.
        remote_device: The device that wrote it.

    Returns:
        ``True`` to take the remote version.
    """
    return (remote_updated, remote_device) > (local_updated, local_device)


def normalize_server_url(text: str) -> str:
    """Turn what someone typed into the sync server's WebSocket URL.

    Accepts a bare ``host:port``, an ``http(s)`` URL, or a ``ws(s)`` URL, and
    fills in the ``/sync`` path the server listens on.

    Args:
        text: What was typed. Blank means no server.

    Returns:
        The URL, or an empty string for no server.

    Raises:
        ValueError: If it can't name a server.
    """
    text = text.strip()
    if not text:
        return ""
    parts = urlsplit(text if "://" in text else f"ws://{text}")
    schemes = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}
    scheme = schemes.get(parts.scheme)
    if scheme is None or not parts.hostname:
        raise ValueError(f"{text!r} doesn't look like a server address. Try something like 192.168.1.20:8765.")
    try:
        _ = parts.port
    except ValueError as error:
        raise ValueError(f"{text!r} has an invalid port.") from error
    return urlunsplit((scheme, parts.netloc, parts.path.rstrip("/") or "/sync", "", ""))


def http_base(socket_url: str) -> str:
    """Return the same server's HTTP origin, where attachments go.

    Args:
        socket_url: The WebSocket URL.

    Returns:
        The origin, with no trailing slash, such as ``http://localhost:8765``.
    """
    parts = urlsplit(socket_url)
    scheme = "https" if parts.scheme == "wss" else "http"
    return urlunsplit((scheme, parts.netloc, "", "", ""))
