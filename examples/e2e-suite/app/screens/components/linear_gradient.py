"""Demo screen for [`pn.LinearGradient`][pythonnative.LinearGradient].

A gradient is a container: children lay out inside it like a ``View``.
Maestro asserts the labels drawn over the gradients render; the colors
themselves aren't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

LABEL = pn.style(color="#FFFFFF", font_weight="700")


@pn.component
def LinearGradientDemo() -> pn.Element:
    """Render vertical, horizontal, and multi-stop gradients with content on top."""
    return demo_screen(
        "LinearGradient",
        "A container whose background is a linear color gradient.",
        section(
            "Directions",
            pn.Row(
                pn.LinearGradient(
                    pn.Text("Top to bottom", style=LABEL),
                    colors=["#6366F1", "#EC4899"],
                    style=pn.style(
                        width=140, height=90, border_radius=12, align_items="center", justify_content="center"
                    ),
                ),
                pn.LinearGradient(
                    pn.Text("Left to right", style=LABEL),
                    colors=["#0EA5E9", "#22C55E"],
                    start_point=(0, 0),
                    end_point=(1, 0),
                    style=pn.style(
                        width=140, height=90, border_radius=12, align_items="center", justify_content="center"
                    ),
                ),
                style=pn.style(spacing=12),
            ),
        ),
        section(
            "Stops",
            pn.LinearGradient(
                pn.Text("Three colors, weighted stops", style=LABEL),
                colors=["#F59E0B", "#EF4444", "#7C3AED"],
                locations=[0.0, 0.3, 1.0],
                start_point=(0, 0),
                end_point=(1, 1),
                style=pn.style(height=90, border_radius=12, align_items="center", justify_content="center"),
            ),
            hint("locations places each color along the start_point to end_point line."),
        ),
    )
