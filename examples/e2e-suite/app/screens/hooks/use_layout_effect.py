"""Demo screen for [`pn.use_layout_effect`][pythonnative.use_layout_effect].

Layout effects run inside the commit, after native mutations and the
layout pass but before passive effects. The demo proves both halves:
it reads a committed frame from a ref inside the layout effect (a
value only available post-layout), and records the phase ordering
against a plain ``use_effect``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseLayoutEffectDemo() -> pn.Node:
    """Measure a box during commit and show effect-phase ordering."""
    box_ref = pn.use_ref(None)
    wide, set_wide = pn.use_state(False)
    measured, set_measured = pn.use_state("pending")
    order, set_order = pn.use_state("pending")

    phases: pn.Ref[list[str]] = pn.use_ref([])

    def on_layout() -> None:
        phases.current.append("layout")
        handle = box_ref.current
        frame = handle.frame if handle is not None else None
        if frame is not None:
            # Setting an equal value is a no-op, so this doesn't loop.
            set_measured(f"{frame.width:.0f}x{frame.height:.0f}")

    def on_passive() -> None:
        phases.current.append("passive")
        set_order(" then ".join(phases.current[-2:]))

    pn.use_layout_effect(on_layout, [wide])
    pn.use_effect(on_passive, [wide])

    return DemoScreen(
        "use_layout_effect",
        "Run an effect inside the commit, before passive effects.",
        DemoSection(
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
            ResultText("Box size", measured),
            ResultText("Phase order", order),
            ButtonsRow(
                pn.Button("Narrow box", on_press=lambda: set_wide(False)),
                pn.Button("Wide box", on_press=lambda: set_wide(True)),
            ),
            Hint(
                "The layout effect reads the committed frame from the ref; "
                "the passive effect always observes 'layout then passive'."
            ),
        ),
    )
