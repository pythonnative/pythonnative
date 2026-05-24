"""Demo screen for [`pn.use_window_dimensions`][pythonnative.use_window_dimensions].

The hook returns a ``{"width": float, "height": float}`` dict for the
current window. The exact values vary by device/emulator, so the demo
asserts the line is present and contains the expected ``×`` glyph.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def UseWindowDimensionsDemo() -> pn.Element:
    """Render the current window dimensions in a stable, single line."""
    dims = pn.use_window_dimensions()

    return demo_screen(
        "use_window_dimensions",
        "Current window size, returned reactively by the hook.",
        section(
            "Dimensions",
            result_text("Window", f"{int(dims['width'])} × {int(dims['height'])}"),
            hint("Maestro asserts the 'Window:' line is visible (size varies)."),
        ),
    )
