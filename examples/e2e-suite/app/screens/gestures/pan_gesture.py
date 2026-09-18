"""Demo screen for ``gestures.Pan`` activation rules and ``enabled``.

The pan target activates only once the horizontal travel crosses
``active_offset_x`` and fails if the vertical travel crosses
``fail_offset_y`` first, so a page scroll never steals it. Every
[`GestureEvent`][pythonnative.gestures.GestureEvent] now carries
``absolute_x`` / ``absolute_y`` (window coordinates) alongside the
view-relative ``x`` / ``y``. A toggle sets ``enabled=False`` on the
descriptor: the gesture keeps its slot but stops delivering events.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section
from pythonnative.gestures import GestureEvent, Pan


@pn.component
def PanGestureDemo() -> pn.Element:
    """Render a pan target with offsets, absolute coordinates, and an enabled toggle."""
    enabled, set_enabled = pn.use_state(True)
    begins, set_begins = pn.use_state(0)
    ends, set_ends = pn.use_state(0)
    translation, set_translation = pn.use_state(0)
    absolute, set_absolute = pn.use_state("none")

    def on_begin(event: GestureEvent) -> None:
        del event
        set_begins(lambda n: n + 1)

    def on_change(event: GestureEvent) -> None:
        set_translation(int(event.translation_x))
        set_absolute("inside window" if event.absolute_x >= 0 and event.absolute_y >= 0 else "outside window")

    def on_end(event: GestureEvent) -> None:
        del event
        set_ends(lambda n: n + 1)

    return demo_screen(
        "Pan gesture",
        "Pan with activation offsets, absolute coordinates, and enabled=False.",
        section(
            # Differs from the box's "Pan target" label: Maestro swipes from
            # the first element matching the text and must find only the box.
            "Pan area",
            result_text("Pan enabled", "yes" if enabled else "no"),
            result_text("Pan begins", begins),
            result_text("Pan ends", ends),
            result_text("Moved left", "yes" if translation < 0 else "no"),
            result_text("Absolute point", absolute),
            pn.View(
                pn.Text("Pan target", style=pn.style(color="#FFFFFF", font_weight="700")),
                gestures=[
                    Pan(
                        enabled=enabled,
                        active_offset_x=(-20, 20),
                        fail_offset_y=(-40, 40),
                        max_pointers=1,
                        on_begin=on_begin,
                        on_change=on_change,
                        on_end=on_end,
                    )
                ],
                style=pn.style(
                    height=120,
                    background_color="#0F766E",
                    border_radius=12,
                    align_items="center",
                    justify_content="center",
                ),
            ),
            buttons_row(
                pn.Button("Disable pan", on_press=lambda: set_enabled(False)),
                pn.Button("Enable pan", on_press=lambda: set_enabled(True)),
            ),
            hint("Swipe left across the target; a disabled pan leaves the counters alone."),
        ),
    )
