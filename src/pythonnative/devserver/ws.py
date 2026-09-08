"""A small RFC 6455 (WebSocket) implementation on the standard library.

The dev server and the on-device dev client both need WebSockets, and
neither can assume a third-party package: the client runs inside the
embedded interpreter on iOS and Android, where every dependency has to
be bundled. This module provides just enough of the protocol for a
trusted development network:

- [`encode_frame`][pythonnative.devserver.ws.encode_frame] and
  [`FrameDecoder`][pythonnative.devserver.ws.FrameDecoder] handle the
  wire format (masking, 7/16/64-bit lengths, fragmentation, control
  frames).
- [`server_handshake`][pythonnative.devserver.ws.server_handshake] and
  [`client_handshake_request`][pythonnative.devserver.ws.client_handshake_request]
  build the HTTP upgrade.
- [`WebSocketClient`][pythonnative.devserver.ws.WebSocketClient] is a
  blocking client meant to live on a background thread (the dev client
  uses one; the main thread never waits on the network).

Extensions (compression) and subprotocols are not negotiated.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import struct
import threading
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlsplit

__all__ = [
    "CLOSE",
    "BINARY",
    "CONTINUATION",
    "PING",
    "PONG",
    "TEXT",
    "FrameDecoder",
    "HandshakeError",
    "WebSocketClient",
    "WebSocketError",
    "accept_key",
    "client_handshake_request",
    "encode_close",
    "encode_frame",
    "parse_http_headers",
    "server_handshake",
]

_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

CONTINUATION = 0x0
TEXT = 0x1
BINARY = 0x2
CLOSE = 0x8
PING = 0x9
PONG = 0xA

_CONTROL_OPCODES = {CLOSE, PING, PONG}
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
"""Upper bound on one reassembled message; anything larger is a protocol error."""


class WebSocketError(Exception):
    """A framing or protocol violation on the connection."""


class HandshakeError(WebSocketError):
    """The HTTP upgrade did not complete."""


# ======================================================================
# Handshake
# ======================================================================


def accept_key(client_key: str) -> str:
    """Return the ``Sec-WebSocket-Accept`` value for ``client_key``."""
    digest = hashlib.sha1(client_key.strip().encode("ascii") + _GUID).digest()
    return base64.b64encode(digest).decode("ascii")


def parse_http_headers(raw: bytes) -> Tuple[str, Dict[str, str]]:
    """Split an HTTP request or response head into ``(start_line, headers)``.

    Header names are lower-cased. ``raw`` should be the bytes up to
    (and optionally including) the blank line that ends the head.
    """
    text = raw.decode("iso-8859-1")
    lines = text.split("\r\n")
    start_line = lines[0].strip()
    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if not line.strip():
            break
        name, sep, value = line.partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    return start_line, headers


def server_handshake(headers: Dict[str, str]) -> bytes:
    """Build the ``101 Switching Protocols`` response for an upgrade request.

    Args:
        headers: Lower-cased request headers (see
            [`parse_http_headers`][pythonnative.devserver.ws.parse_http_headers]).

    Raises:
        HandshakeError: When the request is not a WebSocket upgrade.
    """
    if "websocket" not in headers.get("upgrade", "").lower():
        raise HandshakeError("not a WebSocket upgrade request")
    key = headers.get("sec-websocket-key")
    if not key:
        raise HandshakeError("missing Sec-WebSocket-Key")
    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key(key)}\r\n"
        "\r\n"
    ).encode("ascii")


def client_handshake_request(host: str, path: str, key: Optional[str] = None) -> Tuple[bytes, str]:
    """Build a client upgrade request; returns ``(request_bytes, key)``."""
    if key is None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path or '/'} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).encode("ascii")
    return request, key


# ======================================================================
# Framing
# ======================================================================


def encode_frame(opcode: int, payload: bytes, *, mask: bool = False, fin: bool = True) -> bytes:
    """Encode one frame.

    Clients must send masked frames and servers unmasked ones; the
    caller picks. Text payloads must already be UTF-8 encoded.
    """
    head = bytearray()
    head.append((0x80 if fin else 0x00) | (opcode & 0x0F))
    length = len(payload)
    mask_bit = 0x80 if mask else 0x00
    if length < 126:
        head.append(mask_bit | length)
    elif length < 65536:
        head.append(mask_bit | 126)
        head += struct.pack("!H", length)
    else:
        head.append(mask_bit | 127)
        head += struct.pack("!Q", length)
    if not mask:
        return bytes(head) + payload
    key = os.urandom(4)
    head += key
    return bytes(head) + _apply_mask(payload, key)


def encode_close(code: int = 1000, reason: str = "", *, mask: bool = False) -> bytes:
    """Encode a close frame carrying ``code`` and ``reason``."""
    body = struct.pack("!H", code) + reason.encode("utf-8")
    return encode_frame(CLOSE, body, mask=mask)


def _apply_mask(data: bytes, key: bytes) -> bytes:
    """XOR ``data`` with the repeating 4-byte ``key`` (masking is symmetric)."""
    if not data:
        return b""
    # Extend the key across the payload and XOR the two as big integers;
    # this is far faster than a per-byte loop in pure Python.
    repeated = (key * (len(data) // 4 + 1))[: len(data)]
    return (int.from_bytes(data, "big") ^ int.from_bytes(repeated, "big")).to_bytes(len(data), "big")


class FrameDecoder:
    """Incremental frame parser that reassembles fragmented messages.

    Feed raw bytes with [`feed`][pythonnative.devserver.ws.FrameDecoder.feed];
    it yields complete ``(opcode, payload)`` messages. Control frames
    (ping, pong, close) are yielded as they arrive, even in the middle
    of a fragmented data message, as the RFC allows.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._fragments: List[bytes] = []
        self._fragment_opcode: Optional[int] = None

    def feed(self, data: bytes) -> Iterator[Tuple[int, bytes]]:
        """Consume ``data`` and yield every message it completes."""
        self._buffer += data
        while True:
            parsed = self._parse_one()
            if parsed is None:
                return
            fin, opcode, payload = parsed
            if opcode in _CONTROL_OPCODES:
                if not fin:
                    raise WebSocketError("fragmented control frame")
                yield opcode, payload
                continue
            if opcode == CONTINUATION:
                if self._fragment_opcode is None:
                    raise WebSocketError("continuation frame without a start")
                self._fragments.append(payload)
            else:
                if self._fragment_opcode is not None:
                    raise WebSocketError("new data frame while a message is fragmented")
                self._fragment_opcode = opcode
                self._fragments = [payload]
            if sum(len(f) for f in self._fragments) > MAX_MESSAGE_BYTES:
                raise WebSocketError("message exceeds the size limit")
            if fin:
                message_opcode = self._fragment_opcode
                message = b"".join(self._fragments)
                self._fragments = []
                self._fragment_opcode = None
                yield message_opcode, message

    def _parse_one(self) -> Optional[Tuple[bool, int, bytes]]:
        buf = self._buffer
        if len(buf) < 2:
            return None
        first, second = buf[0], buf[1]
        fin = bool(first & 0x80)
        if first & 0x70:
            raise WebSocketError("reserved bits set (extensions are not negotiated)")
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        offset = 2
        if length == 126:
            if len(buf) < 4:
                return None
            length = struct.unpack("!H", bytes(buf[2:4]))[0]
            offset = 4
        elif length == 127:
            if len(buf) < 10:
                return None
            length = struct.unpack("!Q", bytes(buf[2:10]))[0]
            offset = 10
        if length > MAX_MESSAGE_BYTES:
            raise WebSocketError("frame exceeds the size limit")
        key = b""
        if masked:
            if len(buf) < offset + 4:
                return None
            key = bytes(buf[offset : offset + 4])
            offset += 4
        if len(buf) < offset + length:
            return None
        payload = bytes(buf[offset : offset + length])
        del buf[: offset + length]
        if masked:
            payload = _apply_mask(payload, key)
        return fin, opcode, payload


