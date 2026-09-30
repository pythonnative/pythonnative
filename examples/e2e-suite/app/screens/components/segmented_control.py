"""Demo screen for [`pn.SegmentedControl`][pythonnative.SegmentedControl].

Maestro taps real segments (their titles are accessible on both
platforms) to exercise the native selection event wiring, then drives
the same state through the Pick buttons.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_SEGMENTS = ["One", "Two", "Three"]


@pn.component
def SegmentedControlDemo() -> pn.Node:
    """Render a SegmentedControl plus selector buttons for deterministic driving."""
    index, set_index = pn.use_state(0)

    return DemoScreen(
        "SegmentedControl",
        "Pick a segment via the control or the buttons.",
        DemoSection(
            "Segments",
            ResultText("Selected", _SEGMENTS[index]),
            pn.SegmentedControl(
                segments=_SEGMENTS,
                selected_index=index,
                on_change=set_index,
            ),
            ButtonsRow(
                pn.Button("Pick One", on_press=lambda: set_index(0)),
                pn.Button("Pick Two", on_press=lambda: set_index(1)),
                pn.Button("Pick Three", on_press=lambda: set_index(2)),
            ),
            Hint("Maestro taps segments directly, then the 'Pick X' buttons."),
        ),
    )
