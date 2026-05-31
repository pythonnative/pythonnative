"""Demo screen for [`pn.FlatList`][pythonnative.FlatList].

Renders a virtualized list of 100 rows. Maestro asserts the first
row, scrolls down, and asserts a row further into the list.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def FlatListDemo() -> pn.Element:
    """Render a virtualized 100-row FlatList with stable row labels."""
    items = [{"id": i, "label": f"FlatRow {i + 1}"} for i in range(100)]

    def render_row(item: dict, _: int) -> pn.Element:
        return pn.View(
            pn.Text(item["label"], style=pn.style(font_size=15, font_weight="600")),
            style=pn.style(
                padding=10,
                background_color="#FFFFFF",
                border_radius=6,
            ),
        )

    return demo_screen(
        "FlatList",
        "Virtualized 100-row list; scroll to reveal rows further down.",
        section(
            "List body",
            # See ``components/scroll_view.py`` for the rationale: this
            # is sized so Maestro's screen-center swipe lands inside
            # the FlatList on both the iOS and Android CI emulators.
            pn.FlatList(
                data=items,
                item_height=44,
                separator_height=4,
                render_item=render_row,
                key_extractor=lambda item, _: str(item["id"]),
                style=pn.style(height=400, background_color="#F1F5F9"),
            ),
            hint("Maestro asserts 'FlatRow 1' and (after scroll) 'FlatRow 20'."),
        ),
    )
