"""Demo screen for [`pn.use_back_handler`][pythonnative.use_back_handler].

``use_back_handler`` intercepts the system back action (the Android
hardware back button / predictive back gesture; Escape in the desktop
preview). The demo arms a guard that consumes back presses and counts
them, so a Maestro flow can press device back and assert the screen
did not pop. iOS has no system back button, so there the demo only
verifies that registration is inert.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseBackHandlerDemo() -> pn.Element:
    """Arm a back-press guard and count intercepted presses."""
    armed, set_armed = pn.use_state(False)
    intercepted, set_intercepted = pn.use_state(0)

    def on_back() -> bool:
        if not armed:
            return False
        set_intercepted(lambda n: n + 1)
        return True

    pn.use_back_handler(on_back)

    return demo_screen(
        "use_back_handler",
        "Intercept the system back action while a guard is armed.",
        section(
            "Back guard",
            result_text("Guard armed", "yes" if armed else "no"),
            result_text("Back presses intercepted", intercepted),
            buttons_row(
                pn.Button("Arm guard", on_press=lambda: set_armed(True)),
                pn.Button("Disarm guard", on_press=lambda: set_armed(False)),
            ),
            hint(
                "Android: with the guard armed, the device back button "
                "bumps the counter instead of leaving this screen. "
                "Disarm to restore normal back behavior."
            ),
        ),
    )
