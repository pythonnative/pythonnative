"""Demo screen for [`pn.TouchableOpacity`][pythonnative.TouchableOpacity].

Maestro taps the "Tap me" target and asserts the "Taps" counter
increments on each press, confirming ``on_press`` fires.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def TouchableOpacityDemo() -> pn.Element:
    """Render a TouchableOpacity plus a result line counting presses."""
    taps, set_taps = pn.use_state(0)

    def increment() -> None:
        set_taps(taps + 1)

    return demo_screen(
        "TouchableOpacity",
        "Tap the target; the Taps counter should increment.",
        section(
            "Tap target",
            result_text("Taps", taps),
            pn.TouchableOpacity(
                pn.Text(
                    "Tap me",
                    style=pn.style(color="#FFFFFF", font_weight="700"),
                ),
                on_press=increment,
                style=pn.style(
                    padding=18,
                    background_color="#0EA5E9",
                    border_radius=12,
                    align_items="center",
                ),
            ),
            hint("Maestro taps 'Tap me' and asserts the Taps count increases."),
        ),
    )
