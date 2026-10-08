"""iOS transport: C-ABI calls into ``PythonNativeKit`` through ``ctypes``.

The Swift package exports ``@_cdecl`` symbols (see
``docs/concepts/bridge.md``). They're resolved from the running process
with ``ctypes.CDLL(None)``, which releases the GIL during native calls.
Widget operations are marshaled to the platform UI thread, and incoming
events are queued to the Python application thread. The callback registered
with ``pn_bridge_set_callback`` acquires the GIL when it enters Python.

Strings returned by native are ``strdup``'d; this module copies them
and hands the pointer back to ``pn_bridge_free``.
"""

from __future__ import annotations

import ctypes
from typing import Any, Callable, Optional

__all__ = ["IOSTransport"]

# void (*)(const char *kind, int64_t tag, const char *name, const char *payload_json)
_CALLBACK_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p)


class IOSTransport:
    """Bind the ``pn_bridge_*`` symbols and expose them as Python methods."""

    name = "ios"
    asynchronous_commits = True

    def __init__(self, lib: Any = None) -> None:
        self._lib = lib if lib is not None else ctypes.CDLL(None)
        self._apply = self._sym("pn_bridge_apply", ctypes.c_void_p, [ctypes.c_char_p])
        self._command = self._sym(
            "pn_bridge_command", ctypes.c_void_p, [ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p]
        )
        self._animate = self._sym("pn_bridge_animate", ctypes.c_void_p, [ctypes.c_int64, ctypes.c_char_p])
        self._call = self._sym("pn_bridge_call", ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p])
        self._free = self._sym("pn_bridge_free", None, [ctypes.c_void_p])
        self._set_callback = self._sym("pn_bridge_set_callback", None, [_CALLBACK_TYPE])
        self._version = self._sym("pn_bridge_protocol_version", ctypes.c_int, [])
        # A strong reference so the C trampoline outlives native's calls.
        self._callback_c: Any = None

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

    def apply(self, transaction_json: str) -> str:
        """Apply one serialized transaction (a JSON array of ops)."""
        return self._take(self._apply(transaction_json.encode("utf-8"))) or ""

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""
        return self._take(self._command(int(tag), name.encode("utf-8"), args_json.encode("utf-8")))

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""
        return self._take(self._animate(int(tag), request_json.encode("utf-8")))

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        return self._take(self._call(module.encode("utf-8"), method.encode("utf-8"), args_json.encode("utf-8")))

    def set_callback(self, callback: Callable[[str, int, str, str], None]) -> None:
        """Install ``callback`` as the native -> Python entry point."""

        def trampoline(kind: bytes, tag: int, name: bytes, payload: bytes) -> None:
            try:
                callback(_decode(kind), int(tag), _decode(name), _decode(payload))
            except Exception as exc:  # pragma: no cover - last-resort guard
                print(f"[pn.bridge] callback raised: {exc!r}")

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
