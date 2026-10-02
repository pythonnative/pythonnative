"""Demo screen for [`pn.Animated.timing`][pythonnative.Animated.timing].

A button fades a labelled box from 0.0 to 1.0 opacity over 300 ms. A
second button resets it. Maestro taps the run button and asserts the
status line flips to "done".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def TimingAnimationDemo() -> pn.Node:
    """Render an animated box driven by Animated.timing."""
    opacity = pn.use_animated_value(0.0)
    status, set_status = pn.use_state("idle")

    async def run() -> None:
        set_status("running")
        await pn.Animated.timing(opacity, to=1.0, duration=300)
        set_status("done")

    async def reset() -> None:
        set_status("reset")
        await pn.Animated.timing(opacity, to=0.0, duration=150)
        set_status("idle")

    return DemoScreen(
        "Animated.timing",
        "Fade a box in/out via Animated.timing and surface the status.",
        DemoSection(
            "Timing demo",
            ResultText("Status", status),
            pn.Animated.View(
                pn.Text("timing-box label", style=pn.style(color="#FFFFFF", font_weight="700")),
                style={
                    "opacity": opacity,
                    "padding": 24,
                    "background_color": "#0EA5E9",
                    "border_radius": 12,
                },
            ),
            ButtonsRow(
                pn.Button("Run timing", on_press=run),
                pn.Button("Reset", on_press=reset),
            ),
            Hint("Maestro taps 'Run timing' and asserts 'Status: done'."),
        ),
    )
