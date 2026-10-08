"""The native bridge: one channel between Python and Swift / Kotlin.

Everything that crosses into native code goes through a
[`Transport`][pythonnative.bridge.Transport] (``apply`` a transaction, run a
``command``, drive an ``animate`` request, or ``call`` a native module), and
everything native sends back arrives at
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
from typing import Callable, Optional, Protocol

from . import codec

__all__ = [
    "PROTOCOL_VERSION",
    "Transport",
    "get_transport",
    "has_transport",
    "handshake",
    "native_callback",
    "set_transport",
]

from .commits import PROTOCOL_VERSION

"""Bridge protocol version this Python package speaks."""


class Transport(Protocol):
    """The Python -> native half of the bridge.

    Native and browser transports run Yoga beside their widgets. Only the
    headless [`FakeTransport`][pythonnative.bridge.fake.FakeTransport] lays
    out in Python, so it alone also answers ``measure`` and accepts frame
    (``f``) operations.
    """

    name: str

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the native library."""

    def apply(self, transaction_json: str) -> str:
        """Apply one serialized transaction (a JSON array of ops)."""

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""

    def set_callback(self, callback: Callable[[str, int, str, str], None]) -> None:
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
    if getattr(get_transport(), "name", "") in {"ios", "android"}:
        from ..sdk.schema import YOGA_VERSION, fingerprint

        reply = codec.loads(get_transport().call("Runtime", "capabilities", codec.dumps({"id": 0, "args": {}})))
        capabilities = reply.get("value", {}) if isinstance(reply, dict) else {}
        if capabilities.get("schema") != fingerprint() or capabilities.get("yoga") != YOGA_VERSION:
            raise RuntimeError("Native component contracts changed. Rebuild the app with 'pn run'.")
    return version


# ======================================================================
# native -> Python
# ======================================================================


# Callback threads coalesce continuous input before the application loop
# drains. Native callback threads and the loop both change the table.
_continuous: dict[tuple[int, str], list[str]] = {}
_continuous_lock = threading.Lock()
_CONTINUOUS_EVENTS = frozenset({"on_scroll", "on_window", "on_selection_change", "on_gesture_update"})


def _deliver_continuous(tag: int, name: str, slot: list[str]) -> None:
    with _continuous_lock:
        if _continuous.get((tag, name)) is slot:
            del _continuous[(tag, name)]
        payload = slot[0]
    native_callback("event", tag, name, payload)


def native_callback(kind: str, tag: int, name: str, payload: str) -> None:
    """Single entry point for every native -> Python message.

    Native delivers every message asynchronously, from its events thread,
    and never waits for a result. This function never raises: failures
    are reported through ``diagnostics`` so nothing propagates into UIKit
    or the Android looper.

    Args:
        kind: ``"event"``, ``"module"``, ``"host"``, ``"animation"``, or
            ``"layout"``.
        tag: View tag (events), screen id (host), otherwise ``0``.
        name: Event name, module name, or host event.
        payload: JSON text whose shape depends on ``kind``.
    """
    from ..runtime import _on_loop_thread, get_loop

    loop = get_loop()
    if loop.is_running() and not _on_loop_thread(loop):
        if kind == "event" and name in _CONTINUOUS_EVENTS:
            key = (tag, name)
            with _continuous_lock:
                slot = _continuous.get(key)
                if slot is not None:
                    slot[0] = payload
                    return None
                slot = _continuous[key] = [payload]
            loop.call_soon_threadsafe(_deliver_continuous, tag, name, slot)
        else:
            # Later continuous input starts a new slot, delivered after
            # this discrete message.
            with _continuous_lock:
                _continuous.clear()
            loop.call_soon_threadsafe(native_callback, kind, tag, name, payload)
        return
    try:
        if kind == "layout":
            from ..native_views import get_backend

            get_backend().accept_layout(codec.loads(payload))
        elif kind == "event":
            _on_event(int(tag), name, payload)
        elif kind == "module":
            from ..native_modules.registry import dispatch_module_message

            dispatch_module_message(name, codec.loads(payload) or {})
        elif kind == "host":
            from ..hosts.native import dispatch_host_event

            dispatch_host_event(int(tag), name, codec.loads(payload))
        elif kind == "animation":
            from ..animated import native_animation_completed

            data = codec.loads(payload) or {}
            native_animation_completed(int(data.get("id", 0)), bool(data.get("finished", True)))
        else:
            print(f"[pn.bridge] unknown callback kind {kind!r}")
    except Exception as exc:
        from .. import diagnostics

        if not diagnostics.report_error(exc, phase=f"bridge {kind}:{name}"):
            import traceback

            traceback.print_exc()


def _on_event(tag: int, name: str, payload: str) -> None:
    from ..events import get_event_registry

    args = codec.loads(payload)
    from ..native_views import get_backend

    backend = get_backend()
    defer = getattr(backend, "defer_event", None)
    if defer is not None and defer(tag, name, args):
        return
    accept = getattr(backend, "accept_event", None)
    if accept is not None:
        if not accept(tag, name, args):
            return
        args = args["args"]
    if args is None:
        args = []
    elif not isinstance(args, list):
        args = [args]
    if get_event_registry().get(tag, name) is None:
        return
    try:
        get_event_registry().invoke(tag, name, *args)
    except Exception as exc:
        from .. import diagnostics

        if not diagnostics.report_error(exc, phase=f"event {name!r}"):
            import traceback

            traceback.print_exc()


def _reset_for_tests() -> None:
    """Drop the transport for test isolation."""
    global _transport, _explicit
    with _transport_lock:
        _transport = None
        _explicit = False
