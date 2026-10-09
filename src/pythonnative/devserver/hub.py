"""Route DevTools and debugger traffic between pages, the preview, and dev clients.

The dev server's [`Hub`][pythonnative.devserver.hub.Hub] keeps one
[`Target`][pythonnative.devserver.hub.Target] per running app: the browser
preview (whose agent lives in the ``pn start`` process) and every
connected dev client. DevTools pages pick a target and send it requests;
targets publish events, which the hub keeps a short history of and
broadcasts to every page. Debugger connections are joined to the
selected target's debug adapter.

Everything here runs on the dev server's own event loop.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol

__all__ = ["ClientTarget", "Hub", "LocalTarget", "Target"]

_HISTORY = {"log": 1000, "problem": 200, "network": 300, "perf": 120, "select": 1}
_RPC_TIMEOUT = 30.0
Logger = Callable[[str], None]


class Page(Protocol):
    """A connected DevTools page."""

    def send(self, message: Dict[str, Any]) -> None:
        """Queue one JSON message to the page."""


# ======================================================================
# Targets
# ======================================================================


class Target:
    """A running app DevTools can talk to."""

    id: str = ""
    kind: str = "app"
    platform: str = ""
    device: str = ""
    connected_at: float = 0.0

    def __init__(self) -> None:
        self.history: Dict[str, Deque[Dict[str, Any]]] = {topic: deque(maxlen=size) for topic, size in _HISTORY.items()}

    def label(self) -> str:
        """``ios iPhone 17 Pro``, ``Browser preview``."""
        return " ".join(part for part in (self.platform, self.device) if part) or self.id

    def describe(self) -> Dict[str, Any]:
        """The target's entry in the DevTools target list."""
        return {
            "id": self.id,
            "kind": self.kind,
            "platform": self.platform,
            "device": self.device,
            "label": self.label(),
            "connected_at": self.connected_at,
        }

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = _RPC_TIMEOUT) -> Any:
        """Run devtools request ``method`` in the app and return its result."""
        raise NotImplementedError

    async def open_debug_stream(self, hub: "Hub") -> "DebugStream":
        """Start the app's debug adapter and connect to it."""
        raise NotImplementedError


class DebugStream:
    """One debugger connection's path to an app's adapter."""

    def __init__(
        self,
        write: Callable[[bytes], None],
        close: Callable[[], None],
    ) -> None:
        self.write = write
        self.close = close
        self.on_data: Callable[[bytes], None] = lambda data: None
        self.on_close: Callable[[], None] = lambda: None


class LocalTarget(Target):
    """The browser preview: its agent runs in this process.

    Args:
        agent: The preview's [`Agent`][pythonnative.devtools.agent.Agent].
        loop: The dev server's loop, where replies are delivered.
    """

    def __init__(self, agent: Any, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self.id = "preview"
        self.kind = "preview"
        self.platform = "web"
        self.device = "Browser preview"
        self.connected_at = time.time()
        self.agent = agent
        self._loop = loop

    def label(self) -> str:
        """Always ``Browser preview``."""
        return "Browser preview"

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = _RPC_TIMEOUT) -> Any:
        """Dispatch to the in-process agent and wait for its reply on this loop."""
        future: asyncio.Future[Any] = self._loop.create_future()

        def reply(result: Optional[Any], error: Optional[str]) -> None:
            def settle() -> None:
                if future.done():
                    return
                if error is not None:
                    future.set_exception(RuntimeError(error))
                else:
                    future.set_result(result)

            self._loop.call_soon_threadsafe(settle)

        self.agent.dispatch(method, params or {}, reply)
        return await asyncio.wait_for(future, timeout)

    async def open_debug_stream(self, hub: "Hub") -> DebugStream:
        """Start the preview's adapter and connect to it directly."""
        result = await self.call("debug", {"host_paths": None}, timeout=120.0)
        reader, writer = await asyncio.open_connection("127.0.0.1", int(result["port"]))
        stream = DebugStream(write=writer.write, close=writer.close)

        async def pump() -> None:
            try:
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        break
                    stream.on_data(chunk)
            except (ConnectionError, OSError):
                pass
            finally:
                stream.on_close()

        asyncio.get_running_loop().create_task(pump())
        return stream


