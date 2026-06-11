"""Demo screen for [`pn.Picker`][pythonnative.Picker].

A simple fruit picker plus a button row that selects each value
programmatically. Maestro opens the real picker (action sheet on iOS,
Spinner dropdown on Android) and picks an option, then uses the
buttons for the programmatic path.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_OPTIONS = [
    {"value": "apple", "label": "Apple"},
    {"value": "banana", "label": "Banana"},
    {"value": "cherry", "label": "Cherry"},
]


@pn.component
def PickerDemo() -> pn.Element:
    """Render a Picker plus selector buttons so flows can drive it deterministically."""
    fruit, set_fruit = pn.use_state("apple")

    return demo_screen(
        "Picker",
        "Pick a fruit via the wheel or the buttons.",
        section(
            "Picker",
            result_text("Picked", fruit),
            pn.Picker(
                value=fruit,
                items=_OPTIONS,
                on_change=set_fruit,
                style=pn.style(
                    padding=10,
                    border_radius=6,
                    border_width=1,
                    border_color="#CBD5E1",
                    background_color="#FFFFFF",
                ),
            ),
            buttons_row(
                pn.Button("Pick apple", on_click=lambda: set_fruit("apple")),
                pn.Button("Pick banana", on_click=lambda: set_fruit("banana")),
                pn.Button("Pick cherry", on_click=lambda: set_fruit("cherry")),
            ),
            hint("Maestro opens the picker and selects, then taps the buttons."),
        ),
    )
