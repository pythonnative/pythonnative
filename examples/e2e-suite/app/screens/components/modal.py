"""Demo screen for [`pn.Modal`][pythonnative.Modal].

A button opens the modal; another button (inside the modal) dismisses
it. Maestro taps "Open modal", asserts the modal's body text appears,
then taps "Close modal" and asserts the body text disappears.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def ModalDemo() -> pn.Element:
    """Render a button that opens a Modal containing a dismiss button."""
    visible, set_visible = pn.use_state(False)
    show_count, set_show_count = pn.use_state(0)

    return demo_screen(
        "Modal",
        "Open the modal, then dismiss it from inside.",
        section(
            "Modal toggle",
            result_text("Modal", "open" if visible else "closed"),
            # ``on_show`` fires once per presentation. We surface its
            # count on the *outer* screen (asserted after the modal
            # closes) because on iOS the presented sheet covers the
            # outer view, so a readout inside the modal can't be checked.
            result_text("Show count", show_count),
            pn.Button("Open modal", on_click=lambda: set_visible(True)),
            hint("Maestro asserts 'Modal body text' appears after tap."),
        ),
        pn.Modal(
            pn.Column(
                pn.Text(
                    "Modal body text",
                    style=pn.style(font_size=18, font_weight="600"),
                ),
                pn.Text(
                    "This content only renders when the modal is visible.",
                    style=pn.style(font_size=13, color="#374151"),
                ),
                pn.Button("Close modal", on_click=lambda: set_visible(False)),
                style=pn.style(spacing=12, padding=20),
            ),
            visible=visible,
            title="Demo modal",
            on_show=lambda: set_show_count(show_count + 1),
            on_dismiss=lambda: set_visible(False),
        ),
    )
