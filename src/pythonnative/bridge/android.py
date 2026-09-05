"""Android transport: the ``com.pythonnative.runtime.PNBridge`` class via Chaquopy.

``PNBridge`` is the only Java class Python touches. Its static methods
mirror the C entry points used on iOS (see ``docs/concepts/bridge.md``).
The reverse direction (native -> Python) is installed by the template's
``MainActivity``, which implements ``PythonHost`` by calling
[`pythonnative.bridge.native_callback`][pythonnative.bridge.native_callback]
through Chaquopy; this transport therefore has nothing to register.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

__all__ = ["AndroidTransport"]

BRIDGE_CLASS = "com.pythonnative.runtime.PNBridge"


class AndroidTransport:
    """Thin wrapper over the static ``PNBridge`` methods."""

    name = "android"

    def __init__(self, bridge_class: Any = None) -> None:
        if bridge_class is None:
            from java import jclass

            try:
                bridge_class = jclass(BRIDGE_CLASS)
            except Exception as exc:
                raise RuntimeError(
                    f"{BRIDGE_CLASS} is not on the classpath. Rebuild the app with 'pn run android' or "
                    "'pn build android' so the pythonnative Gradle module is included."
                ) from exc
        self._bridge = bridge_class

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the native library."""
        return int(self._bridge.protocolVersion())

    def apply(self, transaction_json: str) -> None:
        """Apply one serialized transaction (a JSON array of ops)."""
        self._bridge.apply(transaction_json)

    def measure(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Return the intrinsic ``(width, height)`` of the view ``tag`` under the constraints."""
        packed = self._bridge.measure(int(tag), float(max_width), float(max_height))
        if not packed:
            return (0.0, 0.0)
        text = str(packed)
        w, _, h = text.partition(",")
        try:
            return (float(w), float(h))
        except ValueError:
            return (0.0, 0.0)

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""
        return _opt_str(self._bridge.command(int(tag), name, args_json))

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""
        return _opt_str(self._bridge.animate(int(tag), request_json))

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        return _opt_str(self._bridge.call(module, method, args_json))

    def set_callback(self, callback: Callable[[str, int, str, str], Optional[str]]) -> None:
        """No-op: the Android template installs the host through ``PNBridge.setHost``."""
        del callback


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
