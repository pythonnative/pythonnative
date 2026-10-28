"""Demo screen for ``position: "absolute"`` styling.

A dark canvas with four pinned corner labels and a centered label
using percentage offsets. All five labels must be visible.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint

_PIN = pn.style(
    position="absolute",
    background_color="#FBBF24",
    padding=4,
)


@pn.component
def AbsolutePositionDemo() -> pn.Node:
    """Render five absolutely-positioned labels on a dark canvas."""
    return DemoScreen(
        "Absolute positioning",
        "Four corner labels and a centered label pinned absolutely.",
        DemoSection(
            "Canvas",
            pn.View(
                pn.View(pn.Text("abs-top-left"), style={**_PIN, "top": 4, "left": 4}),
                pn.View(pn.Text("abs-top-right"), style={**_PIN, "top": 4, "right": 4}),
                pn.View(pn.Text("abs-bottom-left"), style={**_PIN, "bottom": 4, "left": 4}),
                pn.View(pn.Text("abs-bottom-right"), style={**_PIN, "bottom": 4, "right": 4}),
                pn.View(
                    pn.Text("abs-center"),
                    style={**_PIN, "left": "30%", "right": "30%", "top": "40%"},
                ),
                style=pn.style(
                    height=180,
                    background_color="#1E293B",
                    border_radius=8,
                ),
            ),
            Hint("Maestro asserts each of the five labels."),
        ),
    )
