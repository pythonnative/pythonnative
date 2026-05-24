"""Demo screen for ``aspect_ratio`` styling.

Two sized boxes whose width is set explicitly; the height is computed
from ``aspect_ratio``. The squares should appear square and the
widescreen should be wider than tall.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def AspectRatioDemo() -> pn.Element:
    """Render a 1:1 square and a 16:9 widescreen box."""
    return demo_screen(
        "Aspect ratio",
        "Width is fixed; height derives from aspect_ratio.",
        section(
            "1:1 + 16:9",
            pn.Row(
                pn.View(
                    pn.Text("aspect-1-1", style=pn.style(color="#FFFFFF")),
                    style=pn.style(
                        width=80,
                        aspect_ratio=1.0,
                        background_color="#0EA5E9",
                        padding=8,
                    ),
                ),
                pn.View(
                    pn.Text("aspect-16-9", style=pn.style(color="#FFFFFF")),
                    style=pn.style(
                        width=160,
                        aspect_ratio=16 / 9,
                        background_color="#22C55E",
                        padding=8,
                    ),
                ),
                style=pn.style(spacing=8),
            ),
            hint("Both labels must be visible; layout passes without crashing."),
        ),
    )