# ======================================================================
# Blocking client
# ======================================================================


class WebSocketClient:
    """A blocking WebSocket client for background threads.

    ``recv`` blocks until a text message arrives and transparently
    answers pings; ``send_text`` is safe to call from any thread.

    Args:
        url: ``ws://host:port/path`` (``wss`` is not supported; dev
            traffic stays on the local network).
        timeout: Connect and read timeout in seconds. Reads that time
            out raise ``socket.timeout``, letting the owning thread
            check for shutdown between waits.
    """

    def __init__(self, url: str, *, timeout: Optional[float] = 30.0) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("ws", "http"):
            raise ValueError(f"unsupported WebSocket scheme in {url!r} (use ws://)")
        if not parts.hostname:
            raise ValueError(f"missing host in {url!r}")
        self.host = parts.hostname
        self.port = parts.port or 80
        self.path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._decoder = FrameDecoder()
        self._send_lock = threading.Lock()
        self._closed = False

    @property
    def connected(self) -> bool:
        """Whether the socket is open."""
        return self._sock is not None and not self._closed

    def connect(self) -> None:
        """Open the TCP connection and complete the upgrade handshake."""
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        request, key = client_handshake_request(f"{self.host}:{self.port}", self.path)
        sock.sendall(request)
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise HandshakeError("connection closed during the WebSocket handshake")
            head += chunk
            if len(head) > 65536:
                sock.close()
                raise HandshakeError("oversized handshake response")
        head_bytes, _, rest = head.partition(b"\r\n\r\n")
        status, headers = parse_http_headers(head_bytes)
        if " 101 " not in f" {status} ":
            sock.close()
            raise HandshakeError(f"server refused the upgrade: {status}")
        if headers.get("sec-websocket-accept") != accept_key(key):
            sock.close()
            raise HandshakeError("bad Sec-WebSocket-Accept from server")
        self._sock = sock
        self._closed = False
        if rest:
            # Frames may already trail the handshake; keep them.
            self._pending = list(self._decoder.feed(rest))
        else:
            self._pending = []

    def send_text(self, text: str) -> None:
        """Send one text message (masked, as clients must)."""
        self._send(encode_frame(TEXT, text.encode("utf-8"), mask=True))

    def _send(self, frame: bytes) -> None:
        sock = self._sock
        if sock is None or self._closed:
            raise WebSocketError("socket is closed")
        with self._send_lock:
            sock.sendall(frame)

    def recv(self) -> Optional[str]:
        """Block until a text message arrives.

        Returns ``None`` once the peer closes. Raises ``socket.timeout``
        when the read timeout elapses with no data, so callers can poll
        a shutdown flag.
        """
        while True:
            if self._pending:
                opcode, payload = self._pending.pop(0)
            else:
                sock = self._sock
                if sock is None or self._closed:
                    return None
                chunk = sock.recv(65536)
                if not chunk:
                    self._mark_closed()
                    return None
                messages = list(self._decoder.feed(chunk))
                if not messages:
                    continue
                opcode, payload = messages[0]
                self._pending = messages[1:]
            if opcode == TEXT:
                return payload.decode("utf-8")
            if opcode == PING:
                try:
                    self._send(encode_frame(PONG, payload, mask=True))
                except OSError:
                    self._mark_closed()
                    return None
                continue
            if opcode == CLOSE:
                try:
                    self._send(encode_close(mask=True))
                except OSError:
                    pass
                self._mark_closed()
                return None
            # Binary and pong frames are ignored by the dev protocol.

    def close(self, code: int = 1000, reason: str = "") -> None:
        """Send a close frame (best effort) and shut the socket."""
        sock = self._sock
        if sock is None:
            return
        if not self._closed:
            try:
                self._send(encode_close(code, reason, mask=True))
            except OSError:
                pass
        self._mark_closed()

    def _mark_closed(self) -> None:
        self._closed = True
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
