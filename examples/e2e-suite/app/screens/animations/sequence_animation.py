"""Demo screen for [`pn.Animated.sequence`][pythonnative.Animated.sequence].

Two timing animations chained in sequence (fade in, then fade out).
Maestro taps "Run sequence" and asserts the status flips to "done"
after both complete.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def SequenceAnimationDemo() -> pn.Element:
    """Render a box with sequence (fade in, fade out) animations."""
    opacity = pn.use_animated_value(0.0)
    status, set_status = pn.use_state("idle")

    async def run() -> None:
        set_status("running")
        await pn.Animated.sequence(
            [
                pn.Animated.timing(opacity, to=1.0, duration=200),
                pn.Animated.timing(opacity, to=0.3, duration=200),
            ]
        )
        set_status("done")

    return demo_screen(
        "Animated.sequence",
        "Chain two timings; status flips once the chain finishes.",
        section(
            "Sequence demo",
            result_text("Status", status),
            pn.Animated.View(
                pn.Text("sequence-box label", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=pn.style(
                    opacity=opacity,
                    padding=20,
                    background_color="#7C3AED",
                    border_radius=12,
                ),
            ),
            buttons_row(pn.Button("Run sequence", on_press=lambda: pn.run_async(run()))),
            hint("Maestro taps 'Run sequence' and asserts 'Status: done'."),
        ),
    )
