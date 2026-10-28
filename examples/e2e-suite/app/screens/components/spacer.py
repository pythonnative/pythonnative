"""Demo screen for [`pn.Spacer`][pythonnative.Spacer].

Spacer pushes siblings apart. Two columns of "Top" / "Bottom" text
have a Spacer in between; the demo verifies both ends are visible
without overlap.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


@pn.component
def SpacerDemo() -> pn.Node:
    """Render two text labels separated by an explicit Spacer."""
    return DemoScreen(
        "Spacer",
        "Two labels separated by an explicit Spacer with fixed size.",
        DemoSection(
            "Fixed-size Spacer",
            pn.Column(
                pn.Text("Spacer top label", style=pn.style(font_weight="600")),
                pn.Spacer(size=24),
                pn.Text("Spacer bottom label", style=pn.style(font_weight="600")),
                style=pn.style(gap=0, padding=8, background_color="#FEF3C7", border_radius=8),
            ),
            Hint("Both labels are visible and not overlapping."),
        ),
    )
