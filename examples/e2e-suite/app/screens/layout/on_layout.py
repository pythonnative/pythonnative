"""Demo screen for the declarative ``on_layout`` prop.

A box reports its laid-out frame through ``on_layout``; a button
toggles the box between two widths, and the measured width readout
updates from the layout callback (not from the style prop), proving
the callback fires with the real computed frame after each layout
pass.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def OnLayoutDemo() -> pn.Element:
    """Render a measurable box whose frame is mirrored via on_layout."""
    wide, set_wide = pn.use_state(False)
    measured, set_measured = pn.use_state("none")

    def handle_layout(payload: dict) -> None:
        set_measured(f"{round(payload['width'])}x{round(payload['height'])}")

    return demo_screen(
        "on_layout",
        "Mirror a box's computed frame through the on_layout callback.",
        section(
            "on_layout demo",
            result_text("Measured", measured),
            pn.View(
                pn.Text("measured-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                on_layout=handle_layout,
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
