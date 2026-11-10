"""Demo screen for ``entering``, ``exiting``, and ``layout`` ([`MotionProps`][pythonnative.MotionProps]).

Each chip zooms in when it's added, fades out when it's removed, and
slides to its new place (``LinearTransition`` driven by a
[`pn.Spring`][pythonnative.Spring]) when a sibling comes or goes.
Removing a chip unmounts its component at once while the renderer holds
the native view until the exit animation ends, so Maestro waits for the
removed chip's label to disappear. The chips on screen when the demo
opens sit inside a ``LayoutAnimationConfig(skip_entering=True)``, so they
don't animate in with the screen.

Every animation here passes ``reduce_motion="never"``. CI's Android
emulator runs with system animations off, which PythonNative treats as
reduce motion, and this demo needs its animations to still be running
when Maestro checks them.
"""

from __future__ import annotations

from typing import List

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative.motion import FadeOut, LayoutAnimationConfig, LinearTransition, ZoomIn

_ENTER = ZoomIn(duration=250, reduce_motion="never")
_EXIT = FadeOut(duration=200, reduce_motion="never")
_MOVE = LinearTransition(spring=pn.Spring(damping=18, stiffness=180), reduce_motion="never")


@pn.component
def LayoutAnimationsDemo() -> pn.Node:
    """Add and remove chips that animate in, out, and into place."""
    chips, set_chips = pn.use_state([1, 2, 3])
    next_id, set_next_id = pn.use_state(4)
    removed, set_removed = pn.use_state("none")

    def add() -> None:
        set_chips(lambda current: [*current, next_id])
        set_next_id(next_id + 1)

    def remove_first() -> None:
        if chips:
            set_removed(f"Chip {chips[0]}")
            set_chips(chips[1:])

    def chip(chip_id: int) -> pn.Element:
        return pn.View(
            pn.Text(f"Chip {chip_id}", style=pn.style(color="#FFFFFF", font_weight="600")),
            style=pn.style(padding_horizontal=14, padding_vertical=8, border_radius=16, background_color="#2563EB"),
            entering=_ENTER,
            exiting=_EXIT,
            layout=_MOVE,
            key=str(chip_id),
        )

    shown: List[pn.Element] = [chip(chip_id) for chip_id in chips]
    return DemoScreen(
        "Layout animations",
        "Chips zoom in, fade out, and slide into place with entering, exiting, and layout.",
        DemoSection(
            "Chips",
            ResultText("Chips", len(chips)),
            ResultText("Last removed", removed),
            LayoutAnimationConfig(
                *shown,
                skip_entering=True,
                style=pn.style(flex_direction="row", flex_wrap="wrap", gap=8, min_height=40),
            ),
            ButtonsRow(
                pn.Button("Add chip", on_press=add),
                pn.Button("Remove first chip", on_press=remove_first),
            ),
            Hint("Maestro adds 'Chip 4', removes 'Chip 1', and waits for 'Chip 1' to animate away."),
        ),
    )
