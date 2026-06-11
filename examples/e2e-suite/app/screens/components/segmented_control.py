"""Demo screen for [`pn.SegmentedControl`][pythonnative.SegmentedControl].

Maestro taps real segments (their titles are accessible on both
platforms) to exercise the native selection event wiring, then drives
the same state through the Pick buttons.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_SEGMENTS = ["One", "Two", "Three"]


@pn.component
def SegmentedControlDemo() -> pn.Element:
    """Render a SegmentedControl plus selector buttons for deterministic driving."""
    index, set_index = pn.use_state(0)

    return demo_screen(
        "SegmentedControl",
        "Pick a segment via the control or the buttons.",
        section(
            "Segments",
            result_text("Selected", _SEGMENTS[index]),
            pn.SegmentedControl(
                segments=_SEGMENTS,
                selected_index=index,
                on_change=set_index,
            ),
            buttons_row(
                pn.Button("Pick One", on_click=lambda: set_index(0)),
                pn.Button("Pick Two", on_click=lambda: set_index(1)),
                pn.Button("Pick Three", on_click=lambda: set_index(2)),
            ),
            hint("Maestro taps segments directly, then the 'Pick X' buttons."),
        ),
    )
