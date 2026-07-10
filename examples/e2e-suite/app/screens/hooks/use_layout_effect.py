"""Demo screen for [`pn.use_layout_effect`][pythonnative.use_layout_effect].

Layout effects run inside the commit, after native mutations and the
layout pass but before passive effects. The demo proves both halves:
it reads a committed frame from a ref inside the layout effect (a
value only available post-layout), and records the phase ordering
against a plain ``use_effect``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseLayoutEffectDemo() -> pn.Element:
    """Measure a box during commit and show effect-phase ordering."""
    box_ref = pn.use_ref(None)
    wide, set_wide = pn.use_state(False)
    measured, set_measured = pn.use_state("pending")
    order, set_order = pn.use_state("pending")

    phases = pn.use_ref([])

    def on_layout() -> None:
        phases.current.append("layout")
        frame = box_ref._pn_frame
        if frame is not None:
            _x, _y, w, h = frame
            if measured != f"{w:.0f}x{h:.0f}":
                set_measured(f"{w:.0f}x{h:.0f}")

    def on_passive() -> None:
        phases.current.append("passive")
        joined = " then ".join(phases.current[-2:])
        if order != joined:
            set_order(joined)

    pn.use_layout_effect(on_layout, [wide])
    pn.use_effect(on_passive, [wide])

    return demo_screen(
        "use_layout_effect",
        "Run an effect inside the commit, before passive effects.",
        section(
            "Measured frame",
            pn.View(
                ref=box_ref,
                style=pn.style(
                    width=200 if wide else 120,
                    height=48,
                    background_color="#1F6FEB",
                    border_radius=8,
                ),
            ),
            result_text("Box size", measured),
            result_text("Phase order", order),
            buttons_row(
                pn.Button("Narrow box", on_press=lambda: set_wide(False)),
                pn.Button("Wide box", on_press=lambda: set_wide(True)),
            ),
            hint(
                "The layout effect reads the committed frame from the ref; "
                "the passive effect always observes 'layout then passive'."
            ),
        ),
    )
