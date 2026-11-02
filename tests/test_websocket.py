"""Tests for ``pn.WebSocket`` against a small real server on localhost."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import struct
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

import pytest

import pythonnative as pn
from pythonnative.websocket import WebSocket, WebSocketClosed, WebSocketError

GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


async def read_frame(reader: asyncio.StreamReader) -> tuple[bool, int, bytes]:
    first, second = await reader.readexactly(2)
    assert second & 0x80, "clients must mask"
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    mask = await reader.readexactly(4)
    data = await reader.readexactly(length)
    return bool(first & 0x80), first & 0x0F, bytes(b ^ mask[i % 4] for i, b in enumerate(data))


def frame(opcode: int, data: bytes = b"", *, final: bool = True, rsv: int = 0) -> bytes:
    head = bytes([(0x80 if final else 0) | rsv | opcode])
    if len(data) < 126:
        return head + bytes([len(data)]) + data
    if len(data) < 65536:
        return head + bytes([126]) + struct.pack("!H", len(data)) + data
    return head + bytes([127]) + struct.pack("!Q", len(data)) + data


def handshake_key(head: str) -> str:
    return next(
        line.split(":", 1)[1].strip() for line in head.split("\r\n") if line.lower().startswith("sec-websocket-key")
    )


Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


async def serve(handler: Handler, *, accept: Optional[str] = None, status: str = "101 Switching Protocols") -> Any:
    async def connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        key = next(
            line.split(":", 1)[1].strip() for line in head.split("\r\n") if line.lower().startswith("sec-websocket-key")
        )
        digest = accept or base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode()  # noqa: S324
        extra = "Sec-WebSocket-Protocol: chat\r\n" if "Sec-WebSocket-Protocol" in head else ""
        writer.write(f"HTTP/1.1 {status}\r\nSec-WebSocket-Accept: {digest}\r\n{extra}\r\n".encode())
        await writer.drain()
        try:
            await handler(reader, writer)
        finally:
            writer.close()

    return await asyncio.start_server(connection, "127.0.0.1", 0)


def url(server: Any, path: str = "/") -> str:
    return f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}{path}"


async def echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    while True:
        _, opcode, data = await read_frame(reader)
        if opcode == 0x8:
            writer.write(frame(0x8, data))
            await writer.drain()
            return
        writer.write(frame(opcode, data))
        await writer.drain()


@pytest.fixture
async def echo_server() -> AsyncIterator[Any]:
    server = await serve(echo)
    async with server:
        yield server


async def test_text_binary_and_json_round_trip(echo_server: Any) -> None:
    async with WebSocket(url(echo_server)) as socket:
        await socket.send("hello")
        assert await socket.recv() == "hello"
        await socket.send(b"\x00\x01")
        assert await socket.recv() == b"\x00\x01"
        await socket.send_json({"a": 1})
        assert await socket.recv_json() == {"a": 1}


@pytest.mark.parametrize("size", [125, 126, 65535, 65536])
async def test_every_length_encoding(echo_server: Any, size: int) -> None:
    async with WebSocket(url(echo_server)) as socket:
        await socket.send(b"x" * size)
        assert await socket.recv() == b"x" * size


async def test_async_iteration_stops_on_a_normal_close() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(frame(0x1, b"one") + frame(0x1, b"two") + frame(0x8, struct.pack("!H", 1000)))
        await writer.drain()
        await read_frame(reader)

    async with await serve(handler) as server:
        async with WebSocket(url(server)) as socket:
            assert [message async for message in socket] == ["one", "two"]
            assert socket.close_code == 1000


async def test_fragmented_messages_are_reassembled() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(frame(0x1, b"hel", final=False) + frame(0x9, b"p") + frame(0x0, b"lo"))
        await writer.drain()
        assert await read_frame(reader) == (True, 0xA, b"p")

    async with await serve(handler) as server:
        async with WebSocket(url(server)) as socket:
            assert await socket.recv() == "hello"


async def test_handshake_rejection_and_bad_accept() -> None:
    async def nothing(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        return None

    async with await serve(nothing, status="403 Forbidden") as server:
        with pytest.raises(WebSocketError, match="403"):
            await WebSocket(url(server)).open()
    async with await serve(nothing, accept="wrong") as server:
        with pytest.raises(WebSocketError, match="handshake"):
            await WebSocket(url(server)).open()


async def test_protocol_query_and_headers_reach_the_server() -> None:
    seen: dict[str, str] = {}

    async def connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        seen["head"] = head
        key = next(
            line.split(":", 1)[1].strip() for line in head.split("\r\n") if line.lower().startswith("sec-websocket-key")
        )
        digest = base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode()  # noqa: S324
        writer.write(
            f"HTTP/1.1 101 OK\r\nSec-WebSocket-Accept: {digest}\r\nSec-WebSocket-Protocol: chat\r\n\r\n".encode()
        )
        await writer.drain()
        writer.close()

    async with await asyncio.start_server(connection, "127.0.0.1", 0) as server:
        socket = WebSocket(url(server, "/feed?a=1"), headers={"Authorization": "Bearer x"}, protocols=["chat"])
        await socket.open()
        assert socket.protocol == "chat"
        await socket.close()
    assert seen["head"].startswith("GET /feed?a=1 HTTP/1.1")
    assert "Authorization: Bearer x" in seen["head"]


async def test_dropped_connection_raises_abnormal_close() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(frame(0x1, b"last"))
        await writer.drain()

    async with await serve(handler) as server:
        socket = await WebSocket(url(server)).open()
        assert await socket.recv() == "last"
        with pytest.raises(WebSocketClosed) as info:
            await socket.recv()
        assert info.value.code == 1006
        with pytest.raises(WebSocketClosed):
            await socket.recv()
        with pytest.raises(WebSocketClosed):
            await socket.send("too late")
        await socket.close()


async def test_iteration_raises_on_abnormal_close() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        return None

    async with await serve(handler) as server:
        async with WebSocket(url(server)) as socket:
            with pytest.raises(WebSocketClosed):
                async for _ in socket:
                    pass


async def test_a_protocol_violation_fails_the_connection() -> None:
    received: list[tuple[bool, int, bytes]] = []

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(frame(0x1, b"x", rsv=0x40))
        await writer.drain()
        received.append(await read_frame(reader))

    async with await serve(handler) as server:
        socket = await WebSocket(url(server)).open()
        with pytest.raises(WebSocketClosed) as info:
            await socket.recv()
        assert info.value.code == 1002
        await socket.close()
    assert received[0][1] == 0x8
    assert struct.unpack("!H", received[0][2][:2])[0] == 1002


async def test_too_big_messages_are_refused() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(frame(0x2, b"x" * 100))
        await writer.drain()
        await read_frame(reader)

    async with await serve(handler) as server:
        socket = await WebSocket(url(server), max_message_size=10).open()
        with pytest.raises(WebSocketClosed) as info:
            await socket.recv()
        assert info.value.code == 1009
        await socket.close()


async def test_ping_waits_for_pong_and_heartbeat_detects_a_dead_peer() -> None:
    async def silent(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await asyncio.sleep(5)

    async with await serve(echo) as server:
        async with WebSocket(url(server)) as socket:
            # The echoed ping draws a pong from the client, which the server echoes back.
            await socket.ping(timeout=5)
    async with await serve(silent) as server:
        socket = await WebSocket(url(server), heartbeat=0.05).open()
        with pytest.raises(WebSocketClosed) as info:
            await socket.recv()
        assert info.value.code == 1006
        await socket.close()


async def test_close_is_clean_and_repeatable(echo_server: Any) -> None:
    socket = await WebSocket(url(echo_server)).open()
    await socket.close(1000, "done")
    assert socket.close_code == 1000
    await socket.close()


def test_rejects_other_schemes_and_exports() -> None:
    with pytest.raises(ValueError):
        WebSocket("https://example.com")
    assert pn.WebSocket is WebSocket
