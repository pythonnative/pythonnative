"""Demo screen for [`pn.StatusBar`][pythonnative.StatusBar].

The status bar isn't visually testable via Maestro's accessibility
tree on every platform, so the demo focuses on confirming that
mounting a StatusBar element doesn't crash. A toggle button rotates
between ``"dark"`` and ``"light"`` bar styles so flows can drive the
prop.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def StatusBarDemo() -> pn.Element:
    """Render a StatusBar plus a toggle that flips its ``bar_style`` prop."""
    style, set_style = pn.use_state("dark")

    return demo_screen(
        "StatusBar",
        "Toggle the status bar style between dark and light.",
        section(
            "Status bar style",
            pn.StatusBar(bar_style=style),
            result_text("Bar style", style),
            pn.Button(
                "Toggle",
                on_press=lambda: set_style("light" if style == "dark" else "dark"),
            ),
            hint("Tapping the button flips Bar style between 'dark' and 'light'."),
        ),
    )
