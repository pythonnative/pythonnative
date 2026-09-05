"""The native bridge: one channel between Python and Swift / Kotlin.

Everything that crosses into native code goes through a
[`Transport`][pythonnative.bridge.Transport] (``apply`` a transaction,
``measure`` a view, run a ``command``, drive an ``animate`` request, or
``call`` a native module), and everything native sends back arrives at
[`native_callback`][pythonnative.bridge.native_callback]. The protocol
is documented in ``docs/concepts/bridge.md``.

Under ``pn preview`` the native side is a browser page, reached through
[`WebTransport`][pythonnative.bridge.web.WebTransport]; the preview
installs it with [`set_transport`][pythonnative.bridge.set_transport]
before any screen mounts. In headless tests there is no transport at
all: native modules fall back to their Python implementations, and
tests that want to exercise the bridge itself install a
[`FakeTransport`][pythonnative.bridge.fake.FakeTransport].
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional, Protocol, Tuple

from . import codec

__all__ = [
    "PROTOCOL_VERSION",
    "Transport",
    "get_transport",
    "has_transport",
    "handshake",
    "native_callback",
    "post_to_main",
    "set_transport",
]

PROTOCOL_VERSION = 1
"""Bridge protocol version this Python package speaks."""


class Transport(Protocol):
    """The Python -> native half of the bridge."""

    name: str

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the native library."""

    def apply(self, transaction_json: str) -> None:
        """Apply one serialized transaction (a JSON array of ops)."""

    def measure(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Return the intrinsic ``(width, height)`` of the view ``tag`` under the constraints."""

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""

    def set_callback(self, callback: Callable[[str, int, str, str], Optional[str]]) -> None:
        """Install ``callback`` as the native -> Python entry point."""


# ======================================================================
# Transport selection
# ======================================================================

_transport: Optional[Transport] = None
_transport_lock = threading.Lock()
_explicit = False


def _create_platform_transport() -> Optional[Transport]:
    from ..utils import IS_ANDROID, IS_IOS, IS_WEB

    if IS_IOS:
        from .ios import IOSTransport

        transport: Transport = IOSTransport()
        transport.set_callback(native_callback)
        return transport
    if IS_ANDROID:
        from .android import AndroidTransport

        return AndroidTransport()
    if IS_WEB:
        raise RuntimeError(
            "PN_PLATFORM=web is set but no browser preview transport is installed. "
            "Start the app with `pn preview` (or `pn start`), which installs the WebTransport."
        )
    return None


def get_transport() -> Transport:
    """Return the active transport, creating the platform one on first use.

    Raises:
        RuntimeError: Off-device, where no native runtime exists.
    """
    global _transport
    if _transport is not None:
        return _transport
    with _transport_lock:
        if _transport is None:
            created = _create_platform_transport()
            if created is None:
                raise RuntimeError(
                    "No native bridge is available on this platform (running off-device). "
                    "Use `pn preview` for the browser renderer or install a FakeTransport in tests."
                )
            _transport = created
    return _transport


def has_transport() -> bool:
    """Whether a transport exists or can be created without raising."""
    if _transport is not None:
        return True
    if _explicit:
        return False
    from ..utils import IS_ANDROID, IS_IOS, IS_WEB

    return bool(IS_IOS or IS_ANDROID or IS_WEB)


def set_transport(transport: Optional[Transport]) -> None:
    """Install a transport explicitly (tests) or reset with ``None``."""
    global _transport, _explicit
    with _transport_lock:
        _transport = transport
        _explicit = transport is not None
    if transport is not None:
        transport.set_callback(native_callback)


def handshake() -> int:
    """Verify the native library speaks our protocol version.

    Called by the native templates right after Python starts. Returns
    the negotiated version.

    Raises:
        RuntimeError: On a version mismatch, with a hint to rebuild.
    """
    version = get_transport().protocol_version()
    if version != PROTOCOL_VERSION:
        raise RuntimeError(
            f"Bridge protocol mismatch: the native runtime speaks v{version} but pythonnative "
            f"expects v{PROTOCOL_VERSION}. Re-run 'pn build' so the staged template matches the "
            "installed pythonnative package."
        )
    return version


# ======================================================================
# Main-queue posting
# ======================================================================
#
# The asyncio guest loop and ``call_on_main_thread`` need a way to run
# a callable on the platform main thread's next turn. Native provides
# it: ``Host.post()`` schedules ``callback("pump")``, which drains this
# queue. Keeping the queue in Python means one native crossing per
# batch of callables rather than one per callable.

_main_queue: Deque[Callable[[], None]] = deque()
_main_queue_lock = threading.Lock()
_pump_requested = False


def post_to_main(fn: Callable[[], None]) -> None:
    """Queue ``fn`` for the next main-thread turn (never runs inline)."""
    global _pump_requested
    with _main_queue_lock:
        _main_queue.append(fn)
        if _pump_requested:
            return
        _pump_requested = True
    try:
        get_transport().call("Host", "post", codec.dumps({"call_id": 0, "args": {}}))
    except Exception as exc:
        with _main_queue_lock:
            _pump_requested = False
        print(f"[pn.bridge] Host.post failed; running {len(_main_queue)} queued callable(s) inline: {exc!r}")
        _drain_main_queue()


def _drain_main_queue() -> None:
    global _pump_requested
    while True:
        with _main_queue_lock:
            if not _main_queue:
                _pump_requested = False
                return
            fn = _main_queue.popleft()
        try:
            fn()
        except Exception as exc:
            print(f"[pn.bridge] main-thread callable raised: {exc!r}")


# ======================================================================
# native -> Python
# ======================================================================


def native_callback(kind: str, tag: int, name: str, payload: str) -> Optional[str]:
    """Single entry point for every native -> Python message.

    Args:
        kind: ``"event"``, ``"module"``, ``"host"``, ``"animation"``,
            or ``"pump"``.
        tag: View tag (events), screen id (host), otherwise ``0``.
        name: Event name, module name, or host event.
        payload: JSON text whose shape depends on ``kind``.

    Returns:
        A JSON string for request-style messages (a handler's return
        value, ``"true"`` / ``"false"`` for ``back_pressed``), else
        ``None``. Never raises: failures are reported through
        ``diagnostics`` so nothing propagates into UIKit or the
        Android looper.
    """
    try:
        if kind == "event":
            return _on_event(int(tag), name, payload)
        if kind == "module":
            from ..native_modules.registry import dispatch_module_message

            dispatch_module_message(name, codec.loads(payload) or {})
            return None
        if kind == "host":
            from ..hosts.native import dispatch_host_event

            return dispatch_host_event(int(tag), name, codec.loads(payload))
        if kind == "animation":
            from ..animated import native_animation_completed

            data = codec.loads(payload) or {}
            native_animation_completed(int(data.get("id", 0)), bool(data.get("finished", True)))
            return None
        if kind == "pump":
            _drain_main_queue()
            return None
        print(f"[pn.bridge] unknown callback kind {kind!r}")
    except Exception as exc:
        from .. import diagnostics

        if not diagnostics.report_error(exc, phase=f"bridge {kind}:{name}"):
            import traceback

            traceback.print_exc()
    return None


def _on_event(tag: int, name: str, payload: str) -> Optional[str]:
    from ..events import get_event_registry

    args = codec.loads(payload)
    if args is None:
        args = []
    elif not isinstance(args, list):
        args = [args]
    callback = get_event_registry().get(tag, name)
    if callback is None:
        from ..native_views import get_registry

        backend = get_registry()
        internal = getattr(backend, "handle_internal_event", None)
        if internal is not None:
            result = internal(tag, name, args)
            return None if result is None else codec.dumps(codec.to_jsonable(result))
        return None
    try:
        result = callback(*args)
    except Exception as exc:
        from .. import diagnostics

        if not diagnostics.report_error(exc, phase=f"event {name!r}"):
            import traceback

            traceback.print_exc()
        return None
    if result is None:
        return None
    try:
        return codec.dumps(codec.to_jsonable(result))
    except (TypeError, ValueError):
        return None


def _reset_for_tests() -> None:
    """Drop the transport and any queued main-thread work (test isolation)."""
    global _transport, _explicit, _pump_requested
    with _transport_lock:
        _transport = None
        _explicit = False
    with _main_queue_lock:
        _main_queue.clear()
        _pump_requested = False


def transport_state() -> Dict[str, Any]:
    """Diagnostics snapshot (used by ``pn doctor`` and tests)."""
    return {
        "transport": None if _transport is None else _transport.name,
        "protocol_version": PROTOCOL_VERSION,
        "queued_main_callables": len(_main_queue),
    }
