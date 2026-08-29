"""Demo screen for gesture composition and ``Fling``.

Three targets exercise the composition combinators from
``pythonnative.gestures``:

- ``Exclusive(double, single)``: the single tap waits for the double
  tap to fail, so a quick double tap reports "double" instead of two
  "single" fires.
- ``Race(long_press, pan)``: whichever recognizer activates first wins
  and the other is cancelled.
- ``Fling``: a directional flick reports the direction it detected.

Each target mirrors its last event into a result line so Maestro can
tap, double-tap, long-press, and swipe to verify arbitration.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section
from pythonnative.gestures import Exclusive, Fling, LongPress, Pan, Race, Tap


@pn.component
def GestureCompositionDemo() -> pn.Element:
    """Render exclusive-tap, race, and fling targets."""
    last_tap, set_last_tap = pn.use_state("none")
    race_winner, set_race_winner = pn.use_state("none")
    fling_result, set_fling_result = pn.use_state("none")

    tap_target = pn.View(
        pn.Text("Tap target", style=pn.style(color="#FFFFFF", font_weight="700")),
        gestures=[
            Exclusive(
                Tap(n_taps=2, on_tap=lambda e: set_last_tap("double")),
                Tap(on_tap=lambda e: set_last_tap("single")),
            )
        ],
        style=pn.style(
            background_color="#0EA5E9",
            padding=24,
            border_radius=12,
            align_items="center",
        ),
    )

    race_target = pn.View(
        pn.Text("Hold or drag target", style=pn.style(color="#FFFFFF", font_weight="700")),
        gestures=[
            Race(
                LongPress(
                    min_duration_ms=400,
                    on_long_press=lambda e: set_race_winner("long_press"),
                ),
                Pan(
                    min_distance=15,
                    on_begin=lambda e: set_race_winner("pan"),
                ),
            )
        ],
        style=pn.style(
            background_color="#8B5CF6",
            padding=24,
            border_radius=12,
            align_items="center",
        ),
    )

    fling_target = pn.View(
        pn.Text("Fling target", style=pn.style(color="#FFFFFF", font_weight="700")),
        gestures=[
            Fling(on_fling=lambda e: set_fling_result(e.direction)),
        ],
        style=pn.style(
            background_color="#F59E0B",
            padding=32,
            border_radius=12,
            align_items="center",
        ),
    )

    return demo_screen(
        "Gesture composition",
        "Exclusive taps, a long-press/pan race, and fling detection.",
        section(
            "Exclusive: double tap beats single",
            result_text("Last tap", last_tap),
            tap_target,
        ),
        section(
            "Race: long press vs pan",
            result_text("Race winner", race_winner),
            race_target,
        ),
        section(
            "Fling",
            result_text("Fling", fling_result),
            fling_target,
            hint("Maestro taps, double-taps, long-presses, and swipes."),
        ),
    )
