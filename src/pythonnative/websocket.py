"""A WebSocket client on ``asyncio`` (``pn.WebSocket``).

RFC 6455 in pure Python, so it behaves the same on a device, in tests, and in the
browser preview, and needs no native code or dependency. Connections run on the
application's event loop, and a connection is an async context manager and an
async iterator of messages.

Example:
    ```python
    import pythonnative as pn

    async def follow_feed() -> None:
        async with pn.WebSocket("wss://example.com/feed") as socket:
            await socket.send_json({"subscribe": "news"})
            async for message in socket:
                handle(message)
    ```

Leaving the block closes the connection, so a task owned by ``use_effect`` cleans
up when its component unmounts.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import ssl
import struct
import urllib.parse
from typing import Any, Mapping, Optional, Sequence, Type, Union

__all__ = ["WebSocket", "WebSocketClosed", "WebSocketError"]

_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_CONTINUATION, _TEXT, _BINARY, _CLOSE, _PING, _PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
_NORMAL_CLOSURE = 1000
_ABNORMAL_CLOSURE = 1006
_PROTOCOL_ERROR = 1002
_TOO_BIG = 1009

Message = Union[str, bytes]


class WebSocketError(Exception):
    """The connection couldn't open, or the peer broke the protocol."""


class WebSocketClosed(WebSocketError):
    """The connection is closed.

    Attributes:
        code: The close code, or 1006 when the connection dropped without one.
        reason: The peer's close reason, when it gave one.
    """

    def __init__(self, code: int = _ABNORMAL_CLOSURE, reason: str = "") -> None:
        super().__init__(f"WebSocket closed ({code})" + (f": {reason}" if reason else ""))
        self.code = code
        self.reason = reason


