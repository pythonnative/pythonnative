"""Demo screen for [`pn.use_reduce_motion`][pythonnative.use_reduce_motion].

The hook mirrors the system Reduce Motion setting and re-renders when it
changes. CI emulators run with the setting off, so the flow asserts
"no"; the demo also shows how an app would shorten an animation when it
is on.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def UseReduceMotionDemo() -> pn.Element:
    """Render the Reduce Motion flag and the animation duration derived from it."""
    reduce_motion = pn.use_reduce_motion()
    duration = 0 if reduce_motion else 300

    return demo_screen(
        "use_reduce_motion",
        "System Reduce Motion setting, returned reactively by the hook.",
        section(
            "Reduce motion",
            result_text("Reduce motion", "yes" if reduce_motion else "no"),
            result_text("Animation duration", duration),
            hint("Maestro asserts 'Reduce motion: no' on the stock emulator."),
        ),
    )
