"""Demo screen for [`pn.Image`][pythonnative.Image].

Renders a small placeholder image using a public URL plus an
``accessibility_label`` Maestro can find. The actual pixel content
doesn't matter; what matters is that ``Image`` instantiates without
error and that the surrounding labels render.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

# A 1x1 transparent PNG. Bundling an inline data URI means the demo
# works even when the CI runner has no internet access.
TRANSPARENT_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pn.component
def ImageDemo() -> pn.Element:
    """Render a tiny inline data-URI image with stable labels around it."""
    return demo_screen(
        "Image",
        "Three sized image instances render side-by-side.",
        section(
            "Inline data-URI image",
            pn.Image(
                source=TRANSPARENT_PNG,
                accessibility_label="image-tile",
                style=pn.style(width=64, height=64, background_color="#FECACA"),
            ),
            hint("If the image fails to load, the colored background remains."),
        ),
        section(
            "Three tiles",
            pn.Row(
                pn.Image(
                    source=TRANSPARENT_PNG,
                    style=pn.style(width=40, height=40, background_color="#FCA5A5"),
                ),
                pn.Image(
                    source=TRANSPARENT_PNG,
                    style=pn.style(width=40, height=40, background_color="#86EFAC"),
                ),
                pn.Image(
                    source=TRANSPARENT_PNG,
                    style=pn.style(width=40, height=40, background_color="#93C5FD"),
                ),
                style=pn.style(spacing=8),
            ),
            pn.Text("Tiles rendered: 3"),
        ),
    )
