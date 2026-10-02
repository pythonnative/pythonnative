"""Demo screen for [`pn.Checkbox`][pythonnative.Checkbox].

Maestro taps the native box directly (via its "Accept" label) to
exercise the platform's toggle event wiring, then drives the same
state through the Check/Uncheck buttons.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def CheckboxDemo() -> pn.Node:
    """Render a Checkbox plus a result line tracking its boolean state."""
    on, set_on = pn.use_state(False)

    return DemoScreen(
        "Checkbox",
        "Toggle the checkbox and the Checked line should flip ON/OFF.",
        DemoSection(
            "Single checkbox",
            ResultText("Checked", "ON" if on else "OFF"),
            pn.Checkbox(value=on, on_change=set_on, label="Accept"),
            ButtonsRow(
                pn.Button("Check", on_press=lambda: set_on(True)),
                pn.Button("Uncheck", on_press=lambda: set_on(False)),
            ),
            Hint("Maestro taps the box itself, then the buttons."),
        ),
    )
