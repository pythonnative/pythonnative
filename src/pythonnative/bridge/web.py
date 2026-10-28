"""WebSocket transport for the browser preview.

The page runs the renderer core as WebAssembly, the same C++ core the iOS
and Android apps link (RFC 0007), and mounts its transactions into DOM
widgets. This transport is Python's side of it: every call a device
transport makes into the core (``load_contracts``, ``commit``, ``layout``,
``command``, ``animate``, ``measure``) becomes a request over the dev
server's WebSocket that the page answers with the core's own JSON reply.
Everything the core emits (events, layout, animation, and host messages)
and every command result comes back as a callback, which is queued onto
the Python application thread, as on device. Native module calls go to the
page for the modules it implements and to the Python fallbacks otherwise.

Network I/O and request settlement run independently of the application
asyncio loop; no asyncio loop is pumped by the browser transport.
"""

from __future__ import annotations

import itertools
import json
import queue
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from . import PROTOCOL_VERSION, codec

__all__ = ["BROWSER_MODULES", "WebTransport"]

BROWSER_MODULES = frozenset(
    {
        "DevSupport",
        "Host",
        "Alert",
        "Clipboard",
        "Linking",
        "Share",
        "Haptics",
        "NetInfo",
        "AppState",
        "Device",
        "Keyboard",
        "AccessibilityInfo",
        "Localization",
        "WebViews",
    }
)
"""Native modules the preview page implements; the rest use Python fallbacks."""

REQUEST_TIMEOUT_S = 15.0
"""How long a synchronous request waits for the page before giving up."""

NO_PAGE = "no browser preview page is attached"

Callback = Callable[[str, int, str, str], None]


class _Waiter:
    __slots__ = ("event", "result", "failed")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Any = None
        self.failed = False


