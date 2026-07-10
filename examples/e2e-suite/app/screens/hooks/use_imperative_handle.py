"""Demo screen for [`pn.use_imperative_handle`][pythonnative.use_imperative_handle].

A composite component that accepts a ``ref`` prop can publish a typed
controller on ``ref.current`` instead of exposing a raw native view.
The demo drives a [`FlatList`][pythonnative.FlatList] through the
[`ListController`][pythonnative.ListController] that the list installs
via ``use_imperative_handle``: buttons outside the list scroll it to
the end and back to the top.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def _Row(item: object = None, index: int = 0) -> pn.Element:
    return pn.Row(
        pn.Text(f"Row {index}", style=pn.style(font_size=15)),
        style=pn.style(padding=12, background_color="#FFFFFF"),
    )


@pn.component
def UseImperativeHandleDemo() -> pn.Element:
    """Scroll a FlatList imperatively through its published controller."""
    list_ref = pn.use_ref(None)
    last_action, set_last_action = pn.use_state("none")

    def scroll_to_end() -> None:
        controller = list_ref.current
        if controller is not None:
            controller.scroll_to_end(animated=False)
            set_last_action("scroll_to_end")

    def scroll_to_top() -> None:
        controller = list_ref.current
        if controller is not None:
            controller.scroll_to_offset(0, animated=False)
            set_last_action("scroll_to_top")

    return demo_screen(
        "use_imperative_handle",
        "Publish a controller on a ref and drive a list imperatively.",
        section(
            "Controller",
            result_text("Handle attached", "yes" if list_ref.current is not None else "no"),
            result_text("Last action", last_action),
            buttons_row(
                pn.Button("Scroll to end", on_press=scroll_to_end),
                pn.Button("Scroll to top", on_press=scroll_to_top),
            ),
            hint("The buttons live outside the list and act through ref.current."),
        ),
        section(
            "List",
            pn.View(
                pn.FlatList(
                    data=list(range(40)),
                    render_item=_Row,
                    item_height=44,
                    ref=list_ref,
                ),
                # Exactly 3 rows tall. Kept small so that on the short
                # Android CI emulator (320x640 dp) the page scroll the
                # flow performs to surface the last row is minimal and
                # the controller buttons stay on screen for the
                # follow-up "Scroll to top" tap.
                style=pn.style(height=132, border_radius=8, overflow="hidden"),
            ),
        ),
    )
