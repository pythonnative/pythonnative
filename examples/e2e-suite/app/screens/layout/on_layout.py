"""Demo screen for the declarative ``on_layout`` prop.

A box reports its laid-out frame through ``on_layout`` as a
[`LayoutEvent`][pythonnative.LayoutEvent]; a button toggles the box
between two widths, and the measured width readout updates from the
layout callback (not from the style prop), proving the callback fires
with the real computed frame after each layout pass. The same box
carries a ``ref`` so the demo can read the last committed frame back
from its [`ViewHandle`][pythonnative.ViewHandle].
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def OnLayoutDemo() -> pn.Element:
    """Render a measurable box whose frame is mirrored via on_layout."""
    wide, set_wide = pn.use_state(False)
    measured, set_measured = pn.use_state("none")
    handle_frame, set_handle_frame = pn.use_state("none")
    box_ref = pn.use_ref(None)

    def handle_layout(event: pn.LayoutEvent) -> None:
        set_measured(f"{round(event.width)}x{round(event.height)}")
        handle = box_ref.current
        frame = handle.frame if handle is not None else None
        if frame is not None:
            set_handle_frame(f"{round(frame.width)}x{round(frame.height)}")

    return demo_screen(
        "on_layout",
        "Mirror a box's computed frame through the on_layout callback.",
        section(
            "on_layout demo",
            result_text("Measured", measured),
            result_text("Handle frame", handle_frame),
            pn.View(
                pn.Text("measured-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                on_layout=handle_layout,
                ref=box_ref,
                style=pn.style(
                    width=200 if wide else 120,
                    height=60,
                    background_color="#10B981",
                    border_radius=8,
                    align_items="center",
                    justify_content="center",
                ),
            ),
            buttons_row(
                pn.Button("Widen box", on_press=lambda: set_wide(True)),
                pn.Button("Shrink box", on_press=lambda: set_wide(False)),
            ),
            hint("Maestro widens the box and asserts 'Measured: 200x60'."),
        ),
    )
