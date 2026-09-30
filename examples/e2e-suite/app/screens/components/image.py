"""Demo screen for [`pn.Image`][pythonnative.Image].

Renders a small placeholder image using an inline data URI plus an
``accessibility_label`` Maestro can find. The actual pixel content
doesn't matter; what matters is that ``Image`` instantiates without
error, that the surrounding labels render, and that the load lifecycle
(``on_load_start`` -> ``on_load`` -> ``on_load_end``) reaches Python.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

# A 1x1 transparent PNG. Bundling an inline data URI means the demo
# works even when the CI runner has no internet access.
TRANSPARENT_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pn.component
def ImageDemo() -> pn.Node:
    """Render a tiny inline data-URI image with stable labels around it."""
    load_started, set_load_started = pn.use_state(False)
    load_ended, set_load_ended = pn.use_state(False)
    loaded_size, set_loaded_size = pn.use_state("none")

    def on_load(event: pn.ImageLoadEvent) -> None:
        set_loaded_size(f"{int(event.width)}x{int(event.height)}")

    return DemoScreen(
        "Image",
        "Three sized image instances render side-by-side.",
        DemoSection(
            "Inline data-URI image",
            pn.Image(
                source=TRANSPARENT_PNG,
                accessibility_label="image-tile",
                fade_duration=0,
                on_load_start=lambda: set_load_started(True),
                on_load=on_load,
                on_load_end=lambda: set_load_ended(True),
                style=pn.style(width=64, height=64, background_color="#FECACA"),
            ),
            ResultText("Load started", "yes" if load_started else "no"),
            ResultText("Load ended", "yes" if load_ended else "no"),
            ResultText("Loaded size", loaded_size),
            Hint("If the image fails to load, the colored background remains."),
        ),
        DemoSection(
            "Three tiles",
            pn.Row(
                pn.Image(
                    source=TRANSPARENT_PNG,
                    fade_duration=150,
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
                style=pn.style(gap=8),
            ),
            pn.Text("Tiles rendered: 3"),
        ),
    )
