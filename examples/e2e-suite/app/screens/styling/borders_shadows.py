"""Demo screen for borders, border_radius, border_style, and shadows.

A rounded card with a 1px border and a soft shadow, plus dashed and
dotted boxes for the ``border_style`` values added in RFC 0002. The
exact pixel output is platform-specific but the demo asserts each
element renders with its label.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


def _styled_box(label: str, border_style: pn.BorderStyle) -> pn.Element:
    return pn.View(
        pn.Text(label, style=pn.style(font_size=13, font_weight="600")),
        style=pn.style(
            padding=12,
            border_width=2,
            border_style=border_style,
            border_color="#0EA5E9",
            border_radius=6,
            background_color="#FFFFFF",
        ),
    )


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
        section(
            "border_style",
            pn.Row(
                _styled_box("solid-border", "solid"),
                _styled_box("dashed-border", "dashed"),
                _styled_box("dotted-border", "dotted"),
                style=pn.style(spacing=8, flex_wrap="wrap"),
            ),
            hint("Solid, dashed, and dotted borders drawn by every renderer."),
        ),
    )
