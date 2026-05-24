"""Demo screen for the ``transform`` style.

The ``transform`` style accepts a list of transform specs (translate,
rotate, scale). The demo applies one of each so flows can confirm the
element instantiates without error.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def TransformDemo() -> pn.Element:
    """Render boxes with translate, rotate, and scale transforms."""
    return demo_screen(
        "Transforms",
        "Boxes with translate, rotate, and scale transforms.",
        section(
            "Transformed boxes",
            pn.Row(
                pn.View(
                    pn.Text("translate", style=pn.style(color="#FFFFFF")),
                    style=pn.style(
                        padding=8,
                        background_color="#0EA5E9",
                        transform=[{"translate_x": 12}],
                    ),
                ),
                pn.View(
                    pn.Text("rotate", style=pn.style(color="#FFFFFF")),
                    style=pn.style(
                        padding=8,
                        background_color="#22C55E",
                        transform=[{"rotate": 15.0}],
                    ),
                ),
                pn.View(
                    pn.Text("scale", style=pn.style(color="#FFFFFF")),
                    style=pn.style(
                        padding=8,
                        background_color="#F97316",
                        transform=[{"scale": 1.2}],
                    ),
                ),
                style=pn.style(spacing=12, padding=16),
            ),
            hint("Maestro asserts each of the three transform labels."),
        ),
    )
