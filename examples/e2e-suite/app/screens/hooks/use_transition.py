"""Demo screen for [`pn.use_transition`][pythonnative.use_transition].

Tapping the button makes an urgent update (the tap counter) and wraps
a second, low-priority update in ``start_transition``. The urgent
counter renders immediately; the transition value catches up on a
later loop turn.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def UseTransitionDemo() -> pn.Element:
    """Split one tap into an urgent update and a deferred transition."""
    taps, set_taps = pn.use_state(0)
    adopted, set_adopted = pn.use_state(0)
    is_pending, start_transition = pn.use_transition()

    def on_press() -> None:
        next_value = taps + 1
        set_taps(next_value)  # urgent: renders synchronously
        start_transition(lambda: set_adopted(next_value))  # deferred

    return demo_screen(
        "use_transition",
        "start_transition defers a low-priority update so urgent updates render first.",
        section(
            "Transition",
            result_text("Taps", taps),
            result_text("Adopted", adopted),
            result_text("Pending", "yes" if is_pending else "no"),
            pn.Button("Tap", on_press=on_press),
            hint("Maestro taps, then waits for 'Adopted: 1' (the deferred render catching up)."),
        ),
    )
