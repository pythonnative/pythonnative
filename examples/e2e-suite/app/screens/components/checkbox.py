"""Demo screen for [`pn.Checkbox`][pythonnative.Checkbox].

Maestro taps the native box directly (via its "Accept" label) to
exercise the platform's toggle event wiring, then drives the same
state through the Check/Uncheck buttons.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def CheckboxDemo() -> pn.Element:
    """Render a Checkbox plus a result line tracking its boolean state."""
    on, set_on = pn.use_state(False)

    return demo_screen(
        "Checkbox",
        "Toggle the checkbox and the Checked line should flip ON/OFF.",
        section(
            "Single checkbox",
            result_text("Checked", "ON" if on else "OFF"),
            pn.Checkbox(value=on, on_change=set_on, label="Accept"),
            buttons_row(
                pn.Button("Check", on_click=lambda: set_on(True)),
                pn.Button("Uncheck", on_click=lambda: set_on(False)),
            ),
            hint("Maestro taps the box itself, then the buttons."),
        ),
    )
