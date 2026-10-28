"""Demo screen for [`pn.Platform`][pythonnative.Platform].

Reads ``Platform.OS`` and ``Platform.Version`` and prints them. Maestro
asserts the OS line and version line are present; the version value
varies by device.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def PlatformInfoDemo() -> pn.Node:
    """Render Platform.OS and Platform.Version."""
    return DemoScreen(
        "Platform info",
        "Platform.OS and Platform.Version values.",
        DemoSection(
            "Platform values",
            ResultText("OS", pn.Platform.OS),
            ResultText("Version", pn.Platform.Version),
            ResultText("PythonNative", pn.__version__),
            Hint("Maestro asserts the OS line and the version line are visible."),
        ),
    )
