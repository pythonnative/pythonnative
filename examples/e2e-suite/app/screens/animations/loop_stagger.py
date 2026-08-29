"""Demo screen for ``Animated.loop`` and ``Animated.stagger``.

The loop button pulses a box three times (loop of a two-step timing
sequence) and reports "loop done" when every iteration has finished.
The stagger button fades three chips in with a 120 ms offset between
starts and reports "stagger done".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def LoopStaggerDemo() -> pn.Element:
    """Render loop and stagger runners with awaitable completion."""
    scale = pn.use_animated_value(1.0)
    chip_a = pn.use_animated_value(0.2)
    chip_b = pn.use_animated_value(0.2)
    chip_c = pn.use_animated_value(0.2)
    status, set_status = pn.use_state("idle")

    async def run_loop() -> None:
        set_status("looping")
        await pn.Animated.loop(
            pn.Animated.sequence(
                [
                    pn.Animated.timing(scale, to=1.2, duration=120),
                    pn.Animated.timing(scale, to=1.0, duration=120),
                ]
            ),
            iterations=3,
        )
        set_status("loop done")

    async def run_stagger() -> None:
        set_status("staggering")
        for chip in (chip_a, chip_b, chip_c):
            chip.set_value(0.2)
        await pn.Animated.stagger(
            120,
            [
                pn.Animated.timing(chip_a, to=1.0, duration=150),
                pn.Animated.timing(chip_b, to=1.0, duration=150),
                pn.Animated.timing(chip_c, to=1.0, duration=150),
            ],
        )
        set_status("stagger done")

    def chip(label: str, opacity: pn.AnimatedValue) -> pn.Element:
        return pn.Animated.View(
            pn.Text(label, style=pn.style(color="#FFFFFF", font_weight="700")),
            style=pn.style(
                opacity=opacity,
                background_color="#F59E0B",
                padding=12,
                border_radius=8,
            ),
        )

    return demo_screen(
        "Animated.loop & stagger",
        "Loop a pulse three times, then stagger three chips in.",
        section(
            "Loop & stagger demo",
            result_text("Status", status),
            pn.Animated.View(
                pn.Text("pulse-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=pn.style(
                    transform=[{"scale": scale}],
                    background_color="#8B5CF6",
                    padding=20,
                    border_radius=12,
                    align_self="flex_start",
                ),
            ),
            pn.Row(
                chip("A", chip_a),
                chip("B", chip_b),
                chip("C", chip_c),
                style=pn.style(spacing=8),
            ),
            buttons_row(
                pn.Button("Run loop", on_press=lambda: pn.run_async(run_loop())),
                pn.Button("Run stagger", on_press=lambda: pn.run_async(run_stagger())),
            ),
            hint("Maestro runs both and asserts the status lines."),
        ),
    )
