"""Demo screen for [`pn.Animated.spring`][pythonnative.Animated.spring].

Springs a box to scale=1.0 from 0.5 and back. Maestro taps "Run
spring" and asserts the status flips to "done" once the spring settles.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def SpringAnimationDemo() -> pn.Element:
    """Render an animated box driven by Animated.spring."""
    scale = pn.use_animated_value(0.5)
    status, set_status = pn.use_state("idle")

    async def run() -> None:
        set_status("running")
        await pn.Animated.spring(scale, to=1.0, stiffness=160, damping=12)
        set_status("done")

    async def reset() -> None:
        set_status("reset")
        await pn.Animated.spring(scale, to=0.5, stiffness=160, damping=12)
        set_status("idle")

    return demo_screen(
        "Animated.spring",
        "Spring a box up to full scale and back.",
        section(
            "Spring demo",
            result_text("Status", status),
            pn.Animated.View(
                pn.Text("spring-box label", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=pn.style(
                    scale=scale,
                    padding=20,
                    background_color="#22C55E",
                    border_radius=12,
                ),
            ),
            buttons_row(
                pn.Button("Run spring", on_click=lambda: pn.run_async(run())),
                pn.Button("Reset", on_click=lambda: pn.run_async(reset())),
            ),
            hint("Maestro taps 'Run spring' and asserts 'Status: done'."),
        ),
    )
