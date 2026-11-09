"""Demo screen for [`pn.Swipeable`][pythonnative.Swipeable] and its [`SwipeableHandle`][pythonnative.SwipeableHandle].

The row slides left to reveal a "Delete" action and right to reveal a
"Pin" action. The pan, the open-or-close decision, and the spring run as
worklets on the UI thread; ``on_open`` and ``on_close`` report where the
row settled after a drag. The buttons below drive the handle
(``open_left``, ``open_right``, ``close``), and "Last request" records
each call.
"""

from __future__ import annotations

from typing import Any

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_ACTION = pn.style(flex_grow=1, align_items="center", justify_content="center")


@pn.component
def SwipeableDemo() -> pn.Node:
    """Render a swipeable row with actions on both sides."""
    row = pn.use_ref(None)
    opened, set_opened = pn.use_state("none")
    closes, set_closes = pn.use_state(0)
    actions, set_actions = pn.use_state("none")
    request, set_request = pn.use_state("none")

    def call(name: str) -> None:
        handle: Any = row.current
        set_request(name)
        if name == "open_left":
            handle.open_left()
        elif name == "open_right":
            handle.open_right()
        else:
            handle.close()

    return DemoScreen(
        "Swipeable",
        "Swipe the row left or right to reveal its actions.",
        DemoSection(
            "Swipeable row",
            ResultText("Opened", opened),
            ResultText("Closes", closes),
            ResultText("Action", actions),
            ResultText("Last request", request),
            pn.Swipeable(
                pn.View(
                    pn.Text("Swipe this row", style=pn.style(font_size=16, font_weight="600")),
                    style=pn.style(height=56, padding_horizontal=16, justify_content="center"),
                ),
                left_actions=pn.Pressable(
                    pn.Text("Pin", style=pn.style(color="#FFFFFF", font_weight="700")),
                    on_press=lambda: set_actions("pin"),
                    style=[_ACTION, {"background_color": "#2563EB"}],
                ),
                right_actions=pn.Pressable(
                    pn.Text("Delete", style=pn.style(color="#FFFFFF", font_weight="700")),
                    on_press=lambda: set_actions("delete"),
                    style=[_ACTION, {"background_color": "#DC2626"}],
                ),
                on_open=set_opened,
                on_close=lambda: set_closes(lambda n: n + 1),
                ref=row,
                style=pn.style(border_width=1, border_color="#CBD5E1", border_radius=8),
            ),
            ButtonsRow(
                pn.Button("Open left via ref", on_press=lambda: call("open_left")),
                pn.Button("Close via ref", on_press=lambda: call("close")),
            ),
            Hint("Maestro swipes the row left, taps 'Delete', and asserts 'Opened: right' and 'Action: delete'."),
        ),
    )
