"""Demo screen for [`pn.use_persisted_state`][pythonnative.use_persisted_state].

Stores an integer counter under a stable key in
[`AsyncStorage`][pythonnative.AsyncStorage]. The persistence aspect
isn't testable in a single Maestro flow (you'd need to relaunch the
app), so the demo focuses on the in-session API: tapping "Bump" must
update the visible value and a "Clear" button must reset it to 0.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UsePersistedStateDemo() -> pn.Element:
    """Render a counter persisted under ``e2e.persisted_demo``."""
    value, set_value = pn.use_persisted_state("e2e.persisted_demo", 0)

    return demo_screen(
        "use_persisted_state",
        "Counter persisted to AsyncStorage; restored on relaunch.",
        section(
            "Counter",
            result_text("Persisted value", value),
            buttons_row(
                pn.Button("Bump", on_press=lambda: set_value(value + 1)),
                pn.Button("Clear", on_press=lambda: set_value(0)),
            ),
            hint("Tap 'Bump' twice; Maestro asserts 'Persisted value: 2'."),
        ),
    )
