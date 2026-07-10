"""Demo screen for [`pn.DatePicker`][pythonnative.DatePicker].

Maestro taps the "Set 2026-12-25" button and asserts the "Date" line
shows the ISO date string. Driving via a button keeps the flow
deterministic, since native date wheels are hard to script.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def DatePickerDemo() -> pn.Element:
    """Render a DatePicker plus a button that sets a fixed ISO date."""
    value, set_value = pn.use_state("2026-01-01")

    return demo_screen(
        "DatePicker",
        "Set the date via the button; the Date line shows the ISO value.",
        section(
            "Date",
            result_text("Date", value),
            pn.DatePicker(value=value, mode="date", on_change=set_value),
            pn.Button("Set 2026-12-25", on_press=lambda: set_value("2026-12-25")),
            hint("Maestro taps 'Set 2026-12-25' and asserts 'Date: 2026-12-25'."),
        ),
    )
