"""Demo screen for [`pn.Svg`][pythonnative.Svg] and [`pn.svg`][pythonnative.svg].

Shapes can be built in Python (``svg.Path``, ``svg.Circle``, ...) or
loaded from an ``.svg`` file under ``app/assets/`` with ``svg.load``.
Maestro asserts the shape count reported by the parser; the drawing
itself isn't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section
from pythonnative import svg

LOGO = pn.asset("vectors/logo.svg")


@pn.component
def SvgDemo() -> pn.Element:
    """Draw shapes declared in Python next to a logo loaded from an asset file."""
    logo = svg.load(LOGO, style=pn.style(width=96, height=96), accessibility_label="svg-logo")
    shape_count = len(logo.props.get("shapes") or ())
    return demo_screen(
        "Svg",
        "Vector shapes drawn in one native view, from Python or from an .svg file.",
        section(
            "Shapes from Python",
            pn.Row(
                pn.Svg(
                    svg.Circle(cx=32, cy=32, r=28, fill="#FDE68A", stroke="#B45309", stroke_width=4),
                    svg.Path(d="M20 36 q12 14 24 0", stroke="#B45309", stroke_width=4, fill="none"),
                    svg.Circle(cx=24, cy=26, r=3, fill="#B45309"),
                    svg.Circle(cx=40, cy=26, r=3, fill="#B45309"),
                    view_box="0 0 64 64",
                    style=pn.style(width=96, height=96),
                ),
                pn.Svg(
                    svg.Rect(x=8, y=8, width=48, height=48, rx=10, fill="#BFDBFE"),
                    svg.Polygon(points="32,14 50,50 14,50", fill="#1D4ED8", opacity=0.85),
                    svg.Line(x1=8, y1=56, x2=56, y2=56, stroke="#1E3A8A", stroke_width=3, stroke_linecap="round"),
                    view_box="0 0 64 64",
                    style=pn.style(width=96, height=96),
                ),
                style=pn.style(spacing=16),
            ),
            hint("Coordinates are in view_box units and scale to the style size."),
        ),
        section(
            "Loaded from app/assets/vectors/logo.svg",
            logo,
            result_text("Parsed shapes", shape_count),
        ),
    )
