"""Demo screen for [`pn.Button`][pythonnative.Button].

Exposes an "Increment" button that drives a counter so flows can tap
it twice and assert ``"Counter: 2"``. Also includes a disabled-button
variant whose ``on_press`` should never fire.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def ButtonDemo() -> pn.Node:
    """Render an enabled counter button and a disabled button."""
    count, set_count = pn.use_state(0)
    disabled_count, set_disabled_count = pn.use_state(0)

    return DemoScreen(
        "Button",
        "Tap-driven counter plus a disabled button whose handler must not fire.",
        DemoSection(
            "Enabled button",
            ResultText("Counter", count),
            ButtonsRow(
                pn.Button("Increment", on_press=lambda: set_count(count + 1)),
                pn.Button("Reset", on_press=lambda: set_count(0)),
            ),
            Hint("Tap 'Increment' to increase the counter."),
        ),
        DemoSection(
            "Disabled button",
            ResultText("Disabled taps", disabled_count),
            pn.Button(
                "Should not fire",
                on_press=lambda: set_disabled_count(disabled_count + 1),
                disabled=True,
            ),
            Hint("Tapping this button must keep 'Disabled taps' at 0."),
        ),
    )
