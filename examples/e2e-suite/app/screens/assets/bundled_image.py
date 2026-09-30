"""Demo screen for [`pn.asset`][pythonnative.asset] and bundled images.

``app/assets/images/badge.png`` ships with ``@2x`` and ``@3x`` variants
that are tinted differently (red, green, blue), so the color that shows
tells you which variant the device picked. The same ``Asset`` also
drives ``default_source`` (a local placeholder shown while a remote
image loads) and ``blur_radius``.

Maestro asserts the text derived from the ``Asset`` object (its URI and
``exists()``), which is stable across platforms even though the pixels
aren't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

BADGE = pn.asset("images/badge.png")
PLACEHOLDER = pn.asset("images/placeholder.png")


@pn.component
def BundledImageDemo() -> pn.Node:
    """Render a bundled image at three sizes plus placeholder and blur variants."""
    return DemoScreen(
        "Bundled image",
        "Image sources can be files under app/assets/, resolved per screen density.",
        DemoSection(
            "Density variants",
            pn.Row(
                pn.Image(source=BADGE, style=pn.style(width=24, height=24)),
                pn.Image(source=BADGE, style=pn.style(width=48, height=48)),
                pn.Image(source=BADGE, accessibility_label="bundled-badge", style=pn.style(width=72, height=72)),
                style=pn.style(gap=12, align_items="center"),
            ),
            Hint("Red is the 1x file, green @2x, blue @3x: the runtime picks the closest denser variant."),
            ResultText("Asset URI", BADGE.uri),
            ResultText("Asset exists", "yes" if BADGE.exists() else "no"),
            ResultText("Missing asset exists", "yes" if pn.asset("images/nope.png").exists() else "no"),
        ),
        DemoSection(
            "default_source and blur_radius",
            pn.Row(
                pn.Image(
                    source="https://example.invalid/never-loads.png",
                    default_source=PLACEHOLDER,
                    style=pn.style(width=48, height=48, border_radius=8),
                ),
                pn.Image(source=BADGE, blur_radius=4, style=pn.style(width=48, height=48)),
                style=pn.style(gap=12),
            ),
            Hint("Left: a placeholder stays up because the remote URL never loads. Right: the badge blurred."),
        ),
    )
