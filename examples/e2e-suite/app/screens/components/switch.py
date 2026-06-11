"""Demo screen for [`pn.Switch`][pythonnative.Switch].

Maestro toggles the switch via its accessibility label and asserts
the "State:" line flips between ON and OFF.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def SwitchDemo() -> pn.Element:
    """Render a Switch plus a result line tracking its boolean state."""
    on, set_on = pn.use_state(False)

    return demo_screen(
        "Switch",
        "Toggle the switch and the State line should flip ON/OFF.",
        section(
            "Single switch",
            result_text("State", "ON" if on else "OFF"),
            pn.Switch(value=on, on_change=set_on, accessibility_label="Demo switch"),
            buttons_row(
                pn.Button("Turn on", on_click=lambda: set_on(True)),
                pn.Button("Turn off", on_click=lambda: set_on(False)),
            ),
            hint("Maestro taps the switch itself, then the buttons."),
        ),
    )
