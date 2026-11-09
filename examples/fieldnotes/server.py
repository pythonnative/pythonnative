#!/usr/bin/env python3
"""Field Notes' development sync server, in one standard-library file.

    python server.py                       # for simulators on this machine
    python server.py --host 0.0.0.0        # for phones on your network

It speaks the protocol described in ``app/protocol.py``: a WebSocket at ``/sync``
for entries, and HTTP at ``/attachments`` for their files. Everything lives in one
JSON file and one directory of attachments. It has no authentication and no TLS,
which is what makes it a development server. Don't put it on the internet.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import email.parser
import email.policy
import hashlib
import json
import logging
import os
import re
import struct
from pathlib import Path
from typing import Any, Mapping, Optional

DEFAULT_PORT = 8770
"""Not 8765, which ``pn start`` uses."""

MAX_BODY = 256 * 1024 * 1024
_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_SAFE_ID = re.compile(r"^[0-9A-Za-z_-]{1,64}$")
_TEXT, _BINARY, _CLOSE, _PING, _PONG = 0x1, 0x2, 0x8, 0x9, 0xA

logger = logging.getLogger("fieldnotes.server")


class JournalStore:
    """Every entry the server knows, each stamped with the change number that last touched it.

    Args:
        directory: Where to keep ``journal.json`` and ``attachments/``.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.attachments = directory / "attachments"
        self.attachments.mkdir(parents=True, exist_ok=True)
        self._path = directory / "journal.json"
        self.entries: dict[str, dict[str, Any]] = {}
        self.cursor = 0
        if self._path.exists():
            saved = json.loads(self._path.read_text(encoding="utf-8"))
            self.entries, self.cursor = saved["entries"], saved["cursor"]

    def _save(self) -> None:
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"entries": self.entries, "cursor": self.cursor}), encoding="utf-8")
        temporary.replace(self._path)

    def changes_since(self, cursor: int) -> list[dict[str, Any]]:
        """Return the entries changed after ``cursor``, oldest change first."""
        changed = [entry for entry in self.entries.values() if entry["seq"] > cursor]
        return sorted(changed, key=lambda entry: entry["seq"])

    def merge(self, incoming: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        """Merge a client's version.

        Args:
            incoming: The entry as a client sent it.

        Returns:
            The stored entry if this changed it, or ``None`` if the server already
            had this or something newer.
        """
        current = self.entries.get(incoming["id"])
        merged = _merge(current, incoming)
        if current is not None and _same(current, merged):
            return None
        self.cursor += 1
        merged["seq"] = self.cursor
        merged.pop("change", None)
        self.entries[merged["id"]] = merged
        self._save()
        return merged

    def attachment_path(self, attachment_id: str) -> Path:
        """Return where an attachment's file lives."""
        return self.attachments / attachment_id


def _merge(current: Optional[Mapping[str, Any]], incoming: Mapping[str, Any]) -> dict[str, Any]:
    """The same rule as ``repository.apply_remote``: newest fields win, attachments union by ID."""
    if current is None:
        return dict(incoming)
    newer = (incoming["updated_at"], incoming.get("device", "")) > (current["updated_at"], current.get("device", ""))
    merged = dict(incoming if newer else current)
    by_id = {item["id"]: dict(item) for item in current.get("attachments", ())}
    for item in incoming.get("attachments", ()):
        known = by_id.get(item["id"])
        if known is None:
            by_id[item["id"]] = dict(item)
        else:
            known["deleted_at"] = known.get("deleted_at") or item.get("deleted_at")
            known["remote_path"] = known.get("remote_path") or item.get("remote_path") or ""
    merged["attachments"] = sorted(by_id.values(), key=lambda item: (item.get("created_at", 0), item["id"]))
    return merged


def _same(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Compare two entries, ignoring what's about the server's or a client's bookkeeping."""
    bookkeeping = ("seq", "change")
    return {key: value for key, value in left.items() if key not in bookkeeping} == {
        key: value for key, value in right.items() if key not in bookkeeping
    }


class Connection:
    """One WebSocket client: the frame format, from the server's side of RFC 6455."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        self.device = ""

    async def send_json(self, value: Any) -> None:
        """Send one text message."""
        await self._send_frame(_TEXT, json.dumps(value).encode("utf-8"))

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", 0x80 | opcode, length)
        elif length < 65536:
            header = struct.pack("!BBH", 0x80 | opcode, 126, length)
        else:
            header = struct.pack("!BBQ", 0x80 | opcode, 127, length)
        self.writer.write(header + payload)
        await self.writer.drain()

    async def _read_frame(self) -> tuple[bool, int, bytes]:
        first, second = await self.reader.readexactly(2)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", await self.reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await self.reader.readexactly(8))[0]
        if length > MAX_BODY:
            raise ConnectionError("frame too large")
        mask = await self.reader.readexactly(4) if second & 0x80 else b"\0\0\0\0"
        data = await self.reader.readexactly(length)
        repeated = (mask * (length // 4 + 1))[:length]
        unmasked = (int.from_bytes(data, "little") ^ int.from_bytes(repeated, "little")).to_bytes(length, "little")
        return bool(first & 0x80), first & 0x0F, unmasked

    async def receive(self) -> Optional[str]:
        """Return the next text message, or ``None`` once the client has closed."""
        parts: list[bytes] = []
        while True:
            final, opcode, payload = await self._read_frame()
            if opcode == _PING:
                await self._send_frame(_PONG, payload)
            elif opcode == _CLOSE:
                await self._send_frame(_CLOSE, payload[:2])
                return None
            elif opcode != _PONG:
                parts.append(payload)
                if final:
                    return b"".join(parts).decode("utf-8")

    def drop(self) -> None:
        """Cut the connection with no goodbye, as a lost network would."""
        self.writer.transport.abort()


class SyncServer:
    """The server: one listening socket, the store, and the connected clients.

    Args:
        directory: Where data lives.
        host: The address to listen on.
        port: The port to listen on. ``0`` picks a free one.
    """

    def __init__(self, directory: Path, *, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
        self.store = JournalStore(directory)
        self.host = host
        self.port = port
        self.clients: set[Connection] = set()
        self._server: Optional[asyncio.Server] = None

    async def start(self) -> None:
        """Start listening, and fill in ``port`` if it was ``0``."""
        self._server = await asyncio.start_server(self._accept, self.host, self.port, limit=2**20)
        self.port = self._server.sockets[0].getsockname()[1]

    async def serve_forever(self) -> None:
        """Run until canceled."""
        await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop listening and drop every client."""
        if self._server is not None:
            self._server.close()
        self.drop_clients()
        if self._server is not None:
            await self._server.wait_closed()
            self._server = None

    def drop_clients(self) -> None:
        """Cut every client off. Handy for watching an app reconnect."""
        for client in list(self.clients):
            client.drop()

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1").split("\r\n")
            method, target, _ = head[0].split(" ", 2)
            headers = {
                name.strip().lower(): value.strip() for name, _, value in (line.partition(":") for line in head[1:])
            }
            path = target.split("?", 1)[0]
            if path == "/sync" and headers.get("upgrade", "").lower() == "websocket":
                await self._websocket(reader, writer, headers)
            elif method == "POST" and path == "/attachments":
                await self._receive_attachment(reader, writer, headers)
            elif method == "GET" and path.startswith("/attachments/"):
                await self._send_attachment(writer, path.rsplit("/", 1)[1])
            elif method == "GET" and path == "/health":
                entries = len(self.store.entries)
                await _respond(
                    writer, 200, {"entries": entries, "cursor": self.store.cursor, "clients": len(self.clients)}
                )
            else:
                await _respond(writer, 404, {"error": "not found"})
        except (asyncio.IncompleteReadError, ConnectionError, ValueError) as error:
            logger.debug("connection ended: %s", error)
        finally:
            writer.close()

    # -- entries -------------------------------------------------------

    async def _websocket(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, headers: Mapping[str, str]
    ) -> None:
        accept = base64.b64encode(hashlib.sha1(headers["sec-websocket-key"].encode() + _GUID).digest()).decode()  # noqa: S324
        writer.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("latin-1")
        )
        await writer.drain()
        client = Connection(reader, writer)
        self.clients.add(client)
        try:
            while (raw := await client.receive()) is not None:
                await self._handle(client, json.loads(raw))
        finally:
            self.clients.discard(client)
            logger.info("client %s left, %d connected", client.device[:8], len(self.clients))

    async def _handle(self, client: Connection, message: Mapping[str, Any]) -> None:
        kind = message.get("type")
        if kind == "hello":
            client.device = str(message.get("device", ""))
            logger.info("client %s joined, %d connected", client.device[:8], len(self.clients))
            changes = self.store.changes_since(int(message.get("cursor", 0)))
            await client.send_json({"type": "welcome", "cursor": self.store.cursor, "changes": changes})
        elif kind == "push":
            await self._push(client, message.get("entries", ()))

    async def _push(self, client: Connection, entries: Any) -> None:
        acknowledged = []
        for entry in entries:
            merged = self.store.merge(entry)
            acknowledged.append({"id": entry["id"], "change": entry.get("change", 0)})
            if merged is None:
                # The server has something newer, which the sender may never have seen.
                stored = self.store.entries[entry["id"]]
                if not _same(stored, entry):
                    await client.send_json({"type": "changed", "entry": stored, "cursor": self.store.cursor})
                continue
            logger.info("%s changed by %s", entry["id"][:8], client.device[:8])
            for other in list(self.clients):
                if other is not client or not _same(merged, entry):
                    await other.send_json({"type": "changed", "entry": merged, "cursor": self.store.cursor})
        await client.send_json({"type": "ack", "entries": acknowledged, "cursor": self.store.cursor})

    # -- attachments ---------------------------------------------------

    async def _receive_attachment(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, headers: Mapping[str, str]
    ) -> None:
        length = int(headers.get("content-length", "0"))
        if not 0 < length <= MAX_BODY:
            await _respond(writer, 413, {"error": "attachment too large"})
            return
        body = await reader.readexactly(length)
        document = f"Content-Type: {headers.get('content-type', '')}\r\n\r\n".encode("latin-1") + body
        parsed = email.parser.BytesParser(policy=email.policy.default).parsebytes(document)
        fields: dict[str, str] = {}
        data: Optional[bytes] = None
        for part in parsed.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if part.get_filename() is not None:
                payload = part.get_payload(decode=True)
                data = payload if isinstance(payload, bytes) else None
            elif isinstance(name, str):
                fields[name] = str(part.get_content()).strip()
        attachment_id = fields.get("id", "")
        if data is None or not _SAFE_ID.match(attachment_id):
            await _respond(writer, 400, {"error": "needs a file and a valid id"})
            return
        self.store.attachment_path(attachment_id).write_bytes(data)
        logger.info("stored attachment %s, %d bytes", attachment_id[:8], len(data))
        await _respond(writer, 201, {"path": f"/attachments/{attachment_id}", "size": len(data)})

    async def _send_attachment(self, writer: asyncio.StreamWriter, attachment_id: str) -> None:
        path = self.store.attachment_path(attachment_id)
        if not _SAFE_ID.match(attachment_id) or not path.is_file():
            await _respond(writer, 404, {"error": "no such attachment"})
            return
        data = path.read_bytes()
        writer.write(
            f"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: {len(data)}\r\n"
            "Connection: close\r\n\r\n".encode("latin-1")
        )
        writer.write(data)
        await writer.drain()


async def _respond(writer: asyncio.StreamWriter, status: int, value: Any) -> None:
    body = json.dumps(value).encode("utf-8")
    reasons = {200: "OK", 201: "Created", 400: "Bad Request", 404: "Not Found", 413: "Content Too Large"}
    writer.write(
        (
            f"HTTP/1.1 {status} {reasons[status]}\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        ).encode("latin-1")
        + body
    )
    await writer.drain()


def main() -> None:
    """Run the server until interrupted."""
    parser = argparse.ArgumentParser(description="Field Notes' development sync server.")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on; 0.0.0.0 lets phones reach it")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--data", type=Path, default=Path.home() / ".fieldnotes-server", help="where to keep the journal"
    )
    parser.add_argument("--verbose", action="store_true")
    options = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if options.verbose else logging.INFO, format="%(message)s")
    server = SyncServer(options.data, host=options.host, port=options.port)
    logger.info(
        "Field Notes sync server on ws://%s:%d/sync, keeping data in %s", options.host, options.port, options.data
    )
    logger.info("In the app: Settings > Sync server. An Android emulator reaches this machine at 10.0.2.2.")
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        pass
    os._exit(0)


if __name__ == "__main__":
    main()
