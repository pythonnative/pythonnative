"""Live collaboration: one WebSocket to the sync server, kept open for as long as the app runs.

[`SyncClient.run`][app.syncing.SyncClient.run] is the whole connection's lifetime,
written as one coroutine. ``App`` runs it as an effect keyed on the server's URL,
so changing the URL cancels the old connection and starts a new one, and no URL
means there's nothing to do. Reconnecting is a loop around ``async with
pn.WebSocket``, with the delay coming from [`Backoff`][app.syncing.Backoff].
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

import pythonnative as pn

from .journal import Journal
from .models import SyncStatus
from .protocol import PROTOCOL_VERSION, ProtocolError, WireEntry

_CONNECTION_ERRORS = (OSError, TimeoutError, pn.WebSocketError, ProtocolError, ValueError)


@dataclass
class Backoff:
    """How long to wait before each reconnection attempt.

    The delay doubles after each failure, up to ``maximum``. Jitter keeps a room of
    phones that lost the same server from all coming back in the same instant.

    Attributes:
        initial: The first delay, in seconds.
        maximum: The longest delay, in seconds.
        jitter: The fraction of each delay that's random, from 0 to 1.
        failures: How many attempts in a row have failed.
    """

    initial: float = 1.0
    maximum: float = 60.0
    jitter: float = 0.2
    failures: int = 0

    def next_delay(self, random_unit: Callable[[], float] = random.random) -> float:
        """Count a failure and return how long to wait before the next attempt.

        Args:
            random_unit: Returns a number from 0 to 1. Tests pass a constant.

        Returns:
            Seconds to wait.
        """
        delay = min(self.maximum, self.initial * 2.0**self.failures)
        self.failures += 1
        return delay * (1 - self.jitter + self.jitter * random_unit())

    def reset(self) -> None:
        """Start over, because a connection worked."""
        self.failures = 0


class SyncClient:
    """Keeps this device's journal in step with the sync server.

    Args:
        journal: The journal to read from and merge into.
        backoff: The reconnection policy.
        heartbeat: Seconds between pings, which notice a dead connection.
        open_timeout: Seconds to wait for a connection and handshake.
        after_connect: Called whenever a connection is up and has exchanged
            changes. The app starts its attachment transfers from this.
    """

    def __init__(
        self,
        journal: Journal,
        *,
        backoff: Optional[Backoff] = None,
        heartbeat: float = 20.0,
        open_timeout: float = 10.0,
        after_connect: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.journal = journal
        self.backoff = backoff or Backoff()
        self.heartbeat = heartbeat
        self.open_timeout = open_timeout
        self.after_connect = after_connect
        self._wake: Optional[asyncio.Event] = None
        self._dirty: Optional[asyncio.Event] = None

    # -- the connection ------------------------------------------------

    async def run(self, url: str) -> None:
        """Stay connected to ``url`` until canceled.

        Args:
            url: The server's WebSocket URL. An empty one means no server is
                configured, which isn't a failure: the journal is simply offline.
        """
        self.backoff.reset()
        if not url:
            self._publish(SyncStatus(phase="offline"))
            return
        self._wake = asyncio.Event()
        self._dirty = asyncio.Event()
        stop_listening = self.journal.on_local_change(self.push_soon)
        detail = ""
        try:
            while True:
                self._publish(SyncStatus(phase="connecting", detail=detail, attempt=self.backoff.failures))
                try:
                    async with pn.WebSocket(url, heartbeat=self.heartbeat, open_timeout=self.open_timeout) as socket:
                        await self._session(socket, url)
                    detail = "The server closed the connection."
                except _CONNECTION_ERRORS as error:
                    detail = describe_failure(error)
                await self._wait_to_retry(detail)
        finally:
            stop_listening()
            self._wake = None
            self._dirty = None

    async def _wait_to_retry(self, detail: str) -> None:
        delay = self.backoff.next_delay()
        self._publish(SyncStatus(phase="waiting", detail=detail, attempt=self.backoff.failures, retry_in=delay))
        assert self._wake is not None
        self._wake.clear()
        with suppress(TimeoutError):
            async with asyncio.timeout(delay):
                await self._wake.wait()

    def retry_now(self) -> None:
        """Cut a backoff wait short, because the network came back or the user asked."""
        if self._wake is not None:
            self._wake.set()

    def push_soon(self) -> None:
        """Send local changes as soon as the connection can."""
        if self._dirty is not None:
            self._dirty.set()

    async def _session(self, socket: pn.WebSocket, url: str) -> None:
        """Say hello, then merge what arrives while a second task sends what changes here."""
        await socket.send_json(self._hello())
        pushing: Optional["asyncio.Task[None]"] = None
        try:
            async for raw in socket:
                message = _decode(raw)
                if message["type"] == "welcome":
                    await self._merge_welcome(message)
                    # Only a server that answered proves the connection works.
                    self.backoff.reset()
                    self._publish(SyncStatus(phase="connected", last_synced=time.time()))
                    pushing = asyncio.create_task(self._push_loop(socket))
                    if self.after_connect is not None:
                        pn.run_async(self.after_connect(url))
                else:
                    await self._handle(message)
        finally:
            if pushing is not None:
                pushing.cancel()
                with suppress(asyncio.CancelledError):
                    await pushing

    async def _push_loop(self, socket: pn.WebSocket) -> None:
        assert self._dirty is not None
        self._dirty.set()
        with suppress(pn.WebSocketClosed):
            while True:
                await self._dirty.wait()
                self._dirty.clear()
                await self._push(socket)

    async def _push(self, socket: pn.WebSocket) -> int:
        entries = await self.journal.repository.dirty_wire_entries()
        if entries:
            await socket.send_json({"type": "push", "entries": [entry.to_json() for entry in entries]})
        return len(entries)

    # -- one exchange, for the background task -------------------------

    async def sync_once(self, url: str, *, timeout: float = 25.0) -> int:
        """Connect, exchange everything outstanding, and hang up.

        The background task gets about 30 seconds on iOS, so this has a limit
        of its own and no retries: the next run is the retry.

        Args:
            url: The server's WebSocket URL.
            timeout: Seconds before giving up.

        Returns:
            How many local versions the server acknowledged.

        Raises:
            OSError: If the server can't be reached.
            TimeoutError: If the exchange doesn't finish in time.
            pythonnative.WebSocketError: If the connection fails.
        """
        acknowledged = 0
        async with asyncio.timeout(timeout):
            async with pn.WebSocket(url, heartbeat=None, open_timeout=min(timeout, self.open_timeout)) as socket:
                await socket.send_json(self._hello())
                pending = 0
                async for raw in socket:
                    message = _decode(raw)
                    if message["type"] == "welcome":
                        await self._merge_welcome(message)
                        pending = await self._push(socket)
                        if not pending:
                            break
                    else:
                        await self._handle(message)
                        if message["type"] == "ack":
                            acknowledged += len(message.get("entries") or ())
                            if acknowledged >= pending:
                                break
        return acknowledged

    # -- messages ------------------------------------------------------

    def _hello(self) -> dict[str, Any]:
        settings = self.journal.settings
        return {
            "type": "hello",
            "protocol": PROTOCOL_VERSION,
            "device": settings.device_id,
            "cursor": settings.sync_cursor,
        }

    async def _merge_welcome(self, message: Mapping[str, Any]) -> None:
        for item in message.get("changes") or ():
            await self.journal.merge_remote(WireEntry.from_json(item))
        await self._advance_cursor(message)

    async def _handle(self, message: Mapping[str, Any]) -> None:
        kind = message["type"]
        if kind == "changed":
            await self.journal.merge_remote(WireEntry.from_json(message["entry"]))
            await self._advance_cursor(message)
            if self.after_connect is not None and self.journal.settings.server_url:
                # A new attachment may have arrived along with the entry.
                pn.run_async(self.after_connect(self.journal.settings.server_url))
        elif kind == "ack":
            for item in message.get("entries") or ():
                await self.journal.repository.mark_synced(str(item["id"]), int(item["change"]))
            await self._advance_cursor(message)
            await self.journal.refresh()
            self._publish(SyncStatus(phase="connected", last_synced=time.time()))
        else:
            raise ProtocolError(f"Unknown message {kind!r}")

    async def _advance_cursor(self, message: Mapping[str, Any]) -> None:
        cursor = message.get("cursor")
        if isinstance(cursor, int) and cursor > self.journal.settings.sync_cursor:
            await self.journal.update_settings(sync_cursor=cursor)

    def _publish(self, status: SyncStatus) -> None:
        previous = self.journal.snapshot.sync
        if status.last_synced is None and previous.last_synced is not None:
            status = SyncStatus(status.phase, status.detail, status.attempt, status.retry_in, previous.last_synced)
        self.journal.set_sync_status(status)


def _decode(raw: Any) -> dict[str, Any]:
    """Parse one message, turning anything malformed into a ``ProtocolError`` that drops the connection."""
    try:
        message = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"Unreadable message: {error}") from error
    if not isinstance(message, dict) or "type" not in message:
        raise ProtocolError("A message had no type")
    return message


def describe_failure(error: Exception) -> str:
    """Say what went wrong with a connection attempt, in words for the settings screen.

    Args:
        error: What connecting or the session raised.

    Returns:
        One sentence.
    """
    if isinstance(error, TimeoutError):
        return "The server didn't answer in time."
    if isinstance(error, pn.WebSocketClosed):
        return "The connection dropped."
    if isinstance(error, pn.WebSocketError):
        return f"The server refused the connection: {error}"
    if isinstance(error, OSError):
        return "Couldn't reach the server."
    return f"The server sent something unexpected: {error}"
