"""Demo screen for [`pn.PixelRatio`][pythonnative.PixelRatio].

Reads the device density and font scale and converts a layout size to
physical pixels. ``round_to_nearest_pixel`` snaps a fractional layout
size to the pixel grid; the demo shows the snapped value stays within one
pixel of the input, which holds on every density.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def PixelRatioDemo() -> pn.Node:
    """Render density conversions from the PixelRatio module."""
    ratio = pn.PixelRatio.get()
    font_scale = pn.PixelRatio.get_font_scale()
    pixels = pn.PixelRatio.get_pixel_size_for_layout_size(100)
    snapped = pn.PixelRatio.round_to_nearest_pixel(10.3)

    return DemoScreen(
        "PixelRatio",
        "Density, font scale, and layout-to-pixel conversions.",
        DemoSection(
            "PixelRatio module",
            ResultText("Ratio", ratio),
            ResultText("Ratio positive", "yes" if ratio > 0 else "no"),
            ResultText("Font scale positive", "yes" if font_scale > 0 else "no"),
            ResultText("Pixels for 100", pixels),
            ResultText("Pixels match ratio", "yes" if pixels == round(100 * ratio) else "no"),
            ResultText("Snapped 10.3", snapped),
            ResultText("Snap within a pixel", "yes" if abs(snapped - 10.3) <= 1 / ratio else "no"),
            Hint("Maestro asserts the derived 'yes' flags; raw values vary per device."),
        ),
    )
