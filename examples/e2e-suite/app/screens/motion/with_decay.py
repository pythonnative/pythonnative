"""Demo screen for [`pn.with_decay`][pythonnative.with_decay].

A fling starts at a velocity in points per second and slows by
``deceleration`` every millisecond, so it travels
``velocity / 1000 / (1 - deceleration)`` points. The demo checks where it
settles against that closed form, so a driver that travels the wrong
distance fails here. A second fling has ``clamp=(0, 100)``: it overshoots
the upper bound and rubber-bands back to it.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_VELOCITY = 300.0  # points per second
_DECELERATION = 0.998
_EXPECTED = _VELOCITY / 1000.0 / (1 - _DECELERATION)  # 150 points
_BOUNDS = (0.0, 100.0)


@pn.component
def WithDecayDemo() -> pn.Node:
    """Fling a box with with_decay and check where it settles."""
    tx = pn.use_shared_value(0.0)
    status, set_status = pn.use_state("idle")
    finished, set_finished = pn.use_state("unknown")
    settled, set_settled = pn.use_state("none")
    slide = pn.use_animated_style(lambda: {"transform": [{"translate_x": tx.value}]})

    async def fling() -> None:
        set_status("running")
        tx.value = 0.0
        done = await tx.animate(pn.with_decay(velocity=_VELOCITY, deceleration=_DECELERATION))
        final = tx.value
        set_finished("yes" if done else "no")
        set_settled(f"{final:.0f}")
        set_status("done" if abs(final - _EXPECTED) <= 3 else "off-target")

    async def fling_clamped() -> None:
        set_status("running")
        tx.value = 0.0
        done = await tx.animate(pn.with_decay(velocity=1000.0, clamp=_BOUNDS))
        final = tx.value
        set_finished("yes" if done else "no")
        set_settled(f"{final:.0f}")
        set_status("done" if abs(final - _BOUNDS[1]) <= 1 else "off-target")

    async def reset() -> None:
        set_status("reset")
        await tx.animate(pn.with_timing(0.0, duration=150))
        set_settled("none")
        set_finished("unknown")
        set_status("idle")

    return DemoScreen(
        "with_decay",
        "Fling a box and settle at velocity / 1000 / (1 - deceleration).",
        DemoSection(
            "Decay demo",
            ResultText("Status", status),
            ResultText("Finished", finished),
            ResultText("Settled x", settled),
            ResultText("Expected x", f"{_EXPECTED:.0f}"),
            pn.View(
                pn.Text("decay-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=[
                    pn.style(padding=16, background_color="#F59E0B", border_radius=10, align_self="flex_start"),
                    slide,
                ],
            ),
            ButtonsRow(
                pn.Button("Fling", on_press=fling),
                pn.Button("Fling clamped", on_press=fling_clamped),
            ),
            ButtonsRow(pn.Button("Reset decay", on_press=reset)),
            Hint("Maestro flings and asserts 'Settled x: 150', then 'Settled x: 100' for the clamped fling."),
        ),
    )
