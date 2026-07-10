"""Demo screen for [`pn.ProgressBar`][pythonnative.ProgressBar].

Three progress bars at 0 / 50 / 100 percent + a state-driven progress
bar paired with two buttons. Maestro taps "Advance" twice and asserts
the percentage line steps up to 50.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def ProgressBarDemo() -> pn.Element:
    """Render static and stateful progress bars with stable labels."""
    progress, set_progress = pn.use_state(0.25)

    def advance() -> None:
        set_progress(min(1.0, round(progress + 0.25, 2)))

    def reset() -> None:
        set_progress(0.0)

    return demo_screen(
        "ProgressBar",
        "Static bars + a stateful bar driven by tap to test value updates.",
        section(
            "Static bars",
            pn.Text("0%"),
            pn.ProgressBar(value=0.0),
            pn.Text("50%"),
            pn.ProgressBar(value=0.5),
            pn.Text("100%"),
            pn.ProgressBar(value=1.0),
        ),
        section(
            "Stateful bar",
            result_text("Progress", f"{int(progress * 100)}%"),
            pn.ProgressBar(value=progress),
            buttons_row(
                pn.Button("Advance", on_press=advance),
                pn.Button("Reset", on_press=reset),
            ),
            hint("Tap 'Advance' to move the bar in 25% steps up to 100%."),
        ),
    )
