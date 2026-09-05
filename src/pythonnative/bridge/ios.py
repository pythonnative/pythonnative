"""iOS transport: C-ABI calls into ``PythonNativeKit`` through ``ctypes``.

The Swift package exports ``@_cdecl`` symbols (see
``docs/concepts/bridge.md``). They're resolved from the running process
with ``ctypes.PyDLL(None)``: ``PyDLL`` keeps the GIL held across the
call, so the main thread is never parked while native applies a
transaction, and the Python callback registered with
``pn_bridge_set_callback`` can re-enter Python safely.

Strings returned by native are ``strdup``'d; this module copies them
and hands the pointer back to ``pn_bridge_free``.
"""

from __future__ import annotations

import ctypes
from typing import Any, Callable, Optional, Tuple

__all__ = ["IOSTransport"]

# const char *(*)(const char *kind, int64_t tag, const char *name, const char *payload_json)
_CALLBACK_TYPE = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p)


class IOSTransport:
    """Bind the ``pn_bridge_*`` symbols and expose them as Python methods."""

    name = "ios"

    def __init__(self, lib: Any = None) -> None:
        self._lib = lib if lib is not None else ctypes.PyDLL(None)
        self._apply = self._sym("pn_bridge_apply", None, [ctypes.c_char_p])
        self._measure = self._sym(
            "pn_bridge_measure",
            None,
            [
                ctypes.c_int64,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
            ],
        )
        self._command = self._sym(
            "pn_bridge_command", ctypes.c_void_p, [ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p]
        )
        self._animate = self._sym("pn_bridge_animate", ctypes.c_void_p, [ctypes.c_int64, ctypes.c_char_p])
        self._call = self._sym("pn_bridge_call", ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p])
        self._free = self._sym("pn_bridge_free", None, [ctypes.c_void_p])
        self._set_callback = self._sym("pn_bridge_set_callback", None, [_CALLBACK_TYPE])
        self._version = self._sym("pn_bridge_protocol_version", ctypes.c_int, [])
        # Strong references so the C trampoline and its last return
        # buffer outlive the calls native makes into them.
        self._callback_c: Any = None
        self._last_result: Any = None
        self._out_w = ctypes.c_double(0.0)
        self._out_h = ctypes.c_double(0.0)

    def _sym(self, name: str, restype: Any, argtypes: Any) -> Any:
        try:
            fn = getattr(self._lib, name)
        except AttributeError as exc:
            raise RuntimeError(
                f"PythonNativeKit symbol {name!r} is missing from the app binary. Rebuild the app with "
                "'pn run ios' or 'pn build ios' so the Swift package is linked."
            ) from exc
        fn.restype = restype
        fn.argtypes = argtypes
        return fn

    # -- protocol -------------------------------------------------------

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the native library."""
        return int(self._version())

    def apply(self, transaction_json: str) -> None:
        """Apply one serialized transaction (a JSON array of ops)."""
        self._apply(transaction_json.encode("utf-8"))

    def measure(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Return the intrinsic ``(width, height)`` of the view ``tag`` under the constraints."""
        self._measure(
            int(tag), float(max_width), float(max_height), ctypes.byref(self._out_w), ctypes.byref(self._out_h)
        )
        return (float(self._out_w.value), float(self._out_h.value))

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""
        return self._take(self._command(int(tag), name.encode("utf-8"), args_json.encode("utf-8")))

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""
        return self._take(self._animate(int(tag), request_json.encode("utf-8")))

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        return self._take(self._call(module.encode("utf-8"), method.encode("utf-8"), args_json.encode("utf-8")))

    def set_callback(self, callback: Callable[[str, int, str, str], Optional[str]]) -> None:
        """Install ``callback`` as the native -> Python entry point."""

        def trampoline(kind: bytes, tag: int, name: bytes, payload: bytes) -> Optional[int]:
            try:
                result = callback(
                    _decode(kind),
                    int(tag),
                    _decode(name),
                    _decode(payload),
                )
            except Exception as exc:  # pragma: no cover - last-resort guard
                print(f"[pn.bridge] callback raised: {exc!r}")
                return None
            if result is None:
                return None
            buf = ctypes.create_string_buffer(result.encode("utf-8"))
            self._last_result = buf
            return ctypes.addressof(buf)

        self._callback_c = _CALLBACK_TYPE(trampoline)
        self._set_callback(self._callback_c)

    # -- helpers --------------------------------------------------------

    def _take(self, ptr: Optional[int]) -> Optional[str]:
        """Copy a native ``char*`` result and free it."""
        if not ptr:
            return None
        try:
            return ctypes.string_at(ptr).decode("utf-8")
        finally:
            self._free(ptr)


def _decode(value: Optional[bytes]) -> str:
    if not value:
        return ""
    return value.decode("utf-8", "replace")
