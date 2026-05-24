"""Demo screen for [`pn.ActivityIndicator`][pythonnative.ActivityIndicator].

The indicator animates by default. A button toggles it on/off so flows
can confirm that the ``animating`` prop wires to the underlying
``UIActivityIndicatorView`` / Android ``ProgressBar``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def ActivityIndicatorDemo() -> pn.Element:
    """Render an ActivityIndicator with a toggle button and state readout."""
    spinning, set_spinning = pn.use_state(True)

    return demo_screen(
        "ActivityIndicator",
        "Spinning indicator with a stop/start toggle.",
        section(
            "Indicator",
            result_text("Animating", "yes" if spinning else "no"),
            pn.ActivityIndicator(animating=spinning),
            pn.Button(
                "Stop" if spinning else "Start",
                on_click=lambda: set_spinning(not spinning),
            ),
            hint("Tapping the toggle flips Animating between 'yes' and 'no'."),
        ),
    )
