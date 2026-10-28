"""Demo screen for [`pn.View`][pythonnative.View],
[`pn.Column`][pythonnative.Column], and [`pn.Row`][pythonnative.Row].

The three primitives share a code path but enforce different
``flex_direction`` defaults. The demo renders one of each so Maestro
can confirm they all instantiate and lay children out in the expected
direction.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint
from app.theme import AppStyles

_TILE = pn.style(width=44, height=44, background_color="#34D399", border_radius=8)


@pn.component
def ViewColumnRowDemo() -> pn.Node:
    """Render a Row of three tiles, a Column of three tiles, and a generic View."""
    styles = pn.use_styles(AppStyles)
    return DemoScreen(
        "View / Column / Row",
        "Confirms Row is horizontal, Column is vertical, View is a generic container.",
        DemoSection(
            "Row (flex_direction: row)",
            pn.Row(
                pn.View(pn.Text("A"), style=_TILE),
                pn.View(pn.Text("B"), style=_TILE),
                pn.View(pn.Text("C"), style=_TILE),
                style=pn.style(gap=8),
            ),
            Hint("All three tiles should appear on one horizontal line."),
        ),
        DemoSection(
            "Column (flex_direction: column)",
            pn.Column(
                pn.View(pn.Text("X"), style=_TILE),
                pn.View(pn.Text("Y"), style=_TILE),
                pn.View(pn.Text("Z"), style=_TILE),
                style=pn.style(gap=8),
            ),
            Hint("All three tiles should stack vertically."),
        ),
        DemoSection(
            "Generic View",
            pn.View(
                pn.Text("inside View"),
                style=[styles.card, {"background_color": "#FDE68A"}],
            ),
        ),
    )
