"""Demo screen for [`pn.StatusBar`][pythonnative.StatusBar].

The status bar isn't visually testable via Maestro's accessibility
tree on every platform, so the demo focuses on confirming that
mounting a StatusBar element doesn't crash. A toggle button rotates
between ``"dark"`` and ``"light"`` bar styles so flows can drive the
prop, and a second toggle flips the ``translucent`` (Android) and
``animated`` (iOS) flags added in RFC 0002.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def StatusBarDemo() -> pn.Element:
    """Render a StatusBar plus toggles for ``bar_style``, ``translucent``, and ``animated``."""
    style, set_style = pn.use_state("dark")
    translucent, set_translucent = pn.use_state(False)

    return demo_screen(
        "StatusBar",
        "Toggle the status bar style between dark and light.",
        section(
            "Status bar style",
            pn.StatusBar(
                bar_style=style,
                translucent=translucent,
                animated=True,
                background_color="#00000000" if translucent else None,
            ),
            result_text("Bar style", style),
            result_text("Translucent", "ON" if translucent else "OFF"),
            buttons_row(
                pn.Button(
                    "Toggle",
                    on_press=lambda: set_style("light" if style == "dark" else "dark"),
                ),
                pn.Button("Toggle translucent", on_press=lambda: set_translucent(not translucent)),
            ),
            hint("Tapping the button flips Bar style between 'dark' and 'light'."),
        ),
    )
