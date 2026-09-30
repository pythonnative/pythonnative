"""Demo screen for [`pn.use_reducer`][pythonnative.use_reducer].

A tiny reducer drives a +/-/reset counter. Maestro dispatches each
action via dedicated buttons and asserts the result line.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


def _reducer(state: int, action: str) -> int:
    if action == "inc":
        return state + 1
    if action == "dec":
        return state - 1
    if action == "reset":
        return 0
    return state


@pn.component
def UseReducerDemo() -> pn.Node:
    """Render a 3-action reducer counter."""
    count, dispatch = pn.use_reducer(_reducer, 0)

    return DemoScreen(
        "use_reducer",
        "Counter driven by a reducer with inc / dec / reset actions.",
        DemoSection(
            "Reducer counter",
            ResultText("Counter", count),
            ButtonsRow(
                pn.Button("Dispatch inc", on_press=lambda: dispatch("inc")),
                pn.Button("Dispatch dec", on_press=lambda: dispatch("dec")),
                pn.Button("Dispatch reset", on_press=lambda: dispatch("reset")),
            ),
            Hint("Tap 'Dispatch inc' twice, assert 'Counter: 2'."),
        ),
    )