class WebSocket:
    """One client connection.

    Args:
        url: A ``ws://`` or ``wss://`` URL.
        headers: Extra handshake headers, for example ``Authorization``.
        protocols: Subprotocols to offer. The peer's choice is in
            [`protocol`][pythonnative.websocket.WebSocket.protocol].
        ssl_context: The TLS context for ``wss://``; defaults to the platform's
            certificates, the same as [`fetch`][pythonnative.net.fetch].
        heartbeat: Seconds between pings, which also detect a dead connection, or
            ``None`` to send none.
        max_message_size: Largest message to accept, in bytes.
        open_timeout: Seconds to wait for the connection and handshake.

    Raises:
        ValueError: If the URL isn't a WebSocket URL.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        protocols: Sequence[str] = (),
        ssl_context: Optional[ssl.SSLContext] = None,
        heartbeat: Optional[float] = 30.0,
        max_message_size: int = 16 * 1024 * 1024,
        open_timeout: float = 30.0,
    ) -> None:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("ws", "wss") or not parts.hostname:
            raise ValueError(f"Not a WebSocket URL: {url!r}")
        self.url = url
        self.protocol: Optional[str] = None
        """The subprotocol the peer selected."""
        self.close_code: Optional[int] = None
        """Why the connection closed; ``None`` while it's open."""
        self._parts = parts
        self._headers = dict(headers or {})
        self._protocols = tuple(protocols)
        self._ssl_context = ssl_context
        self._heartbeat = heartbeat
        self._max_message_size = max_message_size
        self._open_timeout = open_timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._messages: "asyncio.Queue[Message | WebSocketClosed]" = asyncio.Queue()
        self._background: list["asyncio.Task[None]"] = []
        self._write_lock = asyncio.Lock()
        self._close_reason = ""
        self._pong_waiters: list["asyncio.Future[None]"] = []

    # -- connection -----------------------------------------------------

    async def open(self) -> "WebSocket":
        """Connect and complete the handshake.

        Returns:
            This connection.

        Raises:
            WebSocketError: If the server refuses the upgrade.
            OSError: For network errors.
            TimeoutError: If ``open_timeout`` elapses.
        """
        try:
            async with asyncio.timeout(self._open_timeout):
                await self._connect()
                await self._handshake()
        except BaseException:
            # `async with` never reaches __aexit__ when opening fails, so close
            # the half-open connection here; close() would speak WebSocket to it.
            self._teardown()
            self._writer = self._reader = None
            raise
        self._background.append(asyncio.create_task(self._read_loop()))
        if self._heartbeat:
            self._background.append(asyncio.create_task(self._heartbeat_loop(self._heartbeat)))
        return self

    async def _connect(self) -> None:
        secure = self._parts.scheme == "wss"
        context: Optional[ssl.SSLContext] = None
        if secure:
            from .net import default_ssl_context

            context = self._ssl_context or default_ssl_context()
        self._reader, self._writer = await asyncio.open_connection(
            self._parts.hostname,
            self._parts.port or (443 if secure else 80),
            ssl=context,
            limit=2**20,
        )

    async def _handshake(self) -> None:
        assert self._reader is not None and self._writer is not None
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = self._parts.path or "/"
        if self._parts.query:
            path = f"{path}?{self._parts.query}"
        host = self._parts.hostname or ""
        if ":" in host:
            # urlsplit strips an IPv6 literal's brackets, which Host needs back.
            host = f"[{host}]"
        if self._parts.port:
            host = f"{host}:{self._parts.port}"
        headers = {
            "Host": host,
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": key,
            "Sec-WebSocket-Version": "13",
        }
        if self._protocols:
            headers["Sec-WebSocket-Protocol"] = ", ".join(self._protocols)
        headers.update(self._headers)
        request = f"GET {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
        self._writer.write(request.encode("utf-8"))
        await self._writer.drain()
        head = await self._reader.readuntil(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        status = lines[0].split(" ", 2)
        if len(status) < 2 or status[1] != "101":
            raise WebSocketError(f"The server refused the WebSocket upgrade: {lines[0]}")
        received = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            received[name.strip().lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1(key.encode("ascii") + _GUID).digest()).decode("ascii")  # noqa: S324
        if received.get("sec-websocket-accept") != expected:
            raise WebSocketError("The server's handshake didn't match this request's key.")
        self.protocol = received.get("sec-websocket-protocol")

    async def __aenter__(self) -> "WebSocket":
        return await self.open()

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc: Any, traceback: Any) -> None:
        await self.close()

    def __aiter__(self) -> "WebSocket":
        return self

    async def __anext__(self) -> Message:
        try:
            return await self.recv()
        except WebSocketClosed as closed:
            if closed.code in (_NORMAL_CLOSURE, 1001):
                raise StopAsyncIteration from None
            raise

    # -- sending and receiving ------------------------------------------

    async def send(self, message: Message) -> None:
        """Send a text (``str``) or binary (``bytes``) message.

        Raises:
            WebSocketClosed: If the connection is closed.
        """
        if isinstance(message, str):
            await self._send_frame(_TEXT, message.encode("utf-8"))
        else:
            await self._send_frame(_BINARY, bytes(message))

    async def send_json(self, value: Any) -> None:
        """Send ``value`` encoded as JSON text."""
        await self.send(json.dumps(value, default=str))

    async def recv(self) -> Message:
        """Wait for the next message.

        Raises:
            WebSocketClosed: When the connection closes. Messages that had
                already arrived are delivered first.
        """
        item = await self._messages.get()
        if isinstance(item, WebSocketClosed):
            # Every later call sees the same outcome.
            self._messages.put_nowait(item)
            raise item
        return item

    async def recv_json(self) -> Any:
        """Wait for the next message and decode it as JSON."""
        return json.loads(await self.recv())

    async def ping(self, timeout: float = 10.0) -> None:
        """Send a ping and wait for the pong.

        Raises:
            TimeoutError: If no pong arrives in time.
            WebSocketClosed: If the connection is closed.
        """
        waiter: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()
        # A pong answers every ping sent before it, so a heartbeat and a ping of
        # the app's own can overlap without one taking the other's answer.
        self._pong_waiters.append(waiter)
        try:
            await self._send_frame(_PING, b"")
            async with asyncio.timeout(timeout):
                await waiter
        finally:
            if waiter in self._pong_waiters:
                self._pong_waiters.remove(waiter)

    async def close(self, code: int = _NORMAL_CLOSURE, reason: str = "") -> None:
        """Close the connection. Safe to call more than once."""
        if self._writer is None:
            return
        if self.close_code is None:
            try:
                payload = struct.pack("!H", code) + reason.encode("utf-8")[:123]
                await self._send_frame(_CLOSE, payload)
                # The peer's close frame ends the read loop.
                done = [task for task in self._background if not task.done()]
                if done:
                    await asyncio.wait(done[:1], timeout=5.0)
            except (OSError, WebSocketClosed):
                pass
        self._finish(self.close_code or code, reason)
        for task in self._background:
            task.cancel()
        self._teardown()

    # -- frames ---------------------------------------------------------

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        writer = self._writer
        if writer is None or self.close_code is not None:
            raise WebSocketClosed(self.close_code or _ABNORMAL_CLOSURE, self._close_reason)
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", 0x80 | opcode, 0x80 | length)
        elif length < 65536:
            header = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, length)
        mask = os.urandom(4)
        masked = _mask(payload, mask)
        async with self._write_lock:
            try:
                writer.write(header + mask + masked)
                await writer.drain()
            except (OSError, RuntimeError) as exc:
                self._finish(_ABNORMAL_CLOSURE, str(exc))
                raise WebSocketClosed(_ABNORMAL_CLOSURE, str(exc)) from exc

    async def _read_frame(self) -> tuple[bool, int, bytes]:
        reader = self._reader
        assert reader is not None
        first, second = await reader.readexactly(2)
        if first & 0x70:
            raise WebSocketError("A frame used a reserved bit, but no extension was negotiated.")
        if second & 0x80:
            raise WebSocketError("Servers must not mask frames.")
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", await reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await reader.readexactly(8))[0]
        opcode = first & 0x0F
        if opcode >= _CLOSE and (length > 125 or not first & 0x80):
            raise WebSocketError("Control frames must be short and unfragmented.")
        if length > self._max_message_size:
            raise _MessageTooBig(f"A frame of {length} bytes exceeds max_message_size.")
        return bool(first & 0x80), opcode, await reader.readexactly(length) if length else b""

    async def _read_loop(self) -> None:
        buffer: list[bytes] = []
        size = 0
        kind: Optional[int] = None
        try:
            while True:
                final, opcode, payload = await self._read_frame()
                if opcode == _PING:
                    await self._send_frame(_PONG, payload)
                elif opcode == _PONG:
                    waiters, self._pong_waiters = self._pong_waiters, []
                    for waiter in waiters:
                        if not waiter.done():
                            waiter.set_result(None)
                elif opcode == _CLOSE:
                    self._on_close_frame(payload)
                    return
                elif opcode in (_TEXT, _BINARY, _CONTINUATION):
                    if opcode == _CONTINUATION:
                        if kind is None:
                            raise WebSocketError("A continuation frame had nothing to continue.")
                    else:
                        if kind is not None:
                            raise WebSocketError("A new message began inside a fragmented one.")
                        kind = opcode
                    size += len(payload)
                    if size > self._max_message_size:
                        raise _MessageTooBig(f"A message of over {size} bytes exceeds max_message_size.")
                    buffer.append(payload)
                    if final:
                        data = b"".join(buffer)
                        self._messages.put_nowait(data.decode("utf-8") if kind == _TEXT else data)
                        buffer, size, kind = [], 0, None
                else:
                    raise WebSocketError(f"Unknown frame type {opcode}.")
        except (asyncio.IncompleteReadError, OSError) as exc:
            self._finish(_ABNORMAL_CLOSURE, str(exc) if isinstance(exc, OSError) else "connection lost")
        except _MessageTooBig as exc:
            await self._fail(_TOO_BIG, str(exc))
        except (WebSocketError, UnicodeDecodeError) as exc:
            await self._fail(_PROTOCOL_ERROR, str(exc))
        finally:
            self._teardown()

    def _on_close_frame(self, payload: bytes) -> None:
        code, reason = 1005, ""
        if len(payload) >= 2:
            code = struct.unpack("!H", payload[:2])[0]
            reason = payload[2:].decode("utf-8", "replace")
        if self._writer is not None and self.close_code is None:
            # Echo the close, once, and ignore a peer that already went away.
            try:
                mask = os.urandom(4)
                body = payload[:2]
                self._writer.write(struct.pack("!BB", 0x80 | _CLOSE, 0x80 | len(body)) + mask + _mask(body, mask))
            except (OSError, RuntimeError):
                pass
        # A clean close arrives as 1000 even when the peer sent no code.
        self._finish(_NORMAL_CLOSURE if code == 1005 else code, reason)

    async def _fail(self, code: int, reason: str) -> None:
        try:
            await self._send_frame(_CLOSE, struct.pack("!H", code) + reason.encode("utf-8")[:123])
        except WebSocketClosed:
            pass
        self._finish(code, reason)

    def _finish(self, code: int, reason: str) -> None:
        if self.close_code is not None:
            return
        self.close_code = code
        self._close_reason = reason
        self._messages.put_nowait(WebSocketClosed(code, reason))
        waiters, self._pong_waiters = self._pong_waiters, []
        for waiter in waiters:
            if not waiter.done():
                waiter.set_exception(WebSocketClosed(code, reason))

    def _teardown(self) -> None:
        writer = self._writer
        if writer is not None:
            try:
                writer.close()
            except (OSError, RuntimeError):
                pass

    async def _heartbeat_loop(self, interval: float) -> None:
        while self.close_code is None:
            await asyncio.sleep(interval)
            try:
                await self.ping(timeout=interval)
            except TimeoutError:
                self._finish(_ABNORMAL_CLOSURE, "no pong within the heartbeat interval")
                self._teardown()
                return
            except WebSocketClosed:
                return


class _MessageTooBig(WebSocketError):
    """A peer's message exceeds ``max_message_size``."""


def _mask(payload: bytes, mask: bytes) -> bytes:
    # XOR as one big integer: per-byte Python would take most of a frame budget on large messages.
    repeated = (mask * (len(payload) // 4 + 1))[: len(payload)]
    value = int.from_bytes(payload, "little") ^ int.from_bytes(repeated, "little")
    return value.to_bytes(len(payload), "little")
