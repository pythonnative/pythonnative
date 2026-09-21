"""Demo screen for [`pn.TextInput`][pythonnative.TextInput].

Maestro types into the name input, checks its echo and selection, then
switches between single-line and multiline widgets without losing the value.
A separate multiline note field shows a live character count. The demo also
covers the RFC 0002 additions: the controlled ``selection`` tuple,
``on_key_press`` ([`KeyPressEvent`][pythonnative.KeyPressEvent]),
``select_text_on_focus``, ``keyboard_appearance``, ``blur_on_submit``, and
``on_content_size_change`` ([`ContentSizeEvent`][pythonnative.ContentSizeEvent]).
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, label, result_text, section
from app.theme import styles


@pn.component
def TextInputDemo() -> pn.Element:
    """Render a single-line input, a multiline input, and live echoes."""
    name, set_name = pn.use_state("")
    notes, set_notes = pn.use_state("")
    focused, set_focused = pn.use_state(False)
    multiline, set_multiline = pn.use_state(False)
    selection, set_selection = pn.use_state(pn.SelectionEvent(0, 0))
    # ``None`` leaves the caret alone; a tuple drives the native selection.
    controlled_selection, set_controlled_selection = pn.use_state(None)
    last_key, set_last_key = pn.use_state("(none)")
    content_height, set_content_height = pn.use_state(0)

    field_style = pn.style(
        padding=10,
        border_radius=6,
        border_width=1,
        border_color="#CBD5E1",
        background_color="#FFFFFF",
        font_size=16,
    )

    def on_selection_change(event: pn.SelectionEvent) -> None:
        set_selection(event)
        # Hand the caret back to the user after a programmatic selection.
        set_controlled_selection(None)

    def select_all() -> None:
        # Drive the native selection through the controlled prop and mirror
        # it locally; platforms that echo the change through
        # on_selection_change report the same range.
        set_controlled_selection((0, len(name)))
        set_selection(pn.SelectionEvent(0, len(name)))

    return demo_screen(
        "TextInput",
        "Single-line and multiline text entry with a live echo line.",
        section(
            "Single-line",
            label("Name"),
            result_text("Focused", "ON" if focused else "OFF"),
            pn.TextInput(
                value=name,
                placeholder="Type your name here",
                on_change=set_name,
                multiline=multiline,
                selection=controlled_selection,
                on_selection_change=on_selection_change,
                on_key_press=lambda event: set_last_key(event.key),
                on_focus=lambda: set_focused(True),
                on_blur=lambda: set_focused(False),
                clear_button=True,
                selection_color="#2563EB",
                keyboard_appearance="dark",
                return_key_type="done",
                blur_on_submit=True,
                auto_correct=False,
                style=field_style,
            ),
            result_text("Echo", name or "(empty)"),
            result_text("Selection", f"{selection.start}:{selection.end}"),
            result_text("Last key", last_key),
            buttons_row(
                pn.Button(
                    "Use single line" if multiline else "Use multiline name",
                    on_press=lambda: set_multiline(not multiline),
                ),
                pn.Button("Select all", on_press=select_all),
            ),
            hint("Switch the name field between modes while keeping its text."),
        ),
        section(
            "Multiline",
            label("Notes"),
            pn.TextInput(
                value=notes,
                placeholder="Type a note…",
                on_change=set_notes,
                multiline=True,
                max_length=200,
                select_text_on_focus=True,
                on_content_size_change=lambda event: set_content_height(int(event.height)),
                style={**field_style, "height": 100},
            ),
            pn.Text(
                f"Length: {len(notes)}",
                style=styles["result"],
            ),
            result_text("Content measured", "yes" if content_height > 0 else "no"),
            hint("Focusing the notes field selects its text; typing reports the content size."),
        ),
    )
