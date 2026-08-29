"""Demo screen for [`AnimatedNode.interpolate`][pythonnative.animated.AnimatedNode.interpolate].

One driver value animates 0 to 1; an interpolation maps it onto a
120-point horizontal shift, a color interpolation crossfades the box
from indigo to emerald, and an arithmetic node (``driver * 0.5 + 0.5``)
drives opacity. The status line flips to "done" when the timing
completes, and the shift readout shows the interpolated output so
Maestro can assert the derived math.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def InterpolateAnimationDemo() -> pn.Element:
    """Render a box driven by interpolated and derived animated nodes."""
    driver = pn.use_animated_value(0.0)
    status, set_status = pn.use_state("idle")

    shift = driver.interpolate([0.0, 1.0], [0.0, 120.0])
    tint = driver.interpolate([0.0, 1.0], ["#6366F1", "#10B981"])
    opacity = driver * 0.5 + 0.5

    async def run() -> None:
        set_status("running")
        await pn.Animated.timing(driver, to=1.0, duration=400)
        set_status("done")

    async def reset() -> None:
        set_status("reset")
        await pn.Animated.timing(driver, to=0.0, duration=200)
        set_status("idle")

    return demo_screen(
        "Animated.interpolate",
        "Interpolate one driver into a shift, a color, and an opacity.",
        section(
            "Interpolate demo",
            result_text("Status", status),
            result_text("Shift", round(float(shift))),
            pn.Animated.View(
                pn.Text("interpolate-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=pn.style(
                    opacity=opacity,
                    background_color=tint,
                    transform=[{"translate_x": shift}],
                    padding=24,
                    border_radius=12,
                    align_self="flex_start",
                ),
            ),
            buttons_row(
                pn.Button("Run interpolate", on_press=lambda: pn.run_async(run())),
                pn.Button("Reset", on_press=lambda: pn.run_async(reset())),
            ),
            hint("Maestro taps 'Run interpolate' and asserts 'Shift: 120'."),
        ),
    )