class WebTransport:
    """Bridge transport whose renderer core and widgets live in a browser page.

    Install it with ``pythonnative.bridge.set_transport`` and hand it to
    ``DevServer.set_preview_channel``; the page does the rest.

    Args:
        log: Where diagnostics go (defaults to stderr).
    """

    name = "web"
    asynchronous_commits = True

    def __init__(self, *, log: Optional[Callable[[str], None]] = None) -> None:
        self._log = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self._callback: Optional[Callback] = None
        self._peer: Any = None
        self._peer_lock = threading.Lock()
        self._ids = itertools.count(1)
        self._waiters: Dict[int, _Waiter] = {}
        self._waiters_lock = threading.Lock()
        self._main: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._main_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._warned_no_peer = False
        self._python_modules: Dict[str, Any] = {}
        self.on_dev_message: Optional[Callable[[Dict[str, Any]], None]] = None
        """Hook for ``["dev", {...}]`` messages on the Python application thread."""
        self.on_peer_changed: Optional[Callable[[bool], None]] = None
        """Called on the application thread with ``True`` on connect and ``False`` on disconnect."""

    # ------------------------------------------------------------------
    # Transport protocol: the renderer core in the page
    # ------------------------------------------------------------------

    def protocol_version(self) -> int:
        """The page's core speaks whatever this package speaks; they ship together."""
        return PROTOCOL_VERSION

    def set_callback(self, callback: Callback) -> None:
        """Install the native -> Python entry point (``bridge.native_callback``)."""
        self._callback = callback

    def load_contracts(self, document: str) -> None:
        """Compile the merged component contracts into the page's core.

        A page that connects later starts with a fresh core; the transport
        forgets what it loaded then, so the next commit loads them again.

        Raises:
            RuntimeError: When the core rejects the document.
        """
        error = self._request(["load_contracts", None, document])
        if isinstance(error, str) and error:
            raise RuntimeError(f"The renderer core rejected the component contracts: {error}")

    def commit(self, envelope_json: str) -> str:
        """Validate, apply, and lay out one commit in the page; returns its acknowledgement."""
        return self._text(self._request(["commit", None, envelope_json]), _failure("commit"))

    def layout(self, request_json: str) -> str:
        """Lay out without a commit; returns ``{"ok", "value": layout}``."""
        return self._text(self._request(["layout", None, request_json]), _failure("layout"))

    def command(self, surface: int, tag: int, name: str, args_json: str, call_id: int) -> str:
        """Queue a view command; its result arrives as a ``command`` message."""
        message = ["command", None, int(surface), int(tag), name, args_json, int(call_id)]
        return self._text(self._request(message), _failure(f"command {name!r}"))

    def animate(self, surface: int, tag: int, request_json: str) -> str:
        """Queue an animation request behind pending mounts."""
        return self._text(self._request(["animate", None, int(surface), int(tag), request_json]), _failure("animate"))

    def measure(self, surface: int, tag: int) -> str:
        """The shadow and window frames of a view, as JSON (``"null"`` when unknown)."""
        return self._text(self._request(["measure", None, int(surface), int(tag)]), "null")

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module: page modules over the wire, the others in Python."""
        if module in BROWSER_MODULES:
            result = self._request(["call", None, module, method, args_json])
            return _as_json_text(result)
        return self._call_python_module(module, method, args_json)

    @staticmethod
    def _text(result: Any, default: str) -> str:
        """The core's JSON text from a page reply, or ``default`` when there was none."""
        if isinstance(result, str) and result:
            return result
        return default

    # ------------------------------------------------------------------
    # Application thread and fallback queue
    # ------------------------------------------------------------------

    def post_to_application(self, fn: Callable[[], None]) -> None:
        """Queue ``fn`` on the application loop, or the fallback queue if it isn't running."""
        from ..runtime import get_loop

        loop = get_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(self._run_job, fn)
        else:
            self._main.put(fn)

    def run_main_loop(self, *, until: Optional[Callable[[], bool]] = None) -> None:
        """Drain fallback work until ``stop`` is called or ``until`` holds.

        The preview uses this as a coordinator while application callbacks
        run on the standard asyncio loop. When that loop isn't running,
        queued jobs execute on the thread calling this method.
        """
        self._main_thread = threading.current_thread()
        self._stop.clear()
        while not self._stop.is_set():
            if until is not None and until():
                return
            try:
                job = self._main.get(timeout=0.1)
            except queue.Empty:
                continue
            self._run_job(job)

    def drain_main(self, timeout: float = 0.0) -> int:
        """Run fallback-queue work inline for tests and return how many jobs ran."""
        self._main_thread = threading.current_thread()
        deadline = time.monotonic() + timeout
        ran = 0
        while True:
            try:
                job = self._main.get_nowait()
            except queue.Empty:
                if timeout <= 0 or time.monotonic() >= deadline:
                    return ran
                time.sleep(0.002)
                continue
            self._run_job(job)
            ran += 1

    def stop(self) -> None:
        """Make ``run_main_loop`` return."""
        self._stop.set()

    def _run_job(self, job: Callable[[], None]) -> None:
        try:
            job()
        except Exception:
            self._log("[pn preview] main-thread job raised:")
            self._log(traceback.format_exc())

    # ------------------------------------------------------------------
    # PreviewChannel (called on the dev server thread)
    # ------------------------------------------------------------------

    def on_preview_connected(self, peer: Any, info: Dict[str, Any]) -> None:
        """A page connected; it becomes the native side."""
        del info
        with self._peer_lock:
            self._peer = peer
        self._warned_no_peer = False
        self.post_to_application(lambda: self._peer_changed(True))

    def on_preview_disconnected(self, peer: Any) -> None:
        """The page went away: fail waiting requests and tear down its screens."""
        with self._peer_lock:
            if self._peer is not peer:
                return
            self._peer = None
        self._fail_all_waiters()
        self.post_to_application(lambda: self._peer_changed(False))

    def on_preview_message(self, peer: Any, text: str) -> None:
        """Route one frame from the page."""
        with self._peer_lock:
            if peer is not self._peer:
                return
        try:
            message = json.loads(text)
        except ValueError:
            self._log(f"[pn preview] dropped malformed message: {text[:120]!r}")
            return
        if not isinstance(message, list) or not message:
            return
        kind = message[0]
        if kind == "res":
            self._settle(message)
            return
        if kind == "cb":
            self.post_to_application(lambda: self._deliver_fire_and_forget(message))
            return
        if kind == "dev":
            payload = message[1] if len(message) > 1 and isinstance(message[1], dict) else {}
            self.post_to_application(lambda: self._deliver_dev(payload))
            return
        self._log(f"[pn preview] unknown message kind {kind!r}")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Whether a page is attached."""
        with self._peer_lock:
            return self._peer is not None

    def send_dev(self, payload: Dict[str, Any]) -> None:
        """Send a ``["dev", {...}]`` message to the page (logs, reload status, ...)."""
        self._send(codec.dumps(["dev", codec.to_jsonable(payload)]))

    def _send(self, text: str) -> bool:
        with self._peer_lock:
            peer = self._peer
        if peer is None:
            return False
        try:
            peer.send(text)
        except Exception as exc:
            self._log(f"[pn preview] send failed: {exc!r}")
            return False
        return True

    def _request(self, message: List[Any]) -> Any:
        """Send ``message`` (slot 1 receives the id) and block for the ``res``."""
        with self._peer_lock:
            peer = self._peer
        if peer is None:
            if not self._warned_no_peer:
                self._warned_no_peer = True
                self._log("[pn preview] request made with no browser attached; answering with defaults")
            return None
        request_id = next(self._ids)
        message[1] = request_id
        waiter = _Waiter()
        with self._waiters_lock:
            self._waiters[request_id] = waiter
        try:
            peer.send(codec.dumps(message))
        except Exception as exc:
            with self._waiters_lock:
                self._waiters.pop(request_id, None)
            self._log(f"[pn preview] request send failed: {exc!r}")
            return None
        if not waiter.event.wait(REQUEST_TIMEOUT_S):
            with self._waiters_lock:
                self._waiters.pop(request_id, None)
            self._log(f"[pn preview] {message[0]} request timed out after {REQUEST_TIMEOUT_S:g}s")
            return None
        if waiter.failed:
            return None
        return waiter.result

    def _settle(self, message: List[Any]) -> None:
        if len(message) < 2:
            return
        try:
            request_id = int(message[1])
        except (TypeError, ValueError):
            return
        with self._waiters_lock:
            waiter = self._waiters.pop(request_id, None)
        if waiter is None:
            return
        waiter.result = message[2] if len(message) > 2 else None
        waiter.event.set()

    def _fail_all_waiters(self) -> None:
        with self._waiters_lock:
            waiters = list(self._waiters.values())
            self._waiters.clear()
        for waiter in waiters:
            waiter.failed = True
            waiter.event.set()

    # ------------------------------------------------------------------
    # Inbound (application thread)
    # ------------------------------------------------------------------

    def _deliver_fire_and_forget(self, message: List[Any]) -> None:
        callback = self._callback
        if callback is None or len(message) < 5:
            return
        _, kind, tag, name, payload = message[:5]
        callback(str(kind), int(tag or 0), str(name), _payload_text(payload))

    def _deliver_dev(self, payload: Dict[str, Any]) -> None:
        hook = self.on_dev_message
        if hook is not None:
            hook(payload)

    def _peer_changed(self, connected: bool) -> None:
        if connected:
            # A new page starts with a fresh core: compile the contracts again.
            from . import _loaded_contracts

            _loaded_contracts.pop(self, None)
        hook = self.on_peer_changed
        if hook is not None:
            hook(connected)

    # -- Python module fallbacks ------------------------------------------

    def _call_python_module(self, module: str, method: str, args_json: str) -> Optional[str]:
        from ..native_modules.registry import NativeModuleError, PythonModule, dispatch_module_message

        envelope = codec.loads(args_json) or {}
        args = envelope.get("args") if isinstance(envelope, dict) else None
        call_id = int(envelope.get("call_id", 0) or 0) if isinstance(envelope, dict) else 0
        # One instance per module for the life of the transport, so stateful
        # fallbacks (Storage, SecureStore, ...) remember between calls.
        impl = self._python_modules.get(module)
        if impl is None:
            impl = self._python_modules[module] = PythonModule(module)
        try:
            fn = impl._method(method)
            value = fn(**(args or {}))
        except KeyError:
            return codec.dumps({"ok": False, "error": f"no module named {module!r}", "code": "unknown_module"})
        except NativeModuleError as exc:
            return codec.dumps({"ok": False, "error": exc.message, "code": exc.code})
        except Exception as exc:
            return codec.dumps({"ok": False, "error": str(exc)})
        if hasattr(value, "__await__"):
            if call_id == 0:
                return codec.dumps({"ok": False, "error": f"{module}.{method} is asynchronous; use call_async()"})
            from ..runtime import run_async

            async def _finish() -> None:
                try:
                    result = await value
                    dispatch_module_message(
                        module, {"call_id": call_id, "ok": True, "value": codec.to_jsonable(result)}
                    )
                except Exception as exc:
                    dispatch_module_message(module, {"call_id": call_id, "ok": False, "error": str(exc)})

            run_async(_finish())
            return codec.dumps({"pending": True})
        try:
            return codec.dumps({"ok": True, "value": codec.to_jsonable(value)})
        except TypeError:
            return codec.dumps({"ok": True, "value": None})


def _failure(what: str) -> str:
    """The core-shaped reply for a request no page answered."""
    return codec.dumps({"ok": False, "error": f"{what} failed: {NO_PAGE} (or it didn't answer)"})


def _as_json_text(result: Any) -> Optional[str]:
    """Normalize a page result to the JSON text the native protocol returns."""
    if result is None:
        return None
    if isinstance(result, str):
        return result
    return codec.dumps(result)


def _payload_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    return codec.dumps(payload)
