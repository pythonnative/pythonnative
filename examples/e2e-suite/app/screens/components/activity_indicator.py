"""Demo screen for [`pn.ActivityIndicator`][pythonnative.ActivityIndicator].

The indicator animates by default. A button toggles it on/off so flows
can confirm that the ``animating`` prop wires to the underlying
``UIActivityIndicatorView`` / Android ``ProgressBar``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def ActivityIndicatorDemo() -> pn.Node:
    """Render an ActivityIndicator with a toggle button and state readout."""
    spinning, set_spinning = pn.use_state(True)

    return DemoScreen(
        "ActivityIndicator",
        "Spinning indicator with a stop/start toggle.",
        DemoSection(
            "Indicator",
            ResultText("Animating", "yes" if spinning else "no"),
            pn.ActivityIndicator(animating=spinning),
            pn.Button(
                "Stop" if spinning else "Start",
                on_press=lambda: set_spinning(not spinning),
            ),
            Hint("Tapping the toggle flips Animating between 'yes' and 'no'."),
        ),
    )
