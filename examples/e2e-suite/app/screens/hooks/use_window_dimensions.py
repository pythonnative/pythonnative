"""Demo screen for [`pn.use_window_dimensions`][pythonnative.use_window_dimensions].

The hook returns a ``{"width": float, "height": float}`` dict for the
current window. The exact values vary by device/emulator, so the demo
asserts the line is present and contains the expected ``×`` glyph.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseWindowDimensionsDemo() -> pn.Node:
    """Render the current window dimensions in a stable, single line."""
    dims = pn.use_window_dimensions()

    return DemoScreen(
        "use_window_dimensions",
        "Current window size, returned reactively by the hook.",
        DemoSection(
            "Dimensions",
            ResultText("Window", f"{int(dims.width)} × {int(dims.height)}"),
            Hint("Maestro asserts the 'Window:' line is visible (size varies)."),
        ),
    )
