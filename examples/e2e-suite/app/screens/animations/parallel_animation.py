"""Demo screen for [`pn.Animated.parallel`][pythonnative.Animated.parallel].

Runs a fade + scale in parallel and asserts the status flips to
"done" after both finish.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def ParallelAnimationDemo() -> pn.Node:
    """Render a box with parallel fade + scale animations."""
    opacity = pn.use_animated_value(0.0)
    scale = pn.use_animated_value(0.5)
    status, set_status = pn.use_state("idle")

    async def run() -> None:
        set_status("running")
        await pn.Animated.parallel(
            [
                pn.Animated.timing(opacity, to=1.0, duration=300),
                pn.Animated.spring(scale, to=1.0, stiffness=180, damping=12),
            ]
        )
        set_status("done")

    return DemoScreen(
        "Animated.parallel",
        "Fade + spring concurrently; status flips when both complete.",
        DemoSection(
            "Parallel demo",
            ResultText("Status", status),
            pn.Animated.View(
                pn.Text("parallel-box label", style=pn.style(color="#FFFFFF", font_weight="700")),
                style={
                    "opacity": opacity,
                    "scale": scale,
                    "padding": 20,
                    "background_color": "#F97316",
                    "border_radius": 12,
                },
            ),
            ButtonsRow(pn.Button("Run parallel", on_press=run)),
            Hint("Maestro taps 'Run parallel' and asserts 'Status: done'."),
        ),
    )
