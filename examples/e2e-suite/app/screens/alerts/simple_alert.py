"""Demo screen for [`pn.Alert.show`][pythonnative.Alert].

Shows a fire-and-forget native alert. Maestro taps the button, waits
for the alert title to appear, then dismisses it via "OK".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


@pn.component
def SimpleAlertDemo() -> pn.Node:
    """Render a button that fires a simple ``pn.Alert.show`` alert."""

    def _show() -> None:
        pn.Alert.show("Hello!", "This is a native alert.")

    return DemoScreen(
        "Alert.show",
        "Open a native alert dialog; dismiss with OK.",
        DemoSection(
            "Alert",
            pn.Button("Show alert", on_press=_show),
            Hint("Maestro asserts 'Hello!' appears, then taps 'OK'."),
        ),
    )
