"""Demo screen for [`pn.use_reduce_motion`][pythonnative.use_reduce_motion].

The hook mirrors the system Reduce Motion setting and re-renders when it
changes. The setting differs between CI devices (Android reports it on
when animations are disabled, as CI's emulator runs), so the flow checks
that the hook agrees with ``AccessibilityInfo.is_reduce_motion_enabled()``
rather than a fixed value. The demo also shows how an app would shorten
an animation when the setting is on.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseReduceMotionDemo() -> pn.Node:
    """Render the Reduce Motion flag and the animation duration derived from it."""
    reduce_motion = pn.use_reduce_motion()
    duration = 0 if reduce_motion else 300
    agrees = reduce_motion == pn.AccessibilityInfo.is_reduce_motion_enabled()

    return DemoScreen(
        "use_reduce_motion",
        "System Reduce Motion setting, returned reactively by the hook.",
        DemoSection(
            "Reduce motion",
            ResultText("Reduce motion", "yes" if reduce_motion else "no"),
            ResultText("Animation duration", duration),
            ResultText("Matches AccessibilityInfo", "yes" if agrees else "no"),
            Hint("Maestro checks the hook against AccessibilityInfo on any device."),
        ),
    )
