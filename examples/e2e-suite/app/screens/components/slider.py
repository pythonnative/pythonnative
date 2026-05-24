"""Demo screen for [`pn.Slider`][pythonnative.Slider].

Renders a slider plus two helper buttons that snap it to the
endpoints. Maestro relies on the buttons (which are easier to drive
than dragging a slider thumb) to exercise ``on_change``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def SliderDemo() -> pn.Element:
    """Render a Slider, two snap buttons, and a numeric Value line."""
    value, set_value = pn.use_state(0.0)

    def on_change(new: float) -> None:
        set_value(round(float(new), 2))

    return demo_screen(
        "Slider",
        "Drag the slider, or tap the buttons to snap to min/max.",
        section(
            "Slider 0…1",
            result_text("Value", f"{value:.2f}"),
            pn.Slider(
                value=value,
                min_value=0.0,
                max_value=1.0,
                on_change=on_change,
            ),
            buttons_row(
                pn.Button("Set 0.0", on_click=lambda: on_change(0.0)),
                pn.Button("Set 0.5", on_click=lambda: on_change(0.5)),
                pn.Button("Set 1.0", on_click=lambda: on_change(1.0)),
            ),
            hint("Maestro taps Set buttons and asserts the Value line."),
        ),
    )
