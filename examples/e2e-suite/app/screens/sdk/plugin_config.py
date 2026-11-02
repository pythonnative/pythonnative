"""Demo screen for a local plugin's C target and declarative configuration.

``native/checksum`` compiles C through SwiftPM on iOS and CMake on Android, and sets
a key in ``Info.plist`` and ``AndroidManifest.xml`` from an option. If any of that
breaks, the app doesn't build or this screen shows ``missing``.
"""

from __future__ import annotations

from typing import Protocol

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, ResultText
from pythonnative.native_modules.registry import native_module
from pythonnative.sdk.plugin import plugin_module


class _ChecksumService(Protocol):
    def adler32(self, text: str) -> int: ...

    def configured_value(self) -> str: ...


class _Fallback:
    def adler32(self, text: str) -> int:
        import zlib

        return zlib.adler32(text.encode())

    def configured_value(self) -> str:
        return "configured by a plugin"


plugin_module("Checksum", _ChecksumService, plugin="e2e_checksum", fallback=_Fallback)


@pn.component
def PluginConfigDemo() -> pn.Node:
    """Show a value computed in the plugin's C code and one its manifest configured."""
    module = native_module("Checksum")
    return DemoScreen(
        "Native plugin configuration",
        DemoSection(
            "Plugin",
            ResultText("Adler-32 of Wikipedia", module.call("adler32", text="Wikipedia")),
            ResultText("Configured value", module.call("configured_value")),
        ),
    )
