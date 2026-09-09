"""Demo screen for [`pn.TextInput`][pythonnative.TextInput].

Maestro types into the name input, checks its echo and selection, then
switches between single-line and multiline widgets without losing the value.
A separate multiline note field shows a live character count.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, label, result_text, section
from app.theme import styles


@pn.component
def TextInputDemo() -> pn.Element:
    """Render a single-line input, a multiline input, and live echoes."""
    name, set_name = pn.use_state("")
    notes, set_notes = pn.use_state("")
    focused, set_focused = pn.use_state(False)
    multiline, set_multiline = pn.use_state(False)
    selection, set_selection = pn.use_state({"start": 0, "end": 0})

    field_style = pn.style(
        padding=10,
        border_radius=6,
        border_width=1,
        border_color="#CBD5E1",
        background_color="#FFFFFF",
        font_size=16,
    )

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
                on_selection_change=set_selection,
                on_focus=lambda: set_focused(True),
                on_blur=lambda: set_focused(False),
                clear_button=True,
                selection_color="#2563EB",
                return_key_type="done",
                auto_correct=False,
                style=field_style,
            ),
            result_text("Echo", name or "(empty)"),
            result_text("Selection", f"{selection['start']}:{selection['end']}"),
            pn.Button(
                "Use single line" if multiline else "Use multiline name", on_press=lambda: set_multiline(not multiline)
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
                style={**field_style, "height": 100},
            ),
            pn.Text(
                f"Length: {len(notes)}",
                style=styles["result"],
            ),
        ),
    )
