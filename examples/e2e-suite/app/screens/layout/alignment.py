"""Demo screen for align_items / justify_content variants.

Three rows demonstrate three different ``align_items`` values, each
with a labelled child so Maestro can confirm the layout pass renders
each variant.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


def _swatch(text: str) -> pn.Element:
    return pn.View(
        pn.Text(text, style=pn.style(color="#FFFFFF")),
        style=pn.style(padding=8, background_color="#0EA5E9"),
    )


@pn.component
def AlignmentDemo() -> pn.Element:
    """Render rows demonstrating three align_items values."""
    return demo_screen(
        "Alignment",
        "Three rows showing align_items: start, center, end.",
        section(
            "align_items: start",
            pn.Row(
                _swatch("align-start-a"),
                _swatch("align-start-b"),
                style=pn.style(align_items="flex_start", spacing=8, height=80, background_color="#F1F5F9"),
            ),
        ),
        section(
            "align_items: center",
            pn.Row(
                _swatch("align-center-a"),
                _swatch("align-center-b"),
                style=pn.style(align_items="center", spacing=8, height=80, background_color="#F1F5F9"),
            ),
        ),
        section(
            "align_items: end",
            pn.Row(
                _swatch("align-end-a"),
                _swatch("align-end-b"),
                style=pn.style(align_items="flex_end", spacing=8, height=80, background_color="#F1F5F9"),
            ),
            hint("Each row's children should sit at top, middle, bottom respectively."),
        ),
    )
