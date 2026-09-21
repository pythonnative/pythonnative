"""Demo screen for [`pn.FlatList`][pythonnative.FlatList].

Renders a virtualized list of 40 rows. Maestro asserts the first row,
scrolls to the end, and asserts the last row.

UIKit collection views and Android recycler views own physical cells; keyed
Python rows remain in the application tree. The flow scrolls both vertical and
horizontal lists to exercise native recycling and axis-specific measurement,
then switches to an ``inverted`` list that opens at ``initial_scroll_index``.
Every variant renders an ``item_separator`` element between rows.

The flow targets the *last* row because a Maestro fling can travel
several hundred points between visibility polls, skipping clean past
a mid-list row that's only in the accessibility tree while on screen
(rows are recycled natively). The end of the list can't be overshot.
40 rows is still ~5 screenfuls of the list box, so recycling is
genuinely exercised, while keeping the scroll to a handful of swipes.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_MODES = ("vertical", "horizontal", "inverted")


def _separator() -> pn.Element:
    return pn.View(style=pn.style(height=4, width=4, background_color="#CBD5E1"))


@pn.component
def FlatListDemo() -> pn.Element:
    """Render a virtualized 40-row FlatList with stable row labels."""
    mode, set_mode = pn.use_state("vertical")
    items = [{"id": i, "label": f"FlatRow {i + 1}"} for i in range(40)]
    horizontal = mode == "horizontal"
    inverted = mode == "inverted"

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
        "Virtualized 40-row list; scroll vertically and horizontally.",
        section(
            "List body",
            result_text("Mode", mode),
            # See ``components/scroll_view.py`` for the rationale: this
            # is sized so Maestro's screen-center swipe lands inside
            # the FlatList on both the iOS and Android CI emulators.
            pn.FlatList(
                data=items,
                item_height=120 if horizontal else 44,
                horizontal=horizontal,
                inverted=inverted,
                # The inverted variant opens on row 21 so the flow can
                # tell that the initial index was honored.
                initial_scroll_index=20 if inverted else None,
                key=mode,
                item_separator=_separator,
                render_item=render_row,
                key_extractor=lambda item, _: str(item["id"]),
                style=pn.style(height=400, background_color="#F1F5F9"),
            ),
            buttons_row(
                pn.Button("Show horizontal list", on_press=lambda: set_mode("horizontal")),
                pn.Button("Show inverted list", on_press=lambda: set_mode("inverted")),
            ),
            hint("Maestro asserts 'FlatRow 1' and (after scroll) 'FlatRow 40'."),
        ),
    )