class ClientTarget(Target):
    """A connected dev client (PythonNative Go or a debug build).

    Args:
        client_id: The server's connection id.
        send: Queues one JSON message to the client.
    """

    _ids = itertools.count(1)

    def __init__(self, client_id: int, send: Callable[[Dict[str, Any]], None]) -> None:
        super().__init__()
        self.client_id = client_id
        self.id = f"client-{client_id}"
        self.connected_at = time.time()
        self._send = send
        self._pending: Dict[int, asyncio.Future[Any]] = {}
        self._streams: Dict[int, DebugStream] = {}
        self.distributions: Dict[str, str] = {}
        self.packages: Dict[str, str] = {}
        self.ready = False
        self.package_waiters: Dict[int, asyncio.Future[Any]] = {}
        self.sync_packages: Optional[Callable[[List[str], Optional[int]], int]] = None
        self.host_paths: Dict[str, Any] = {}

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = _RPC_TIMEOUT) -> Any:
        """Send an ``rpc`` to the client and wait for its ``rpc_result``."""
        request_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        self._send({"type": "rpc", "id": request_id, "method": method, "params": params or {}})
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)

    def settle(self, message: Dict[str, Any]) -> None:
        """Deliver an ``rpc_result``."""
        future = self._pending.get(int(message.get("id") or 0))
        if future is None or future.done():
            return
        if message.get("error") is not None:
            future.set_exception(RuntimeError(str(message["error"])))
        else:
            future.set_result(message.get("result"))

    def packages_ready(self, message: Dict[str, Any]) -> None:
        """A ``packages`` message with a request id finished installing."""
        future = self.package_waiters.pop(int(message.get("request") or 0), None)
        if future is not None and not future.done():
            future.set_result(message.get("packages"))

    async def ensure_packages(self, names: List[str], timeout: float = 120.0) -> None:
        """Sync ``names`` (and their dependencies) to the client and wait until they're installed."""
        if all(name in self.distributions or name in self.packages for name in names):
            return
        if self.sync_packages is None:
            raise RuntimeError("this server can't sync packages")
        request = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self.package_waiters[request] = future
        if not self.sync_packages(names, request):
            self.package_waiters.pop(request, None)
            return
        await asyncio.wait_for(future, timeout)

    async def open_debug_stream(self, hub: "Hub") -> DebugStream:
        """Sync ``debugpy``, start the client's adapter, and tunnel to it."""
        await self.ensure_packages(["debugpy"])
        result = await self.call("debug", {"host_paths": self.host_paths}, timeout=120.0)
        stream_id = next(self._ids)

        def write(data: bytes) -> None:
            self._send({"type": "tunnel", "stream": stream_id, "op": "data", "data": base64.b64encode(data).decode()})

        def close() -> None:
            if self._streams.pop(stream_id, None) is not None:
                self._send({"type": "tunnel", "stream": stream_id, "op": "close"})

        stream = DebugStream(write=write, close=close)
        self._streams[stream_id] = stream
        self._send({"type": "tunnel", "stream": stream_id, "op": "open", "port": int(result["port"])})
        return stream

    def tunnel(self, message: Dict[str, Any]) -> None:
        """Deliver a ``tunnel`` message from the client."""
        stream_id = int(message.get("stream") or 0)
        stream = self._streams.get(stream_id)
        if stream is None:
            return
        if message.get("op") == "data" and isinstance(message.get("data"), str):
            stream.on_data(base64.b64decode(message["data"]))
        elif message.get("op") == "close":
            self._streams.pop(stream_id, None)
            stream.on_close()

    def disconnected(self) -> None:
        """Fail pending requests and close streams."""
        for future in list(self._pending.values()) + list(self.package_waiters.values()):
            if not future.done():
                future.set_exception(ConnectionError("the dev client disconnected"))
        for stream in list(self._streams.values()):
            stream.on_close()
        self._streams.clear()


# ======================================================================
# Hub
# ======================================================================


