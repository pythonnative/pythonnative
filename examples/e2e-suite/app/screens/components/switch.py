"""Demo screen for [`pn.Switch`][pythonnative.Switch].

Maestro toggles the switch via its accessibility label and asserts
the "State:" line flips between ON and OFF.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def SwitchDemo() -> pn.Node:
    """Render a Switch plus a result line tracking its boolean state."""
    on, set_on = pn.use_state(False)

    return DemoScreen(
        "Switch",
        "Toggle the switch and the State line should flip ON/OFF.",
        DemoSection(
            "Single switch",
            ResultText("State", "ON" if on else "OFF"),
            pn.Switch(value=on, on_change=set_on, accessibility_label="Demo switch"),
            ButtonsRow(
                pn.Button("Turn on", on_press=lambda: set_on(True)),
                pn.Button("Turn off", on_press=lambda: set_on(False)),
            ),
            Hint("Maestro taps the switch itself, then the buttons."),
        ),
    )
