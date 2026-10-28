"""Demo screen for [`pn.SafeAreaView`][pythonnative.SafeAreaView].

Wraps a body of text in ``SafeAreaView``. The visual result is
trivial on the simulator since we're already inside a stack with
nav-bar insets applied, but the demo confirms the element instantiates
without error and renders its children.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


@pn.component
def SafeAreaViewDemo() -> pn.Node:
    """Render a SafeAreaView holding a stable text line."""
    return DemoScreen(
        "SafeAreaView",
        "Children inside SafeAreaView should render without overlapping insets.",
        DemoSection(
            "SafeAreaView body",
            pn.SafeAreaView(
                pn.Text(
                    "Inside SafeAreaView",
                    style=pn.style(font_size=16, padding=12, background_color="#E0E7FF"),
                ),
                style=pn.style(background_color="#EEF2FF", padding=8),
            ),
            Hint("Maestro asserts 'Inside SafeAreaView' is visible."),
        ),
    )
