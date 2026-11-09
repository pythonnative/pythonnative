"""Demo screen for ``item_entering``, ``item_exiting``, and ``item_layout`` on [`pn.FlatList`][pythonnative.FlatList].

A native list owns its rows, so it animates dataset changes itself:
a new row slides in from the right, a removed one fades out, and the
rows around them move into place. Recycling and scrolling never trigger
these animations, only changes to ``data``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative.motion import FadeOut, LinearTransition, SlideIn


@pn.component
def ListItemAnimationsDemo() -> pn.Node:
    """Insert and remove rows at the top of a FlatList."""
    rows, set_rows = pn.use_state([5, 4, 3, 2, 1])

    def add_row() -> None:
        set_rows(lambda current: [max(current, default=0) + 1, *current])

    def remove_top() -> None:
        set_rows(lambda current: current[1:])

    def render_row(item: int, _index: int) -> pn.Element:
        return pn.View(
            pn.Text(f"ItemRow {item}", style=pn.style(font_size=15, font_weight="600")),
            style=pn.style(padding=10, background_color="#FFFFFF", border_radius=6),
        )

    return DemoScreen(
        "List item animations",
        "FlatList rows slide in, fade out, and move with item_entering, item_exiting, and item_layout.",
        DemoSection(
            "Animated list",
            ResultText("Rows", len(rows)),
            ResultText("Top row", f"ItemRow {rows[0]}" if rows else "none"),
            pn.FlatList(
                data=rows,
                render_item=render_row,
                key_extractor=lambda item, _index: str(item),
                item_height=44,
                item_entering=SlideIn(edge="right", duration=250),
                item_exiting=FadeOut(duration=200),
                item_layout=LinearTransition(duration=250),
                style=pn.style(height=300, background_color="#F1F5F9"),
            ),
            ButtonsRow(
                pn.Button("Add row", on_press=add_row),
                pn.Button("Remove top row", on_press=remove_top),
            ),
            Hint("Maestro adds 'ItemRow 6', removes it again, and waits for it to fade out."),
        ),
    )
