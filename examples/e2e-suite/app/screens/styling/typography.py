"""Demo screen for typography styling.

Shows several font sizes, weights, colors, the boolean italic style,
and text decoration. Maestro asserts each labelled line is present.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


@pn.component
def TypographyDemo() -> pn.Node:
    """Render text in several typographic styles."""
    return DemoScreen(
        "Typography",
        "Six text variants with different size, weight, color, decoration.",
        DemoSection(
            "Variants",
            pn.Text("type-headline", style=pn.style(font_size=24, font_weight="700")),
            pn.Text("type-body", style=pn.style(font_size=16)),
            pn.Text("type-caption", style=pn.style(font_size=12, color="#6B7280")),
            pn.Text("type-italic", style=pn.style(font_size=15, italic=True)),
            pn.Text("type-underline", style=pn.style(font_size=15, text_decoration="underline")),
            pn.Text(
                "type-letter-spacing",
                style=pn.style(font_size=15, letter_spacing=2.0),
            ),
            Hint("Maestro asserts each labelled line."),
        ),
    )
