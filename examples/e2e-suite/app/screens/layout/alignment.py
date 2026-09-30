"""Demo screen for align_items / justify_content variants.

Three rows demonstrate three different ``align_items`` values, each
with a labelled child so Maestro can confirm the layout pass renders
each variant.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


def _swatch(text: str) -> pn.Element:
    return pn.View(
        pn.Text(text, style=pn.style(color="#FFFFFF")),
        style=pn.style(padding=8, background_color="#0EA5E9"),
    )


@pn.component
def AlignmentDemo() -> pn.Node:
    """Render rows demonstrating three align_items values."""
    return DemoScreen(
        "Alignment",
        "Three rows showing align_items: start, center, end.",
        DemoSection(
            "align_items: start",
            pn.Row(
                _swatch("align-start-a"),
                _swatch("align-start-b"),
                style=pn.style(align_items="flex_start", gap=8, height=80, background_color="#F1F5F9"),
            ),
        ),
        DemoSection(
            "align_items: center",
            pn.Row(
                _swatch("align-center-a"),
                _swatch("align-center-b"),
                style=pn.style(align_items="center", gap=8, height=80, background_color="#F1F5F9"),
            ),
        ),
        DemoSection(
            "align_items: end",
            pn.Row(
                _swatch("align-end-a"),
                _swatch("align-end-b"),
                style=pn.style(align_items="flex_end", gap=8, height=80, background_color="#F1F5F9"),
            ),
            Hint("Each row's children should sit at top, middle, bottom respectively."),
        ),
    )
