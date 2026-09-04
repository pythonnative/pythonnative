"""The browser preview's half of the bridge.

``pn preview`` renders an app in a browser tab. Rather than a second
rendering backend, the page is treated as *the native runtime*: it
receives the very same JSON transactions the Swift and Kotlin runtimes
apply, answers the same synchronous ``measure`` / ``command`` /
``animate`` / ``call`` requests, and raises the same
``callback(kind, tag, name, payload)`` events. The reconciler therefore
runs the on-device
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
and the on-device
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost]
unchanged; only this transport differs, and it is about moving strings
over a WebSocket.

Threads:

- The **main thread** owns the framework: it drains
  [`WebTransport.run_main_loop`][pythonnative.bridge.web.WebTransport.run_main_loop],
  which is the browser's stand-in for the UIKit / Android main queue.
  Every callback from the page and every asyncio pump runs there.
- The **dev server thread** owns the socket. It delivers page messages
  to the transport, which either settles a waiting request (``res``)
  or queues work for the main thread.

Synchronous requests (``measure`` above all) block the main thread on a
``threading.Event`` until the page answers; the page is single-threaded
but its message handling is asynchronous, so it can answer a
``measure`` while it is itself awaiting Python (a row bind, say).

Wire format (JSON arrays):

- Python -> page: ``["apply", ops]``, ``["measure", id, tag, w, h]``,
  ``["command", id, tag, name, args]``, ``["animate", id, tag, request]``,
  ``["call", id, module, method, envelope]``, ``["res", id, result]``,
  ``["dev", {...}]``.
- Page -> Python: ``["res", id, result]``, ``["cb", kind, tag, name,
  payload]`` (fire and forget), ``["req", id, kind, tag, name, payload]``
  (Python answers with ``res``), ``["gesture", tag, phase, info]``
  (pointer stream for the Python gesture arbiter), ``["dev", {...}]``.

``payload`` / ``args`` / ``request`` / ``result`` are JSON *strings*,
exactly the text the native protocol carries, so both sides reuse their
existing codecs. Modules the page implements (``Host``, ``Alert``,
``Clipboard``, ...) are called there; every other native module falls
back to the Python implementations in
``pythonnative.native_modules.fallback``.
"""

from __future__ import annotations

import itertools
import json
import queue
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import PROTOCOL_VERSION, codec

__all__ = ["BROWSER_MODULES", "WebTransport"]

BROWSER_MODULES = frozenset(
    {"Host", "Alert", "Clipboard", "Linking", "Share", "Haptics", "NetInfo", "AppState", "Device"}
)
"""Native modules the preview page implements; the rest use Python fallbacks."""

REQUEST_TIMEOUT_S = 15.0
"""How long a synchronous request waits for the page before giving up."""

Callback = Callable[[str, int, str, str], Optional[str]]


class _Waiter:
    __slots__ = ("event", "result", "failed")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Any = None
        self.failed = False