class Hub:
    """Targets, DevTools pages, event history, and debugger routing.

    Args:
        log: Terminal logger.
        on_open_devtools: Called when an app asks to open DevTools.
    """

    def __init__(
        self,
        log: Logger,
        on_open_devtools: Optional[Callable[[], None]] = None,
        on_open_editor: Optional[Callable[[str, int], Any]] = None,
    ) -> None:
        self.log = log
        self.targets: Dict[str, Target] = {}
        self.pages: List[Page] = []
        self.debug_target: Optional[str] = None
        self.debug_sessions = 0
        self._on_open_devtools = on_open_devtools
        self._on_open_editor = on_open_editor

    # -- targets ---------------------------------------------------------

    def add_target(self, target: Target) -> None:
        """Register a target and tell every page."""
        self.targets[target.id] = target
        self.broadcast_targets()

    def remove_target(self, target_id: str) -> None:
        """Forget a target and tell every page."""
        target = self.targets.pop(target_id, None)
        if isinstance(target, ClientTarget):
            target.disconnected()
        if self.debug_target == target_id:
            self.debug_target = None
        self.broadcast_targets()

    def describe_targets(self) -> List[Dict[str, Any]]:
        """Every target, most recently connected first."""
        return [target.describe() for target in sorted(self.targets.values(), key=lambda t: -t.connected_at)]

    def broadcast_targets(self) -> None:
        """Send the target list to every page."""
        self.broadcast({"type": "targets", "targets": self.describe_targets(), "debug_target": self.debug_target})

    def default_target(self) -> Optional[Target]:
        """The debug target: the chosen one, else the newest device, else the preview."""
        if self.debug_target and self.debug_target in self.targets:
            return self.targets[self.debug_target]
        clients = [t for t in self.targets.values() if isinstance(t, ClientTarget)]
        if clients:
            return max(clients, key=lambda t: t.connected_at)
        return self.targets.get("preview")

    # -- events ----------------------------------------------------------

    def on_event(self, target_id: str, topic: str, data: Any) -> None:
        """Record and broadcast an event a target published."""
        target = self.targets.get(target_id)
        if topic == "open_devtools":
            if self._on_open_devtools is not None:
                self._on_open_devtools()
            return
        if topic == "open_editor":
            if self._on_open_editor is not None and isinstance(data, dict):
                self._on_open_editor(str(data.get("file") or ""), int(data.get("line") or 1))
            return
        if topic == "debug_target":
            self.debug_target = target_id
            self.log(
                f"[pn] debugger: attach to 127.0.0.1:{self.debug_port or 5678} (VS Code: 'PythonNative: Attach') "
                f"to debug {target.label() if target else target_id}"
            )
            self.broadcast_targets()
            return
        event = {"type": "event", "target": target_id, "topic": topic, "data": data, "time": time.time()}
        if target is not None and topic in target.history:
            target.history[topic].append(event)
        self.broadcast(event)

    def log_line(self, target_id: str, level: str, text: str) -> None:
        """Record one log line from a target."""
        self.on_event(target_id, "log", {"level": level, "text": text})

    # -- pages -----------------------------------------------------------

    def add_page(self, page: Page) -> None:
        """Register a DevTools page; it receives the targets and history."""
        self.pages.append(page)
        history: List[Dict[str, Any]] = []
        for target in self.targets.values():
            for events in target.history.values():
                history.extend(events)
        history.sort(key=lambda event: event.get("time", 0))
        page.send({"type": "targets", "targets": self.describe_targets(), "debug_target": self.debug_target})
        page.send({"type": "history", "events": history})

    def remove_page(self, page: Page) -> None:
        """Forget a page."""
        try:
            self.pages.remove(page)
        except ValueError:
            pass

    def broadcast(self, message: Dict[str, Any]) -> None:
        """Send ``message`` to every page."""
        for page in list(self.pages):
            try:
                page.send(message)
            except Exception:
                self.remove_page(page)

    async def page_request(self, page: Page, message: Dict[str, Any]) -> None:
        """Answer one ``rpc`` message from a page."""
        request_id = message.get("id")
        target = self.targets.get(str(message.get("target") or ""))
        if target is None:
            page.send({"type": "rpc_result", "id": request_id, "error": "that app isn't connected"})
            return
        try:
            result = await target.call(str(message.get("method") or ""), message.get("params") or {})
        except asyncio.TimeoutError:
            page.send({"type": "rpc_result", "id": request_id, "error": "the app didn't answer in time"})
            return
        except Exception as exc:
            page.send({"type": "rpc_result", "id": request_id, "error": str(exc)})
            return
        page.send({"type": "rpc_result", "id": request_id, "result": result})

    def clear(self, target_id: Optional[str], topic: str) -> None:
        """Drop a topic's history (``target_id=None`` for every target)."""
        for target in self.targets.values():
            if target_id in (None, target.id) and topic in target.history:
                target.history[topic].clear()

    # -- debugger --------------------------------------------------------

    debug_port: int = 0

    async def debug_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Join a Debug Adapter Protocol connection to the selected target's adapter."""
        target = self.default_target()
        if target is None:
            self.log("[pn] debugger: no app is connected; start one, then attach again")
            writer.close()
            return
        self.log(f"[pn] debugger: attaching to {target.label()}")
        try:
            stream = await target.open_debug_stream(self)
        except Exception as exc:
            reason = str(exc) or ("it didn't answer in time" if isinstance(exc, asyncio.TimeoutError) else repr(exc))
            self.log(f"[pn] debugger: couldn't start debugging {target.label()}: {reason}")
            writer.close()
            return
        self.debug_sessions += 1
        self.broadcast({"type": "debug", "state": "attached", "target": target.id})
        closed = asyncio.Event()

        def on_data(data: bytes) -> None:
            try:
                writer.write(data)
            except Exception:
                closed.set()

        def on_close() -> None:
            closed.set()

        stream.on_data = on_data
        stream.on_close = on_close

        async def pump() -> None:
            try:
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        break
                    stream.write(chunk)
            except (ConnectionError, OSError):
                pass
            finally:
                closed.set()

        task = asyncio.get_running_loop().create_task(pump())
        await closed.wait()
        task.cancel()
        stream.close()
        try:
            writer.close()
        except Exception:
            pass
        self.debug_sessions -= 1
        self.broadcast({"type": "debug", "state": "detached", "target": target.id})
        self.log(f"[pn] debugger: detached from {target.label()}")


def encode(message: Dict[str, Any]) -> str:
    """Serialize a hub message (``default=str`` so odd values never break a page)."""
    return json.dumps(message, default=str)
