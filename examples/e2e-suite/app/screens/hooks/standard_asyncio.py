"""Verify ordinary asyncio networking and cancellation inside embedded Python."""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, ResultText


@pn.component
def StandardAsyncioDemo() -> pn.Node:
    """Run socket, TaskGroup, timeout, and cancellation checks on the app's event loop."""
    status, set_status = pn.use_state("idle")

    async def verify() -> None:
        set_status("running")
        finished = asyncio.Event()

        async def echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                writer.write(await reader.readexactly(4))
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                finished.set()

        async with asyncio.timeout(5):
            async with await asyncio.start_server(echo, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                try:
                    async with asyncio.TaskGroup() as group:
                        received = group.create_task(reader.readexactly(4))
                        writer.write(b"ping")
                        group.create_task(writer.drain())
                    assert received.result() == b"ping"
                    await finished.wait()
                finally:
                    writer.close()
                    await writer.wait_closed()
        try:
            async with asyncio.timeout(0.01):
                await asyncio.Event().wait()
        except TimeoutError:
            pass
        else:
            raise AssertionError("timeout didn't cancel the wait")
        task = asyncio.create_task(asyncio.sleep(60))
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled()
        set_status("passed")

    return DemoScreen(
        "Standard asyncio",
        "Sockets, TaskGroup, timeouts, and cancellation in embedded Python.",
        DemoSection("Runtime", ResultText("Runtime", status), pn.Button("Run runtime checks", on_press=verify)),
    )
