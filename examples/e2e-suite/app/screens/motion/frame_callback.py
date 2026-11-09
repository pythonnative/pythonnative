"""Demo screen for [`pn.use_frame_callback`][pythonnative.use_frame_callback].

A worklet runs every display frame while ``active`` is true. It adds the
frame's [`FrameInfo`][pythonnative.FrameInfo] ``delta_ms`` to an
``elapsed`` shared value and turns a dial by it. Python never sees the
frames: "Read elapsed" reads the shared value's latest published value,
and pausing must stop it from advancing.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def FrameCallbackDemo() -> pn.Node:
    """Spin a dial from a frame callback and read the elapsed time from Python."""
    elapsed = pn.use_shared_value(0.0)
    running, set_running = pn.use_state(False)
    advanced, set_advanced = pn.use_state("unknown")
    paused_still, set_paused_still = pn.use_state("unknown")

    @pn.worklet
    def tick(frame: pn.FrameInfo) -> None:
        elapsed.value = elapsed.value + frame.delta_ms

    pn.use_frame_callback(tick, active=running)
    dial = pn.use_animated_style(lambda: {"transform": [{"rotate": (elapsed.value * 0.36) % 360}]})

    def read_elapsed() -> None:
        set_advanced("yes" if elapsed.value > 0 else "no")

    async def check_paused() -> None:
        before = elapsed.value
        await asyncio.sleep(0.3)
        set_paused_still("yes" if elapsed.value == before else "no")

    return DemoScreen(
        "use_frame_callback",
        "A worklet runs every frame while active and accumulates elapsed time.",
        DemoSection(
            "Frame callback",
            ResultText("Frames running", "yes" if running else "no"),
            ResultText("Elapsed advanced", advanced),
            ResultText("Paused stays still", paused_still),
            pn.View(
                pn.View(style=pn.style(width=6, height=36, border_radius=3, background_color="#FFFFFF")),
                style=[
                    pn.style(
                        width=80,
                        height=80,
                        border_radius=40,
                        background_color="#0EA5E9",
                        align_items="center",
                        justify_content="flex_start",
                        padding_top=4,
                    ),
                    dial,
                ],
            ),
            ButtonsRow(
                pn.Button("Start frames", on_press=lambda: set_running(True)),
                pn.Button("Pause frames", on_press=lambda: set_running(False)),
            ),
            ButtonsRow(
                pn.Button("Read elapsed", on_press=read_elapsed),
                pn.Button("Check paused", on_press=check_paused),
            ),
            Hint("Maestro starts frames, reads 'Elapsed advanced: yes', pauses, and checks it holds still."),
        ),
    )
