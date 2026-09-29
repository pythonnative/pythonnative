"""Demo screen for ``Animated.decay``.

A fling starts at a velocity in points per millisecond and decays as
``v0 * deceleration^t``; the projected final value is
``v0 / (1 - deceleration)``, the same on the Python ticker, the Swift
driver, and the Kotlin fling. The awaited
[`AnimationResult`][pythonnative.AnimationResult] reports whether the
fling ran to completion, and the demo checks the settled value against
the closed form so a driver that travels the wrong distance fails here.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_VELOCITY = 1.5  # points per millisecond
_DECELERATION = 0.99
_EXPECTED = _VELOCITY / (1 - _DECELERATION)  # 150 points


@pn.component
def DecayAnimationDemo() -> pn.Element:
    """Fling a box with Animated.decay and check where it settles."""
    tx = pn.use_animated_value(0.0)
    status, set_status = pn.use_state("idle")
    finished, set_finished = pn.use_state("unknown")
    settled, set_settled = pn.use_state("none")

    async def fling() -> None:
        set_status("running")
        tx.set_value(0.0)
        result = await pn.Animated.decay(tx, velocity=_VELOCITY, deceleration=_DECELERATION)
        set_finished("yes" if result.finished else "no")
        final = tx.value
        set_settled(f"{final:.0f}")
        set_status("done" if abs(final - _EXPECTED) <= 3 else "off-target")

    async def reset() -> None:
        set_status("reset")
        await pn.Animated.timing(tx, to=0.0, duration=150)
        set_settled("none")
        set_finished("unknown")
        set_status("idle")

    return demo_screen(
        "Animated.decay",
        "Fling a box and settle at velocity / (1 - deceleration).",
        section(
            "Decay demo",
            result_text("Status", status),
            result_text("Finished", finished),
            result_text("Settled x", settled),
            result_text("Expected x", f"{_EXPECTED:.0f}"),
            pn.Animated.View(
                pn.Text("decay-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=pn.style(
                    translate_x=tx,
                    padding=16,
                    background_color="#F59E0B",
                    border_radius=10,
                    align_self="flex_start",
                ),
            ),
            buttons_row(
                pn.Button("Fling", on_press=lambda: pn.run_async(fling())),
                pn.Button("Reset decay", on_press=lambda: pn.run_async(reset())),
            ),
            hint("Maestro taps 'Fling' and asserts 'Status: done' and 'Finished: yes'."),
        ),
    )
