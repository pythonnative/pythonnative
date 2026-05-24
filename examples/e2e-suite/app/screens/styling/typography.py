"""Demo screen for typography styling.

Shows several font sizes, weights, colors, and a text-decoration
example. Maestro asserts each labelled line is present.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def TypographyDemo() -> pn.Element:
    """Render text in several typographic styles."""
    return demo_screen(
        "Typography",
        "Six text variants with different size, weight, color, decoration.",
        section(
            "Variants",
            pn.Text("type-headline", style=pn.style(font_size=24, font_weight="700")),
            pn.Text("type-body", style=pn.style(font_size=16)),
            pn.Text("type-caption", style=pn.style(font_size=12, color="#6B7280")),
            pn.Text("type-italic", style=pn.style(font_size=15, font_style="italic")),
            pn.Text("type-underline", style=pn.style(font_size=15, text_decoration="underline")),
            pn.Text(
                "type-letter-spacing",
                style=pn.style(font_size=15, letter_spacing=2.0),
            ),
            hint("Maestro asserts each labelled line."),
        ),
    )
