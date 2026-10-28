"""Demo screen for [`pn.ScrollViewHandle`][pythonnative.ScrollViewHandle].

Passing a ``ref`` to a [`ScrollView`][pythonnative.ScrollView] publishes
a typed handle on ``ref.current``. Buttons outside the box call
``scroll_to_end()``, ``scroll_to(y=...)``, and ``flash_scroll_indicators()``,
and the async ``get_scroll_offset()`` reads the native content offset back
as a [`ScrollOffset`][pythonnative.ScrollOffset].
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def ScrollViewHandleDemo() -> pn.Node:
    """Drive a ScrollView through the handle published on its ref."""
    scroll_ref = pn.use_ref(None)
    last_call, set_last_call = pn.use_state("none")
    offset, set_offset = pn.use_state("unread")

    def scroll_to_end() -> None:
        handle = scroll_ref.current
        if handle is not None:
            handle.scroll_to_end(animated=False)
            set_last_call("scroll_to_end")

    def scroll_to_top() -> None:
        handle = scroll_ref.current
        if handle is not None:
            handle.scroll_to(y=0, animated=False)
            set_last_call("scroll_to")

    def flash() -> None:
        handle = scroll_ref.current
        if handle is not None:
            handle.flash_scroll_indicators()
            set_last_call("flash_scroll_indicators")

    async def read_offset() -> None:
        handle = scroll_ref.current
        if handle is None:
            return
        current = await handle.get_scroll_offset()
        set_offset("top" if current.y < 1 else "scrolled")
        set_last_call("get_scroll_offset")

    return DemoScreen(
        "ScrollViewHandle",
        "Scroll a ScrollView imperatively through ref.current.",
        DemoSection(
            "Handle",
            ResultText("Handle attached", "yes" if scroll_ref.current is not None else "no"),
            ResultText("Last call", last_call),
            ResultText("Offset", offset),
            ButtonsRow(
                pn.Button("Handle scroll to end", on_press=scroll_to_end),
                pn.Button("Handle scroll to top", on_press=scroll_to_top),
            ),
            ButtonsRow(
                pn.Button("Read offset", on_press=read_offset),
                pn.Button("Flash indicators", on_press=flash),
            ),
            Hint("The buttons live outside the box and act through the handle."),
        ),
        DemoSection(
            "Content",
            pn.ScrollView(
                pn.Column(
                    *[
                        pn.Text(
                            f"HandleRow {i}",
                            style=pn.style(font_size=15, padding=8, background_color="#F1F5F9"),
                        )
                        for i in range(1, 41)
                    ],
                    style=pn.style(gap=4),
                ),
                ref=scroll_ref,
                # Three rows tall: the flow only needs the first row to
                # leave and the last row to arrive when the handle scrolls.
                style=pn.style(height=132, border_width=1, border_color="#CBD5E1"),
            ),
        ),
    )
