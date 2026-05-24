"""Demo screen for [`pn.use_focus_effect`][pythonnative.use_focus_effect].

The focus effect bumps a counter every time the screen gains focus.
Maestro pushes another screen on top, pops back, and asserts the
focus counter incremented.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def FocusEffectDemo() -> pn.Element:
    """Render a focus counter bumped by ``use_focus_effect``."""
    focus_count, set_focus_count = pn.use_state(0)
    nav = pn.use_navigation()

    def _on_focus() -> None:
        # ``use_focus_effect`` re-runs every time the screen gains focus,
        # so we don't need a cleanup here.
        set_focus_count(focus_count + 1)

    pn.use_focus_effect(_on_focus, [])

    def push_and_pop_temp() -> None:
        # Navigate to a sibling screen and immediately come back. The
        # "use_state" route exists in the registry and has a back button.
        nav.navigate("use_state")

    return demo_screen(
        "use_focus_effect",
        "Focus counter increments every time the screen comes back into focus.",
        section(
            "Focus",
            result_text("Focus count", focus_count),
            buttons_row(
                pn.Button("Push another screen", on_click=push_and_pop_temp),
            ),
            hint(
                "Push, then tap Back. The focus count should be at least 2 "
                "after returning here (1 on mount, 1 on refocus)."
            ),
        ),
    )
