"""Demo screen for borders, border_radius, and shadows.

A rounded card with a 1px border and a soft shadow. The exact pixel
output is platform-specific but the demo asserts the element renders
with its label.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def BordersShadowsDemo() -> pn.Element:
    """Render a card with borders, radius, and shadow styling."""
    return demo_screen(
        "Borders & shadows",
        "Card with border, radius, and shadow / elevation.",
        section(
            "Card",
            pn.View(
                pn.Text("border-shadow-card", style=pn.style(font_weight="600", font_size=16)),
                pn.Text(
                    "Inside a card with a soft shadow",
                    style=pn.style(color="#475569", font_size=13),
                ),
                style=pn.style(
                    padding=16,
                    background_color="#FFFFFF",
                    border_radius=12,
                    border_width=1,
                    border_color="#E2E8F0",
                    shadow_color="#000000",
                    shadow_offset={"width": 0, "height": 4},
                    shadow_opacity=0.08,
                    shadow_radius=10,
                    elevation=4,
                    spacing=6,
                ),
            ),
            hint("Maestro asserts the 'border-shadow-card' label."),
        ),
    )
