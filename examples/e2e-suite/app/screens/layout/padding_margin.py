"""Demo screen for padding / margin styling.

Three boxes with different padding and margin values, all wrapped in
a colored parent so the relative spacing is visually obvious.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def PaddingMarginDemo() -> pn.Element:
    """Render padded and margined siblings inside a colored parent."""
    return demo_screen(
        "Padding & margin",
        "Three boxes with different padding / margin values.",
        section(
            "Padding",
            pn.View(
                pn.Text("padding-4", style=pn.style(color="#FFFFFF", padding=4, background_color="#0EA5E9")),
                pn.Text(
                    "padding-12",
                    style=pn.style(color="#FFFFFF", padding=12, background_color="#22C55E"),
                ),
                pn.Text(
                    "padding-24",
                    style=pn.style(color="#FFFFFF", padding=24, background_color="#F97316"),
                ),
                style=pn.style(spacing=8, padding=12, background_color="#E2E8F0", border_radius=8),
            ),
            hint("All three labels must be visible with visibly different padding."),
        ),
        section(
            "Margin",
            pn.Column(
                pn.View(
                    pn.Text("margin-0", style=pn.style(color="#FFFFFF")),
                    style=pn.style(padding=6, background_color="#0EA5E9"),
                ),
                pn.View(
                    pn.Text("margin-12", style=pn.style(color="#FFFFFF")),
                    style=pn.style(padding=6, background_color="#22C55E", margin=12),
                ),
                style=pn.style(spacing=0, background_color="#E2E8F0", border_radius=8),
            ),
        ),
    )
