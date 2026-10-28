"""Demo screen for [`pn.use_persisted_state`][pythonnative.use_persisted_state].

Stores an integer counter under a stable key in
[`AsyncStorage`][pythonnative.AsyncStorage]. The persistence aspect
isn't testable in a single Maestro flow (you'd need to relaunch the
app), so the demo focuses on the in-session API: tapping "Bump" must
update the visible value and a "Clear" button must reset it to 0.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UsePersistedStateDemo() -> pn.Node:
    """Render a counter persisted under ``e2e.persisted_demo``."""
    value, set_value = pn.use_persisted_state("e2e.persisted_demo", 0)

    return DemoScreen(
        "use_persisted_state",
        "Counter persisted to AsyncStorage; restored on relaunch.",
        DemoSection(
            "Counter",
            ResultText("Persisted value", value),
            ButtonsRow(
                pn.Button("Bump", on_press=lambda: set_value(lambda current: current + 1)),
                pn.Button("Clear", on_press=lambda: set_value(0)),
            ),
            Hint("Tap 'Bump' twice; Maestro asserts 'Persisted value: 2'."),
        ),
    )
