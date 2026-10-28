"""Android transport: ``libpncore.so`` through ``ctypes``, modules through Chaquopy.

Kotlin loads the renderer core before Python starts, registers its
platform callbacks, and exports the library's path in ``PN_CORE_LIBRARY``;
Python opens the same loaded image. Commits go to the core. Native module
calls go to the ``com.pythonnative.runtime.PNBridge`` class, the only Java
class Python touches. The reverse direction (native -> Python) is installed
by the template's ``MainActivity``, which implements ``PythonHost`` by
calling [`pythonnative.bridge.native_callback`][pythonnative.bridge.native_callback]
through Chaquopy; this transport therefore has nothing to register.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .core import RendererCore, load_core

__all__ = ["AndroidTransport"]

BRIDGE_CLASS = "com.pythonnative.runtime.PNBridge"


class AndroidTransport:
    """The renderer core plus the static ``PNBridge`` module entry point."""

    name = "android"
    asynchronous_commits = True

    def __init__(self, bridge_class: Any = None, core: Optional[RendererCore] = None) -> None:
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
        self.core = core if core is not None else load_core()

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the renderer core."""
        return self.core.protocol_version()

    def load_contracts(self, document: str) -> None:
        """Compile the merged component contracts into the core."""
        self.core.load_contracts(document, "android")

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

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        return _opt_str(self._bridge.call(module, method, args_json))

    def set_callback(self, callback: Callable[[str, int, str, str], None]) -> None:
        """No-op: the Android template installs the host through ``PNBridge.setHost``."""
        del callback


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
