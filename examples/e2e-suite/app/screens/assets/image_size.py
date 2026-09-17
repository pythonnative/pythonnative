"""Demo screen for the [`pn.Images`][pythonnative.Images] module.

``Images.get_size`` reads an image's logical dimensions without
displaying it, and ``Images.prefetch`` warms the cache. Both are
``async`` and run inside an ``async def`` effect here. The bundled badge
is 48 x 48 at 1x (its ``@2x`` and ``@3x`` variants report the same
logical size), which Maestro asserts.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section

BADGE = pn.asset("images/badge.png")


@pn.component
def ImageSizeDemo() -> pn.Element:
    """Measure and prefetch a bundled image through the Images module."""
    size, set_size = pn.use_state("measuring")
    prefetched, set_prefetched = pn.use_state("pending")
    error, set_error = pn.use_state("")

    async def _measure() -> None:
        try:
            measured = await pn.Images.get_size(BADGE)
            set_size(f"{measured.width:.0f} x {measured.height:.0f}")
            set_prefetched("yes" if await pn.Images.prefetch(BADGE) else "no")
        except Exception as exc:  # pragma: no cover - surfaced in the UI for debugging
            set_error(str(exc))

    pn.use_effect(_measure, [])

    return demo_screen(
        "Images module",
        "Images.get_size and Images.prefetch work on bundled assets and URLs.",
        section(
            "get_size",
            result_text("Size", size),
            hint("The badge is 48 x 48 logical points regardless of which density variant is bundled."),
        ),
        section(
            "prefetch",
            result_text("Prefetched", prefetched),
            pn.Button("Clear image cache", on_press=pn.Images.clear_cache),
        ),
        *([result_text("Error", error)] if error else []),
    )
