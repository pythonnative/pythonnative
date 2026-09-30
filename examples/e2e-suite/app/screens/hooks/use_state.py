"""Demo screen for [`pn.use_state`][pythonnative.use_state].

Most basic hook demo: increment, decrement, reset. Maestro taps
"Increment" twice and asserts the value reaches 2.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseStateDemo() -> pn.Node:
    """Render an int counter driven by use_state."""
    count, set_count = pn.use_state(0)

    return DemoScreen(
        "use_state",
        "Counter driven by a single use_state hook.",
        DemoSection(
            "Counter",
            ResultText("Counter", count),
            ButtonsRow(
                pn.Button("Increment", on_press=lambda: set_count(count + 1)),
                pn.Button("Decrement", on_press=lambda: set_count(count - 1)),
                pn.Button("Reset", on_press=lambda: set_count(0)),
            ),
            Hint("Maestro taps Increment twice, asserts 'Counter: 2'."),
        ),
    )
