"""Demo screen for [`pn.use_deferred_value`][pythonnative.use_deferred_value].

The counter updates urgently on every tap; the deferred copy adopts
the new value in a transition-priority render one beat later. On a
quiet screen both lines settle to the same number, which is what the
flow asserts.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def UseDeferredValueDemo() -> pn.Element:
    """Show a value and its deferred copy converging after updates."""
    count, set_count = pn.use_state(0)
    deferred = pn.use_deferred_value(count)

    return demo_screen(
        "use_deferred_value",
        "use_deferred_value returns a copy that lags during bursts and catches up when things go quiet.",
        section(
            "Deferred value",
            result_text("Value", count),
            result_text("Deferred", deferred),
            pn.Button("Increment", on_press=lambda: set_count(count + 1)),
            hint("Maestro taps Increment and waits for both 'Value: 1' and 'Deferred: 1'."),
        ),
    )
