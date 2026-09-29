"""Demo screen for [`pn.PixelRatio`][pythonnative.PixelRatio].

Reads the device density and font scale and converts a layout size to
physical pixels. ``round_to_nearest_pixel`` snaps a fractional layout
size to the pixel grid; the demo shows the snapped value stays within one
pixel of the input, which holds on every density.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def PixelRatioDemo() -> pn.Element:
    """Render density conversions from the PixelRatio module."""
    ratio = pn.PixelRatio.get()
    font_scale = pn.PixelRatio.get_font_scale()
    pixels = pn.PixelRatio.get_pixel_size_for_layout_size(100)
    snapped = pn.PixelRatio.round_to_nearest_pixel(10.3)

    return demo_screen(
        "PixelRatio",
        "Density, font scale, and layout-to-pixel conversions.",
        section(
            "PixelRatio module",
            result_text("Ratio", ratio),
            result_text("Ratio positive", "yes" if ratio > 0 else "no"),
            result_text("Font scale positive", "yes" if font_scale > 0 else "no"),
            result_text("Pixels for 100", pixels),
            result_text("Pixels match ratio", "yes" if pixels == round(100 * ratio) else "no"),
            result_text("Snapped 10.3", snapped),
            result_text("Snap within a pixel", "yes" if abs(snapped - 10.3) <= 1 / ratio else "no"),
            hint("Maestro asserts the derived 'yes' flags; raw values vary per device."),
        ),
    )
