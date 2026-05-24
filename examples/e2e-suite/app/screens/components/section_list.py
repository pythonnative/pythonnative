"""Demo screen for [`pn.SectionList`][pythonnative.SectionList].

Two short sections with stable headers and rows; the test mostly
verifies that the section header and the first row of each section
render together.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def SectionListDemo() -> pn.Element:
    """Render a 2-section SectionList using the eager fallback for stability."""
    sections = [
        {
            "title": "Section Alpha",
            "data": [{"name": f"Alpha row {i + 1}"} for i in range(3)],
        },
        {
            "title": "Section Beta",
            "data": [{"name": f"Beta row {i + 1}"} for i in range(3)],
        },
    ]

    def render_item(item: dict, _i: int, _s: int) -> pn.Element:
        return pn.Text(
            item["name"],
            style=pn.style(font_size=14, padding=8, background_color="#FFFFFF"),
        )

    def render_header(s: dict, _i: int) -> pn.Element:
        return pn.Text(
            s["title"],
            style=pn.style(
                font_size=15,
                font_weight="700",
                padding=8,
                background_color="#E2E8F0",
            ),
        )

    return demo_screen(
        "SectionList",
        "Two sections with three rows each.",
        section(
            "Sections",
            pn.SectionList(
                sections=sections,
                render_item=render_item,
                render_section_header=render_header,
                style=pn.style(height=240, background_color="#F1F5F9"),
            ),
            hint("Both section headers and their rows should be visible."),
        ),
    )
