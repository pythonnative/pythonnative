"""Demo screen for [`pn.Dimensions`][pythonnative.Dimensions].

``Dimensions.get("window")`` and ``Dimensions.get("screen")`` return
[`WindowDimensions`][pythonnative.WindowDimensions] records with the size,
``scale``, and ``font_scale``; ``Dimensions.add_listener`` reports a
[`DimensionsEvent`][pythonnative.DimensionsEvent] when either changes. The
exact values vary by device, so the flow asserts the lines are present and
that the readings are positive.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def DimensionsDemo() -> pn.Element:
    """Render window and screen dimensions plus a change counter."""
    changes, set_changes = pn.use_state(0)
    window = pn.Dimensions.get("window")
    screen = pn.Dimensions.get("screen")

    def subscribe():
        def on_change(event: pn.DimensionsEvent) -> None:
            del event
            set_changes(lambda n: n + 1)

        return pn.Dimensions.add_listener(on_change)

    pn.use_effect(subscribe, [])

    return demo_screen(
        "Dimensions",
        "Dimensions.get for the window and screen, plus change events.",
        section(
            "Dimensions module",
            result_text("Window", f"{int(window.width)} x {int(window.height)}"),
            result_text("Screen", f"{int(screen.width)} x {int(screen.height)}"),
            result_text("Window positive", "yes" if window.width > 0 and window.height > 0 else "no"),
            result_text("Screen covers window", "yes" if screen.height >= window.height else "no"),
            result_text("Scale", window.scale),
            result_text("Font scale", window.font_scale),
            result_text("Dimension changes", changes),
            hint("Values vary per device; Maestro asserts the positive flags."),
        ),
    )
