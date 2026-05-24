"""Demo screen for [`pn.Text`][pythonnative.Text].

Exercises the simplest element factory in isolation, including
``style`` font sizing, bold, color, and a few combined styles. Maestro
asserts that several text labels render together.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def TextDemo() -> pn.Element:
    """Render a handful of [`Text`][pythonnative.Text] variants."""
    return demo_screen(
        "Text",
        "Plain text, bold text, sized text, and colored text in one place.",
        section(
            "Plain text",
            pn.Text("Plain text line"),
            hint("Renders with default body style."),
        ),
        section(
            "Bold text",
            pn.Text("Bold text line", style=pn.style(bold=True, font_size=18)),
        ),
        section(
            "Sized + colored text",
            pn.Text(
                "Sized and colored line",
                style=pn.style(font_size=20, color="#DC2626", font_weight="600"),
            ),
        ),
        section(
            "Multi-line text",
            pn.Text(
                "First paragraph that should wrap if it is long enough to "
                "exceed the available horizontal space inside its parent.",
                style=pn.style(font_size=14, color="#1F2937", line_height=20),
            ),
        ),
    )
