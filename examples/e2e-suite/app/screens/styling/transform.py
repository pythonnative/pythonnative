"""Demo screen for the ``transform`` style.

The ``transform`` style accepts a list of transform specs (translate,
rotate, scale, and the 3D operations added in RFC 0002: ``rotate_x``,
``rotate_y``, ``skew_x`` / ``skew_y``, and ``perspective``). The demo
applies one of each so flows can confirm the element instantiates
without error on every renderer.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


def _box(label: str, color: str, transform: pn.TransformSpec) -> pn.Element:
    return pn.View(
        pn.Text(label, style=pn.style(color="#FFFFFF")),
        style=pn.style(padding=8, background_color=color, transform=transform),
    )


@pn.component
def TransformDemo() -> pn.Node:
    """Render boxes with translate, rotate, scale, and 3D transforms."""
    return DemoScreen(
        "Transforms",
        "Boxes with translate, rotate, and scale transforms.",
        DemoSection(
            "Transformed boxes",
            pn.Row(
                _box("translate", "#0EA5E9", [{"translate_x": 12}]),
                _box("rotate", "#22C55E", [{"rotate": 15.0}]),
                _box("scale", "#F97316", [{"scale": 1.2}]),
                style=pn.style(gap=12, padding=16),
            ),
            Hint("Maestro asserts each of the three transform labels."),
        ),
        DemoSection(
            "3D transforms",
            pn.Row(
                _box("rotate_x", "#8B5CF6", [{"perspective": 400}, {"rotate_x": "30deg"}]),
                _box("rotate_y", "#EC4899", [{"perspective": 400}, {"rotate_y": "-30deg"}]),
                _box("skew", "#14B8A6", [{"skew_x": "12deg"}, {"skew_y": "4deg"}]),
                style=pn.style(gap=12, padding=16),
            ),
            Hint("Perspective, X/Y rotation, and skew compose with the other operations."),
        ),
    )
