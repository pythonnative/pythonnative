"""Demo screen for [`pn.use_state`][pythonnative.use_state].

Most basic hook demo: increment, decrement, reset. Maestro taps
"Increment" twice and asserts the value reaches 2.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseStateDemo() -> pn.Element:
    """Render an int counter driven by use_state."""
    count, set_count = pn.use_state(0)

    return demo_screen(
        "use_state",
        "Counter driven by a single use_state hook.",
        section(
            "Counter",
            result_text("Counter", count),
            buttons_row(
                pn.Button("Increment", on_click=lambda: set_count(count + 1)),
                pn.Button("Decrement", on_click=lambda: set_count(count - 1)),
                pn.Button("Reset", on_click=lambda: set_count(0)),
            ),
            hint("Maestro taps Increment twice, asserts 'Counter: 2'."),
        ),
    )
