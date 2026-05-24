"""Demo screen for [`pn.TextInput`][pythonnative.TextInput].

Maestro types into the single-line input and asserts the ``Echo:``
line mirrors the typed value. The multiline variant is also rendered
so flows can confirm both modes coexist on one screen.
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
            pn.TextInput(
                value=name,
                placeholder="Type your name here",
                on_change=set_name,
                return_key_type="done",
                style=field_style,
            ),
            result_text("Echo", name or "(empty)"),
            hint("Maestro types into this field and asserts the echo updates."),
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