class WebTransport:
    """Bridge transport whose native side is a browser page.

    Install it with ``pythonnative.bridge.set_transport`` and hand it to
    ``DevServer.set_preview_channel``; the page does the rest.

    Args:
        log: Where diagnostics go (defaults to stderr).
    """

    name = "web"

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
        self._gestures: Dict[int, Tuple[str, Any]] = {}
        self._gesture_timer: Optional[Any] = None
        self._warned_no_peer = False
        self._python_modules: Dict[str, Any] = {}
        self.on_dev_message: Optional[Callable[[Dict[str, Any]], None]] = None
        """Hook for ``["dev", {...}]`` messages from the page (runs on the main thread)."""
        self.on_peer_changed: Optional[Callable[[bool], None]] = None
        """Called on the main thread with ``True`` on connect and ``False`` on disconnect."""

    # ------------------------------------------------------------------
    # Transport protocol
    # ------------------------------------------------------------------

    def protocol_version(self) -> int:
        """The page speaks whatever this package speaks; they ship together."""
        return PROTOCOL_VERSION

    def set_callback(self, callback: Callback) -> None:
        """Install the native -> Python entry point (``bridge.native_callback``)."""
        self._callback = callback

    def apply(self, transaction_json: str) -> None:
        """Forward one commit to the page (fire and forget)."""
        self._send('["apply",' + transaction_json + "]")

    def measure(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Ask the page for the intrinsic size of ``tag``."""
        result = self._request(["measure", None, int(tag), _finite(max_width), _finite(max_height)])
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            try:
                return (float(result[0]), float(result[1]))
            except (TypeError, ValueError):
                return (0.0, 0.0)
        return (0.0, 0.0)

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""
        result = self._request(["command", None, int(tag), name, args_json])
        return _as_json_text(result)

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""
        result = self._request(["animate", None, int(tag), request_json])
        return _as_json_text(result)

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module: ``Host.post`` locally, page modules over the wire, others in Python."""
        if module == "Host" and method == "post":
            self.post_to_main(self._pump)
            return codec.dumps({"ok": True, "value": None})
        if module in BROWSER_MODULES:
            result = self._request(["call", None, module, method, args_json])
            return _as_json_text(result)
        return self._call_python_module(module, method, args_json)

    # ------------------------------------------------------------------
    # Main thread
    # ------------------------------------------------------------------

    def post_to_main(self, fn: Callable[[], None]) -> None:
        """Queue ``fn`` for the main loop (never runs inline)."""
        self._main.put(fn)

    def run_main_loop(self, *, until: Optional[Callable[[], bool]] = None) -> None:
        """Drain main-thread work until ``stop`` is called (or ``until`` holds).

        This is the preview's event loop: the browser's stand-in for the
        platform main queue. Call it from the thread that should own the
        framework (the process main thread under ``pn preview``).
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
        """Run queued main-thread work inline (tests); returns how many jobs ran."""
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

    def _pump(self) -> None:
        if self._callback is not None:
            self._callback("pump", 0, "", "")

    # ------------------------------------------------------------------
    # PreviewChannel (called on the dev server thread)
    # ------------------------------------------------------------------

    def on_preview_connected(self, peer: Any, info: Dict[str, Any]) -> None:
        """A page connected; it becomes the native side."""
        del info
        with self._peer_lock:
            self._peer = peer
        self._warned_no_peer = False
        self.post_to_main(lambda: self._peer_changed(True))

    def on_preview_disconnected(self, peer: Any) -> None:
        """The page went away: fail waiting requests and tear down its screens."""
        with self._peer_lock:
            if self._peer is not peer:
                return
            self._peer = None
        self._fail_all_waiters()
        self.post_to_main(lambda: self._peer_changed(False))

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
            self.post_to_main(lambda: self._deliver_fire_and_forget(message))
            return
        if kind == "req":
            self.post_to_main(lambda: self._deliver_request(peer, message))
            return
        if kind == "gesture":
            self.post_to_main(lambda: self._deliver_gesture(message))
            return
        if kind == "dev":
            payload = message[1] if len(message) > 1 and isinstance(message[1], dict) else {}
            self.post_to_main(lambda: self._deliver_dev(payload))
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
    # Inbound (main thread)
    # ------------------------------------------------------------------

    def _deliver_callback(self, message: List[Any]) -> Optional[str]:
        callback = self._callback
        if callback is None or len(message) < 5:
            return None
        _, kind, tag, name, payload = message[:5]
        return callback(str(kind), int(tag or 0), str(name), _payload_text(payload))

    def _deliver_fire_and_forget(self, message: List[Any]) -> None:
        self._deliver_callback(message)

    def _deliver_request(self, peer: Any, message: List[Any]) -> None:
        if len(message) < 6:
            return
        request_id = message[1]
        result = self._deliver_callback(["cb", *message[2:6]])
        try:
            peer.send(codec.dumps(["res", request_id, result]))
        except Exception as exc:
            self._log(f"[pn preview] reply failed: {exc!r}")

    def _deliver_dev(self, payload: Dict[str, Any]) -> None:
        hook = self.on_dev_message
        if hook is not None:
            hook(payload)

    def _peer_changed(self, connected: bool) -> None:
        if not connected:
            self._gestures.clear()
        hook = self.on_peer_changed
        if hook is not None:
            hook(connected)

    # -- gestures --------------------------------------------------------

    def _deliver_gesture(self, message: List[Any]) -> None:
        """Feed a pointer event to the tag's arbiter (built from the specs the page sends)."""
        if len(message) < 4:
            return
        _, tag, phase, info = message[:4]
        if not isinstance(info, dict):
            return
        tag = int(tag)
        arbiter = self._arbiter_for(tag, info.get("specs"))
        if arbiter is None:
            return
        t = float(info.get("t", time.monotonic()))
        pointer = int(info.get("id", 0))
        x = float(info.get("x", 0.0))
        y = float(info.get("y", 0.0))
        if phase == "down":
            arbiter.pointer_down(pointer, x, y, t)
        elif phase == "move":
            arbiter.pointer_move(pointer, x, y, t)
        elif phase == "up":
            arbiter.pointer_up(pointer, x, y, t)
        elif phase == "cancel":
            arbiter.cancel(t)
        elif phase == "clear":
            self._gestures.pop(tag, None)
            return
        self._schedule_gesture_poll()

    def _arbiter_for(self, tag: int, specs: Any) -> Any:
        if not isinstance(specs, list) or not specs:
            self._gestures.pop(tag, None)
            return None
        key = json.dumps(specs, sort_keys=True)
        existing = self._gestures.get(tag)
        if existing is not None and existing[0] == key:
            return existing[1]
        from ..events import dispatch_event
        from ..gestures import make_arbiter

        def _emit(index: int, payload: Dict[str, Any]) -> None:
            dispatch_event(tag, f"gesture:{index}", payload)

        arbiter = make_arbiter([s for s in specs if isinstance(s, dict)], _emit)
        self._gestures[tag] = (key, arbiter)
        return arbiter

    def _schedule_gesture_poll(self) -> None:
        """Arm one timer for the earliest recognizer deadline (long press, multi-tap windows)."""
        deadlines = [d for _, arb in self._gestures.values() if (d := arb.next_deadline()) is not None]
        if not deadlines:
            return
        delay = max(0.0, min(deadlines) - time.monotonic())
        from ..runtime import get_loop

        loop = get_loop()
        if self._gesture_timer is not None:
            try:
                self._gesture_timer.cancel()
            except Exception:
                pass
        self._gesture_timer = loop.call_later(delay + 0.001, self._poll_gestures)

    def _poll_gestures(self) -> None:
        self._gesture_timer = None
        now = time.monotonic()
        for _, arbiter in list(self._gestures.values()):
            arbiter.poll(now)
        self._schedule_gesture_poll()

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


_UNBOUNDED = 1e6
"""Wire sentinel for an unconstrained measure axis (matches the native runtimes)."""


def _finite(value: Any) -> float:
    """JSON has no infinity: clamp unconstrained measure axes to the wire sentinel."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return _UNBOUNDED
    if f != f or f > _UNBOUNDED or f == float("inf"):
        return _UNBOUNDED
    return max(0.0, f)


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
