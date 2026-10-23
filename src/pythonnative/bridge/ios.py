"""iOS transport: the renderer core and ``PythonNativeKit`` through ``ctypes``.

The app binary links the renderer core and the Swift package. Both export
C symbols (see ``docs/concepts/bridge.md``), resolved from the running
process with ``ctypes.CDLL(None)``, which releases the GIL during native
calls. Commits go to the core, which lays out on the calling thread and
queues mount transactions for the main thread; native module calls go to
Swift. The callback registered with ``pn_bridge_set_callback`` acquires
the GIL when it enters Python.

Strings returned by Swift are ``strdup``'d; this module copies them and
hands the pointer back to ``pn_bridge_free``.
"""

from __future__ import annotations

import ctypes
from typing import Any, Callable, Optional

from .core import RendererCore

__all__ = ["IOSTransport"]

# void (*)(const char *kind, int64_t tag, const char *name, const char *payload_json)
_CALLBACK_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p)


class IOSTransport:
    """Bind the core and the ``pn_bridge_*`` module symbols."""

    name = "ios"
    asynchronous_commits = True

    def __init__(self, lib: Any = None) -> None:
        self._lib = lib if lib is not None else ctypes.CDLL(None)
        self.core = RendererCore(self._lib)
        self._call = self._sym("pn_bridge_call", ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p])
        self._free = self._sym("pn_bridge_free", None, [ctypes.c_void_p])
        self._set_callback = self._sym("pn_bridge_set_callback", None, [_CALLBACK_TYPE])
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

    # -- the renderer core ----------------------------------------------

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the renderer core."""
        return self.core.protocol_version()

    def load_contracts(self, document: str) -> None:
        """Compile the merged component contracts into the core."""
        self.core.load_contracts(document, "ios")

    def commit(self, envelope_json: str) -> str:
        """Validate, apply, and lay out one commit; returns its acknowledgement."""
        return self.core.commit(envelope_json)

    def layout(self, request_json: str) -> str:
        """Lay out without a commit."""
        return self.core.layout(request_json)

    def command(self, surface: int, tag: int, name: str, args_json: str, call_id: int) -> str:
        """Queue a view command behind pending mounts."""
        return self.core.command(surface, tag, name, args_json, call_id)

    def animate(self, surface: int, tag: int, request_json: str) -> str:
        """Queue an animation request behind pending mounts."""
        return self.core.animate(surface, tag, request_json)

    def measure(self, surface: int, tag: int) -> str:
        """The shadow and window frames of a view."""
        return self.core.measure(surface, tag)

    # -- native modules -------------------------------------------------

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
