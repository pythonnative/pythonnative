"""Demo screen for [`pn.Alert.show`][pythonnative.Alert].

Shows a fire-and-forget native alert. Maestro taps the button, waits
for the alert title to appear, then dismisses it via "OK".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def SimpleAlertDemo() -> pn.Element:
    """Render a button that fires a simple ``pn.Alert.show`` alert."""

    def _show() -> None:
        pn.Alert.show("Hello!", "This is a native alert.")

    return demo_screen(
        "Alert.show",
        "Open a native alert dialog; dismiss with OK.",
        section(
            "Alert",
            pn.Button("Show alert", on_click=_show),
            hint("Maestro asserts 'Hello!' appears, then taps 'OK'."),
        ),
    )
