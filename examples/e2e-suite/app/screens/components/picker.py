"""Demo screen for [`pn.Picker`][pythonnative.Picker].

A simple fruit picker plus a button row that selects each value
programmatically. Maestro opens the real picker (action sheet on iOS,
Spinner dropdown on Android) and picks an option, then uses the
buttons for the programmatic path.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_OPTIONS = [
    {"value": "apple", "label": "Apple"},
    {"value": "banana", "label": "Banana"},
    {"value": "cherry", "label": "Cherry"},
]


@pn.component
def PickerDemo() -> pn.Node:
    """Render a Picker plus selector buttons so flows can drive it deterministically."""
    fruit, set_fruit = pn.use_state("apple")

    return DemoScreen(
        "Picker",
        "Pick a fruit via the wheel or the buttons.",
        DemoSection(
            "Picker",
            ResultText("Picked", fruit),
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
            ButtonsRow(
                pn.Button("Pick apple", on_press=lambda: set_fruit("apple")),
                pn.Button("Pick banana", on_press=lambda: set_fruit("banana")),
                pn.Button("Pick cherry", on_press=lambda: set_fruit("cherry")),
            ),
            Hint("Maestro opens the picker and selects, then taps the buttons."),
        ),
    )
