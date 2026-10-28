"""Demo screen for [`pn.ProgressBar`][pythonnative.ProgressBar].

Three progress bars at 0 / 50 / 100 percent + a state-driven progress
bar paired with two buttons. Maestro taps "Advance" twice and asserts
the percentage line steps up to 50.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def ProgressBarDemo() -> pn.Node:
    """Render static and stateful progress bars with stable labels."""
    progress, set_progress = pn.use_state(0.25)

    def advance() -> None:
        set_progress(min(1.0, round(progress + 0.25, 2)))

    def reset() -> None:
        set_progress(0.0)

    return DemoScreen(
        "ProgressBar",
        "Static bars + a stateful bar driven by tap to test value updates.",
        DemoSection(
            "Static bars",
            pn.Text("0%"),
            pn.ProgressBar(value=0.0),
            pn.Text("50%"),
            pn.ProgressBar(value=0.5),
            pn.Text("100%"),
            pn.ProgressBar(value=1.0),
        ),
        DemoSection(
            "Stateful bar",
            ResultText("Progress", f"{int(progress * 100)}%"),
            pn.ProgressBar(value=progress),
            ButtonsRow(
                pn.Button("Advance", on_press=advance),
                pn.Button("Reset", on_press=reset),
            ),
            Hint("Tap 'Advance' to move the bar in 25% steps up to 100%."),
        ),
    )
