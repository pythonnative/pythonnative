"""Demo screen for composed animations.

It covers [`pn.with_sequence`][pythonnative.with_sequence],
[`pn.with_delay`][pythonnative.with_delay], and
[`pn.with_repeat`][pythonnative.with_repeat]:

- The sequence pops a box up and, after a delay, back down; Python awaits
  the whole composition.
- The repeat pulses a box's opacity four times with ``reverse=True``. Its
  ``on_finish`` worklet runs on the UI thread and reports back with
  [`run_on_python`][pythonnative.run_on_python].
- The loop spins a box forever (``times=None``) until ``cancel()`` stops
  it where it is.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_BOX = pn.style(padding=16, border_radius=10, align_self="flex_start")
_LABEL = pn.style(color="#FFFFFF", font_weight="700")


@pn.component
def CompositionDemo() -> pn.Node:
    """Compose animations and report when each finishes."""
    pop = pn.use_shared_value(1.0)
    pulse = pn.use_shared_value(1.0)
    spin = pn.use_shared_value(0.0)
    sequence, set_sequence = pn.use_state("idle")
    repeat, set_repeat = pn.use_state("idle")
    loop, set_loop = pn.use_state("stopped")
    loop_moved, set_loop_moved = pn.use_state("unknown")

    pop_style = pn.use_animated_style(lambda: {"transform": [{"scale": pop.value}]})
    pulse_style = pn.use_animated_style(lambda: {"opacity": pulse.value})
    spin_style = pn.use_animated_style(lambda: {"transform": [{"rotate": spin.value}]})

    def repeat_finished(outcome: str) -> None:
        set_repeat(outcome)

    @pn.worklet
    def repeat_done(finished: bool) -> None:
        pn.run_on_python(repeat_finished, "finished" if finished else "interrupted")

    async def run_sequence() -> None:
        set_sequence("running")
        done = await pop.animate(
            pn.with_sequence(
                pn.with_timing(1.3, duration=150),
                pn.with_delay(100, pn.with_timing(1.0, duration=150)),
            )
        )
        set_sequence("done" if done else "interrupted")

    def run_repeat() -> None:
        set_repeat("running")
        pulse.value = pn.with_repeat(pn.with_timing(0.2, duration=100), times=4, reverse=True, on_finish=repeat_done)

    def start_loop() -> None:
        set_loop("running")
        set_loop_moved("unknown")
        spin.value = pn.with_repeat(pn.with_timing(360.0, duration=900, easing=pn.Easing.linear))

    def stop_loop() -> None:
        spin.cancel()
        set_loop("stopped")
        set_loop_moved("yes" if spin.value > 0 else "no")

    return DemoScreen(
        "Sequence, repeat, delay",
        "Compose animations with with_sequence, with_delay, and with_repeat.",
        DemoSection(
            "Sequence with a delay",
            ResultText("Sequence", sequence),
            pn.View(pn.Text("pop-box", style=_LABEL), style=[_BOX, {"background_color": "#EC4899"}, pop_style]),
            ButtonsRow(pn.Button("Run sequence", on_press=run_sequence)),
        ),
        DemoSection(
            "Repeat with on_finish",
            ResultText("Repeat", repeat),
            pn.View(pn.Text("pulse-box", style=_LABEL), style=[_BOX, {"background_color": "#6366F1"}, pulse_style]),
            ButtonsRow(pn.Button("Run repeat", on_press=run_repeat)),
        ),
        DemoSection(
            "Repeat forever",
            ResultText("Loop", loop),
            ResultText("Loop moved", loop_moved),
            pn.View(pn.Text("spin-box", style=_LABEL), style=[_BOX, {"background_color": "#14B8A6"}, spin_style]),
            ButtonsRow(
                pn.Button("Start loop", on_press=start_loop),
                pn.Button("Stop loop", on_press=stop_loop),
            ),
            Hint("Maestro asserts 'Sequence: done', 'Repeat: finished', and 'Loop moved: yes'."),
        ),
    )
