"""Demo screen for [`pn.Platform`][pythonnative.Platform].

Reads ``Platform.OS`` and ``Platform.Version`` and prints them. Maestro
asserts the OS line and version line are present; the version value
varies by device.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def PlatformInfoDemo() -> pn.Element:
    """Render Platform.OS and Platform.Version."""
    return demo_screen(
        "Platform info",
        "Platform.OS and Platform.Version values.",
        section(
            "Platform values",
            result_text("OS", pn.Platform.OS),
            result_text("Version", pn.Platform.Version),
            result_text("PythonNative", pn.__version__),
            hint("Maestro asserts the OS line and the version line are visible."),
        ),
    )
