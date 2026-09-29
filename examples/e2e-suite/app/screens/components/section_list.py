"""Demo screen for [`pn.SectionList`][pythonnative.SectionList].

Two sections with stable headers and rows; the test verifies that the
section header and the first row of each section render together, and
that the ``sticky_section_headers`` native layout keeps a header pinned while
the list is scrolled. Rows are separated by an ``item_separator``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


def _separator() -> pn.Element:
    return pn.View(style=pn.style(height=2, background_color="#E2E8F0"))


@pn.component
def SectionListDemo() -> pn.Element:
    """Render a 2-section SectionList with sticky headers and separators."""
    sections = [
        pn.Section(key="Section Alpha", title="Section Alpha", data=[{"name": f"Alpha row {i + 1}"} for i in range(8)]),
        pn.Section(key="Section Beta", title="Section Beta", data=[{"name": f"Beta row {i + 1}"} for i in range(8)]),
    ]

    def render_item(item: dict, _i: int, _s: int) -> pn.Element:
        return pn.Text(
            item["name"],
            style=pn.style(font_size=14, padding=8, background_color="#FFFFFF"),
        )

    def render_header(s: pn.Section[dict], _i: int) -> pn.Element:
        return pn.Text(
            s.title,
            style=pn.style(
                font_size=15,
                font_weight="700",
                padding=8,
                background_color="#E2E8F0",
            ),
        )

    return demo_screen(
        "SectionList",
        "Two sections with eight rows each and sticky headers.",
        section(
            "Sections",
            pn.SectionList(
                sections=sections,
                render_item=render_item,
                render_section_header=render_header,
                item_height=34,
                section_header_height=36,
                item_separator=_separator,
                sticky_section_headers=True,
                style=pn.style(height=240, background_color="#F1F5F9"),
            ),
            hint("Section Alpha's header stays pinned while its rows scroll under it."),
        ),
    )
