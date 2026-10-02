"""Demo screen for [`pn.use_transition`][pythonnative.use_transition].

Tapping the button makes an urgent update (the tap counter) and wraps
a second, low-priority update in ``start_transition``. The urgent
counter renders immediately; the transition value catches up on a
later loop turn.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseTransitionDemo() -> pn.Node:
    """Split one tap into an urgent update and a deferred transition."""
    taps, set_taps = pn.use_state(0)
    adopted, set_adopted = pn.use_state(0)
    is_pending, start_transition = pn.use_transition()

    def on_press() -> None:
        next_value = taps + 1
        set_taps(next_value)  # urgent: renders synchronously
        start_transition(lambda: set_adopted(next_value))  # deferred

    return DemoScreen(
        "use_transition",
        "start_transition defers a low-priority update so urgent updates render first.",
        DemoSection(
            "Transition",
            ResultText("Taps", taps),
            ResultText("Adopted", adopted),
            ResultText("Pending", "yes" if is_pending else "no"),
            pn.Button("Tap", on_press=on_press),
            Hint("Maestro taps, then waits for 'Adopted: 1' (the deferred render catching up)."),
        ),
    )
