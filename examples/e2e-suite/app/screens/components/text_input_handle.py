"""Demo screen for [`pn.TextInputHandle`][pythonnative.TextInputHandle].

Passing a ``ref`` to a [`TextInput`][pythonnative.TextInput] publishes a
typed handle on ``ref.current``. Buttons outside the field drive it:
``focus()`` / ``blur()`` flip the focus readout through the real native
focus events, ``select_all()`` and ``set_selection()`` move the caret,
``clear()`` empties the controlled value, and the async ``get_value()``
reads the text back from the native widget.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def TextInputHandleDemo() -> pn.Element:
    """Drive a TextInput through the handle published on its ref."""
    input_ref = pn.use_ref(None)
    value, set_value = pn.use_state("handle text")
    focused, set_focused = pn.use_state(False)
    native_value, set_native_value = pn.use_state("(unread)")
    selection, set_selection = pn.use_state(pn.SelectionEvent(0, 0))
    last_call, set_last_call = pn.use_state("none")

    def call(name: str) -> None:
        handle = input_ref.current
        if handle is None:
            return
        getattr(handle, name)()
        set_last_call(name)

    async def read_value() -> None:
        handle = input_ref.current
        if handle is None:
            return
        set_native_value(await handle.get_value())
        set_last_call("get_value")

    def set_caret() -> None:
        handle = input_ref.current
        if handle is not None:
            handle.set_selection(0, 6)
            set_last_call("set_selection")

    return demo_screen(
        "TextInputHandle",
        "focus, blur, select, clear, and read a TextInput through ref.current.",
        section(
            "Handle",
            # The controls sit above the field: the software keyboard covers
            # the lower half of the screen while the field is focused.
            buttons_row(
                pn.Button("Focus input", on_press=lambda: call("focus")),
                pn.Button("Blur input", on_press=lambda: call("blur")),
            ),
            buttons_row(
                pn.Button("Select all text", on_press=lambda: call("select_all")),
                pn.Button("Select first word", on_press=set_caret),
            ),
            buttons_row(
                pn.Button("Read native value", on_press=lambda: pn.run_async(read_value())),
                pn.Button("Clear input", on_press=lambda: call("clear")),
            ),
            result_text("Handle attached", "yes" if input_ref.current is not None else "no"),
            result_text("Focused", "ON" if focused else "OFF"),
            result_text("Last call", last_call),
            result_text("Native value", native_value),
            result_text("Selection", f"{selection.start}:{selection.end}"),
            result_text("Echo", value or "(empty)"),
            pn.TextInput(
                value=value,
                on_change=set_value,
                on_focus=lambda: set_focused(True),
                on_blur=lambda: set_focused(False),
                on_selection_change=set_selection,
                placeholder="Handle target",
                ref=input_ref,
                style=pn.style(
                    padding=10,
                    border_radius=6,
                    border_width=1,
                    border_color="#CBD5E1",
                    background_color="#FFFFFF",
                    font_size=16,
                ),
            ),
            hint("Maestro focuses, reads, and clears the field without touching it."),
        ),
    )
