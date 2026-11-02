"""Demo screen for [`pn.WebSocket`][pythonnative.WebSocket] and multipart ``fetch``.

The screen starts an RFC 6455 echo server and a small HTTP server on localhost, inside
the app, so the flow proves the real client over a real socket with no external network.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import struct
from typing import Any

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, ResultText

_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


async def _echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    head = (await reader.readuntil(b"\r\n\r\n")).decode()
    key = next(line.split(":", 1)[1].strip() for line in head.split("\r\n") if line.lower().startswith("sec-websocket-key"))
    accept = base64.b64encode(hashlib.sha1(key.encode() + _GUID).digest()).decode()  # noqa: S324
    writer.write(f"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
    await writer.drain()
    try:
        while True:
            first, second = await reader.readexactly(2)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", await reader.readexactly(2))[0]
            mask = await reader.readexactly(4)
            data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(await reader.readexactly(length)))
            opcode = first & 0x0F
            header = bytes([0x80 | opcode, length]) if length < 126 else bytes([0x80 | opcode, 126]) + struct.pack("!H", length)
            writer.write(header + data)
            await writer.drain()
            if opcode == 0x8:
                return
    except asyncio.IncompleteReadError:
        return
    finally:
        writer.close()


async def _multipart(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    head = (await reader.readuntil(b"\r\n\r\n")).decode().lower()
    length = int(next(line.split(":")[1] for line in head.split("\r\n") if line.startswith("content-length")))
    body = await reader.readexactly(length)
    reply = f"{body.count(b'Content-Disposition')} parts"
    writer.write(f"HTTP/1.1 200 OK\r\nContent-Length: {len(reply)}\r\nConnection: close\r\n\r\n{reply}".encode())
    await writer.drain()
    writer.close()


@pn.component
def WebSocketDemo() -> pn.Node:
    """Round-trip messages through a WebSocket and upload a multipart form."""
    echoed, set_echoed = pn.use_state("waiting")
    close_code, set_close_code = pn.use_state("open")
    uploaded, set_uploaded = pn.use_state("waiting")
    progress, set_progress = pn.use_state("0")

    async def run() -> None:
        servers: list[Any] = []
        try:
            echo_server = await asyncio.start_server(_echo, "127.0.0.1", 0)
            upload_server = await asyncio.start_server(_multipart, "127.0.0.1", 0)
            servers += [echo_server, upload_server]
            port = echo_server.sockets[0].getsockname()[1]
            socket = await pn.WebSocket(f"ws://127.0.0.1:{port}/").open()
            await socket.send("hello from Python")
            await socket.send_json({"value": 42})
            set_echoed(f"{await socket.recv()} / {await socket.recv()}")
            await socket.close()
            set_close_code(str(socket.close_code))
            response = await pn.fetch(
                f"http://127.0.0.1:{upload_server.sockets[0].getsockname()[1]}/",
                method="POST",
                body={"caption": "Trailhead"},
                files={"photo": ("trail.jpg", b"x" * 100000, "image/jpeg")},
                on_upload_progress=lambda sent, total: set_progress(f"{sent * 100 // total}"),
            )
            set_uploaded(response.text())
        finally:
            for server in servers:
                server.close()

    pn.use_effect(run, [])
    return DemoScreen(
        "WebSocket",
        "A real socket and a multipart upload against servers on localhost.",
        DemoSection(
            "Local socket",
            ResultText("Echoed", echoed),
            ResultText("Close code", close_code),
            ResultText("Uploaded", uploaded),
            ResultText("Progress", progress),
        ),
    )
