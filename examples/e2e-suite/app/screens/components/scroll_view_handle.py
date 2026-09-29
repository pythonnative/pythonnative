"""Demo screen for [`pn.ScrollViewHandle`][pythonnative.ScrollViewHandle].

Passing a ``ref`` to a [`ScrollView`][pythonnative.ScrollView] publishes
a typed handle on ``ref.current``. Buttons outside the box call
``scroll_to_end()``, ``scroll_to(y=...)``, and ``flash_scroll_indicators()``,
and the async ``get_scroll_offset()`` reads the native content offset back
as a [`ScrollOffset`][pythonnative.ScrollOffset].
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def ScrollViewHandleDemo() -> pn.Element:
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

    return demo_screen(
        "ScrollViewHandle",
        "Scroll a ScrollView imperatively through ref.current.",
        section(
            "Handle",
            result_text("Handle attached", "yes" if scroll_ref.current is not None else "no"),
            result_text("Last call", last_call),
            result_text("Offset", offset),
            buttons_row(
                pn.Button("Handle scroll to end", on_press=scroll_to_end),
                pn.Button("Handle scroll to top", on_press=scroll_to_top),
            ),
            buttons_row(
                pn.Button("Read offset", on_press=lambda: pn.run_async(read_offset())),
                pn.Button("Flash indicators", on_press=flash),
            ),
            hint("The buttons live outside the box and act through the handle."),
        ),
        section(
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
                    style=pn.style(spacing=4),
                ),
                ref=scroll_ref,
                # Three rows tall: the flow only needs the first row to
                # leave and the last row to arrive when the handle scrolls.
                style=pn.style(height=132, border_width=1, border_color="#CBD5E1"),
            ),
        ),
    )
