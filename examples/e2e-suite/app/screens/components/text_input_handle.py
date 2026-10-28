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
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def TextInputHandleDemo() -> pn.Node:
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

    return DemoScreen(
        "TextInputHandle",
        "focus, blur, select, clear, and read a TextInput through ref.current.",
        DemoSection(
            "Handle",
            # The controls sit above the field: the software keyboard covers
            # the lower half of the screen while the field is focused.
            ButtonsRow(
                pn.Button("Focus input", on_press=lambda: call("focus")),
                pn.Button("Blur input", on_press=lambda: call("blur")),
            ),
            ButtonsRow(
                pn.Button("Select all text", on_press=lambda: call("select_all")),
                pn.Button("Select first word", on_press=set_caret),
            ),
            ButtonsRow(
                pn.Button("Read native value", on_press=read_value),
                pn.Button("Clear input", on_press=lambda: call("clear")),
            ),
            ResultText("Handle attached", "yes" if input_ref.current is not None else "no"),
            ResultText("Focused", "ON" if focused else "OFF"),
            ResultText("Last call", last_call),
            ResultText("Native value", native_value),
            ResultText("Selection", f"{selection.start}:{selection.end}"),
            ResultText("Echo", value or "(empty)"),
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
            Hint("Maestro focuses, reads, and clears the field without touching it."),
        ),
    )
