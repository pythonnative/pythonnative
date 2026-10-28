"""Demo screen for [`pn.Slider`][pythonnative.Slider].

Renders a slider plus helper buttons that snap it to fixed values.
Maestro drags the real slider (it starts at 0.5 so the thumb sits at
the control's center, where an element-anchored swipe begins) and then
uses the buttons for exact-value assertions.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def SliderDemo() -> pn.Node:
    """Render a Slider, snap buttons, and a numeric Value line."""
    value, set_value = pn.use_state(0.5)

    def on_change(new: float) -> None:
        set_value(round(float(new), 2))

    return DemoScreen(
        "Slider",
        "Drag the slider, or tap the buttons to snap to min/max.",
        DemoSection(
            "Slider 0…1",
            ResultText("Value", f"{value:.2f}"),
            pn.Slider(
                value=value,
                min_value=0.0,
                max_value=1.0,
                on_change=on_change,
                accessibility_label="Demo slider",
            ),
            ButtonsRow(
                pn.Button("Set 0.0", on_press=lambda: on_change(0.0)),
                pn.Button("Set 0.5", on_press=lambda: on_change(0.5)),
                pn.Button("Set 1.0", on_press=lambda: on_change(1.0)),
            ),
            Hint("Maestro drags the slider right, then taps the Set buttons."),
        ),
    )
