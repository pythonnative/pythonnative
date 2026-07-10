"""Demo screen for [`pn.Alert.confirm`][pythonnative.Alert].

A confirm alert returns a bool. The demo stores the last response and
exposes it on a result line so Maestro can assert "Last response:
confirmed" or "cancelled".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def ConfirmAlertDemo() -> pn.Element:
    """Render a button that fires Alert.confirm; persist the latest response."""
    last, set_last = pn.use_state("(none)")

    async def _run() -> None:
        ok = await pn.Alert.confirm(
            "Confirm action",
            message="Pick Confirm or Cancel.",
            confirm_label="Confirm",
            cancel_label="Cancel",
        )
        set_last("confirmed" if ok else "cancelled")

    return demo_screen(
        "Alert.confirm",
        "Awaitable confirm alert; the response is shown below.",
        section(
            "Confirm",
            result_text("Last response", last),
            buttons_row(
                pn.Button("Show confirm", on_press=lambda: pn.run_async(_run())),
            ),
            hint(
                "Maestro taps 'Show confirm', taps 'Confirm', asserts 'Last response: confirmed'. "
                "Repeat with 'Cancel'."
            ),
        ),
    )
