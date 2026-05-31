"""Demo screen for [`pn.ImageBackground`][pythonnative.ImageBackground].

Maestro only needs to confirm the foreground "On top" text renders
over the background image; no interaction is required.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

# A 1x1 transparent PNG as an inline data URI, so the demo renders
# without network access on CI runners.
TRANSPARENT_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pn.component
def ImageBackgroundDemo() -> pn.Element:
    """Render foreground text layered over a fixed-size background image."""
    return demo_screen(
        "ImageBackground",
        "Foreground text renders on top of a background image.",
        section(
            "Background image",
            pn.ImageBackground(
                pn.Text(
                    "On top",
                    style=pn.style(color="#FFFFFF", font_weight="700"),
                ),
                source=TRANSPARENT_PNG,
                style=pn.style(
                    width=220,
                    height=120,
                    background_color="#1E293B",
                    align_items="center",
                    justify_content="center",
                    border_radius=8,
                ),
            ),
            hint("Maestro asserts the 'On top' label is visible over the image."),
        ),
    )
