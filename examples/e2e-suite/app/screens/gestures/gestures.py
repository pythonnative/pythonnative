"""Demo screen for the ``pythonnative.gestures`` system.

One gesture area carries a ``Tap``, a ``LongPress``, and a ``Swipe``
recognizer simultaneously. Each callback bumps a counter (or records
the swipe direction) so Maestro can assert that native recognition
reached Python through the tag-based event channel.

The thresholds are deliberately forgiving (short long-press, low swipe
velocity) so the flow is robust across emulator speeds.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section
from pythonnative import gestures


@pn.component
def GesturesDemo() -> pn.Element:
    """Render a gesture area tracking taps, long presses, and swipes."""
    taps, set_taps = pn.use_state(0)
    presses, set_presses = pn.use_state(0)
    swipe, set_swipe = pn.use_state("none")

    return demo_screen(
        "gestures",
        "Tap, long-press, or swipe the area below.",
        section(
            "Gesture area",
            result_text("Taps", taps),
            result_text("Long presses", presses),
            result_text("Swipe", swipe),
            pn.View(
                # Label deliberately differs from the "Gesture area" section
                # title — Maestro taps by text and must match only the box.
                pn.Text(
                    "Gesture target",
                    style=pn.style(color="#FFFFFF", font_weight="700"),
                ),
                style=pn.style(
                    height=140,
                    background_color="#6366F1",
                    border_radius=12,
                    align_items="center",
                    justify_content="center",
                ),
                gestures=[
                    gestures.Tap(on_tap=lambda e: set_taps(lambda n: n + 1)),
                    gestures.LongPress(
                        on_long_press=lambda e: set_presses(lambda n: n + 1),
                        min_duration_ms=400,
                    ),
                    gestures.Swipe(
                        on_swipe=lambda e: set_swipe(e.direction or "none"),
                        min_velocity=120,
                    ),
                ],
            ),
            hint("Maestro taps, long-presses, then swipes left."),
        ),
    )
