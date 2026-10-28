"""Demo screen for [`pn.TouchableOpacity`][pythonnative.TouchableOpacity].

Maestro taps the "Tap me" target and asserts the "Taps" counter
increments on each press, confirming ``on_press`` fires.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def TouchableOpacityDemo() -> pn.Node:
    """Render a TouchableOpacity plus a result line counting presses."""
    taps, set_taps = pn.use_state(0)

    def increment() -> None:
        set_taps(taps + 1)

    return DemoScreen(
        "TouchableOpacity",
        "Tap the target; the Taps counter should increment.",
        DemoSection(
            "Tap target",
            ResultText("Taps", taps),
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
            Hint("Maestro taps 'Tap me' and asserts the Taps count increases."),
        ),
    )
