"""Demo screen for [`pn.with_timing`][pythonnative.with_timing] awaited from Python.

A [`use_shared_value`][pythonnative.use_shared_value] drives a box's
opacity through [`use_animated_style`][pythonnative.use_animated_style].
The run button awaits ``opacity.animate(pn.with_timing(...))``, which
resolves to ``True`` once the core's driver reaches the target, and the
demo mirrors that into the status line. The interrupt button starts a
slow fade and writes a plain value partway through, so the awaited
animation reports ``False``.

Every animation here passes ``reduce_motion="never"``. CI's Android
emulator runs with system animations off, which PythonNative treats as
reduce motion, and this demo needs its animations to still be running
when Maestro checks them.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def WithTimingDemo() -> pn.Node:
    """Fade a box in and out with awaited ``with_timing`` animations."""
    opacity = pn.use_shared_value(0.2)
    status, set_status = pn.use_state("idle")
    finished, set_finished = pn.use_state("unknown")
    fade = pn.use_animated_style(lambda: {"opacity": opacity.value})

    async def run() -> None:
        set_status("running")
        done = await opacity.animate(pn.with_timing(1.0, duration=300, reduce_motion="never"))
        set_finished("yes" if done else "no")
        set_status("done" if done else "interrupted")

    async def interrupt() -> None:
        set_status("running")
        slow = asyncio.ensure_future(opacity.animate(pn.with_timing(0.0, duration=2000, reduce_motion="never")))
        await asyncio.sleep(0.2)
        opacity.value = 0.5
        done = await slow
        set_finished("yes" if done else "no")
        set_status("done" if done else "interrupted")

    async def reset() -> None:
        await opacity.animate(pn.with_timing(0.2, duration=150, easing=pn.Easing.linear, reduce_motion="never"))
        set_finished("unknown")
        set_status("idle")

    return DemoScreen(
        "with_timing",
        "Await a timing animation on a shared value from Python.",
        DemoSection(
            "Timing demo",
            ResultText("Status", status),
            ResultText("Finished", finished),
            pn.View(
                pn.Text("timing-box label", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=[
                    pn.style(padding=24, background_color="#0EA5E9", border_radius=12),
                    fade,
                ],
            ),
            ButtonsRow(
                pn.Button("Run timing", on_press=run),
                pn.Button("Interrupt timing", on_press=interrupt),
            ),
            ButtonsRow(pn.Button("Reset", on_press=reset)),
            Hint("Maestro taps 'Run timing' and asserts 'Status: done' and 'Finished: yes'."),
        ),
    )
