"""Demo screen for a [`@pn.worklet`][pythonnative.worklet] Pan that keeps tracking while Python is busy.

The card's ``Pan`` callbacks are worklets: the core runs them on the UI
thread, so the drag, the snap decision
([`snap_point`][pythonnative.snap_point]), and the spring never wait on
Python. A [`use_derived_value`][pythonnative.use_derived_value] tilts the
card as it travels.

"Block Python" sets a ``busy`` shared value and then spins the Python
thread in a blocking loop for :data:`BLOCK_SECONDS`. A drag during that
window still follows the finger and snaps. The release worklet reads
``busy`` and reports the side it snapped to with
[`run_on_python`][pythonnative.run_on_python]; the call is queued and
runs once Python is free, so "Released while busy: yes" proves the
release ran on the UI thread while Python couldn't.
"""

from __future__ import annotations

import asyncio
import time

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative import gestures

BLOCK_SECONDS = 4.0
"""How long "Block Python" holds the Python thread (tests shorten it)."""

TRACK = 160.0
"""Distance from the left detent to the right one, in points."""


def _hold_python(seconds: float) -> None:
    """Spin the Python thread without yielding, like a heavy decode or import would."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        pass


@pn.component
def DragUnderLoadDemo() -> pn.Node:
    """Render a draggable card that snaps left or right on the UI thread."""
    x = pn.use_shared_value(0.0)
    start = pn.use_shared_value(0.0)
    busy = pn.use_shared_value(False)
    tilt = pn.use_derived_value(lambda: pn.interpolate(x.value, (0, TRACK), (0, 6), "clamp"))
    python_busy, set_python_busy = pn.use_state("no")
    blocks, set_blocks = pn.use_state(0)
    side, set_side = pn.use_state("left")
    releases, set_releases = pn.use_state(0)
    while_busy, set_while_busy = pn.use_state("unknown")

    def released(snapped: str, during_block: bool) -> None:
        set_side(snapped)
        set_releases(lambda n: n + 1)
        set_while_busy("yes" if during_block else "no")

    @pn.worklet
    def begin(event: gestures.GestureEvent) -> None:
        start.value = x.value

    @pn.worklet
    def drag(event: gestures.GestureEvent) -> None:
        x.value = pn.clamp(start.value + event.translation_x, -24, TRACK + 24)

    @pn.worklet
    def release(event: gestures.GestureEvent) -> None:
        target = pn.snap_point(x.value, event.velocity_x, (0.0, TRACK))
        x.value = pn.with_spring(target, velocity=event.velocity_x, damping=20, stiffness=220)
        pn.run_on_python(released, "right" if target > 0 else "left", busy.value)

    moved = pn.use_animated_style(lambda: {"transform": [{"translate_x": x.value}, {"rotate": tilt.value}]})

    async def block() -> None:
        busy.value = True
        set_python_busy("yes")
        # Let the busy flag and the readout reach the UI thread before blocking.
        await asyncio.sleep(0.25)
        _hold_python(BLOCK_SECONDS)
        busy.value = False
        set_python_busy("no")
        set_blocks(lambda n: n + 1)

    def recenter() -> None:
        x.value = pn.with_spring(0.0)
        set_side("left")

    return DemoScreen(
        "Drag under load",
        "A worklet Pan keeps tracking and snapping while the Python thread is blocked.",
        DemoSection(
            "Drag the card",
            ResultText("Python busy", python_busy),
            ResultText("Blocks", blocks),
            ResultText("Side", side),
            ResultText("Releases", releases),
            ResultText("Released while busy", while_busy),
            pn.View(
                pn.View(
                    pn.Text("Drag me", style=pn.style(color="#FFFFFF", font_weight="700")),
                    gestures=[gestures.Pan(active_offset_x=(-10, 10), on_begin=begin, on_change=drag, on_end=release)],
                    style=[
                        pn.style(
                            width=120,
                            height=80,
                            border_radius=12,
                            background_color="#0F766E",
                            align_items="center",
                            justify_content="center",
                        ),
                        moved,
                    ],
                    accessibility_label="Drag card",
                ),
                style=pn.style(height=96, justify_content="center", background_color="#E2E8F0", border_radius=12),
            ),
            ButtonsRow(
                pn.Button("Block Python", on_press=block),
                pn.Button("Recenter card", on_press=recenter),
            ),
            Hint("Maestro blocks Python, swipes the card right during the block, and asserts the release snapped."),
        ),
    )
