"""Demo screen for [`pn.ScrollView`][pythonnative.ScrollView].

Renders a tall column of numbered rows inside a fixed-height scroll
view. Maestro asserts the first row, scrolls, and then asserts a row
that was initially off-screen.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def ScrollViewDemo() -> pn.Element:
    """Render a fixed-height ScrollView with 30 numbered rows."""
    rows = list(range(1, 31))
    return demo_screen(
        "ScrollView",
        "Scroll vertically to reveal rows beyond the visible area.",
        section(
            "Tall content",
            pn.ScrollView(
                pn.Column(
                    *[
                        pn.Text(
                            f"ScrollRow {i}",
                            style=pn.style(font_size=15, padding=8, background_color="#F1F5F9"),
                        )
                        for i in rows
                    ],
                    style=pn.style(spacing=4),
                ),
                style=pn.style(height=200, border_width=1, border_color="#CBD5E1"),
            ),
            hint("Maestro scrolls to reveal a row from later in the list."),
        ),
    )
