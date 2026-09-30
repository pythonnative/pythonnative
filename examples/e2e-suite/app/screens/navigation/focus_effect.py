"""Demo screen for [`pn.use_focus_effect`][pythonnative.use_focus_effect].

The focus effect bumps a counter every time the screen gains focus.
Maestro pushes another screen on top, pops back, and asserts the
focus counter incremented.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.hooks.use_state import UseStateDemo
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def FocusEffectDemo() -> pn.Node:
    """Render a focus counter bumped by ``use_focus_effect``."""
    focus_count, set_focus_count = pn.use_state(0)
    nav = pn.use_navigation()

    def _on_focus() -> None:
        # ``use_focus_effect`` re-runs every time the screen gains focus,
        # so we don't need a cleanup here.
        set_focus_count(lambda count: count + 1)

    pn.use_focus_effect(_on_focus, [])

    def push_and_pop_temp() -> None:
        # Navigate to a sibling screen and immediately come back. The
        # use_state demo is a root screen and has a back button.
        nav.navigate(UseStateDemo())

    return DemoScreen(
        "use_focus_effect",
        "Focus counter increments every time the screen comes back into focus.",
        DemoSection(
            "Focus",
            ResultText("Focus count", focus_count),
            ButtonsRow(
                pn.Button("Push another screen", on_press=push_and_pop_temp),
            ),
            Hint(
                "Push, then tap Back. The focus count should be at least 2 "
                "after returning here (1 on mount, 1 on refocus)."
            ),
        ),
    )
