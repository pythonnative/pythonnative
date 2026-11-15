"""Demo screen for [`pn.StrictMode`][pythonnative.StrictMode].

In development, components under ``StrictMode`` render twice and their
mount effects run, clean up, and run again. The demo counts effect
runs and compares them with what the build mode predicts.
"""

from __future__ import annotations

from typing import Callable, cast

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText
from pythonnative import diagnostics


@pn.component
def Checked(report: Callable[[str], None]) -> pn.Node:
    """Report each effect run and cleanup to the parent."""

    def effect() -> Callable[[], None]:
        report("run")
        return lambda: report("cleanup")

    pn.use_effect(effect, [report])
    return pn.Text("Checked child mounted")


@pn.component
def StrictModeDemo() -> pn.Node:
    """Mount a child under StrictMode and show its effect runs."""
    events: tuple[str, ...]
    events, set_events = pn.use_state(cast(tuple[str, ...], ()))

    def append(event: str) -> None:
        set_events(lambda seen: (*seen, event))

    report = pn.use_callback(append, [])
    runs = events.count("run")
    expected = 2 if diagnostics.is_dev() else 1
    return DemoScreen(
        "StrictMode",
        "StrictMode re-runs bodies and mount effects in development to surface impure code.",
        DemoSection(
            "Mount effects",
            pn.StrictMode(Checked(report)),
            ResultText("Effect runs", runs),
            ResultText("Mode", "development" if diagnostics.is_dev() else "release"),
            ResultText("Matches", "yes" if runs == expected else "no"),
            Hint("Maestro waits for 'Matches: yes'."),
        ),
    )
