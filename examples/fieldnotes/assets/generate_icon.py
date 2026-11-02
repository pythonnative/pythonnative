"""Draw the Field Notes app icon: a green field notebook with a contour-line page.

Run it from this directory with Pillow installed (``python generate_icon.py``).
The result, ``icon.png``, is checked in, so a build doesn't need this script.
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
FIELD = (31, 77, 58)
COVER = (232, 223, 200)
SPINE = (178, 94, 53)
INK = (31, 77, 58)
RULE = (196, 183, 150)


def draw_icon() -> Image.Image:
    """Return the 1024x1024 icon, opaque as the App Store requires."""
    icon = Image.new("RGB", (SIZE, SIZE), FIELD)
    draw = ImageDraw.Draw(icon)
    # The notebook's cover and spine band.
    draw.rounded_rectangle((212, 132, 812, 892), radius=48, fill=COVER)
    draw.rounded_rectangle((212, 132, 322, 892), radius=48, fill=SPINE)
    draw.rectangle((282, 132, 322, 892), fill=SPINE)
    # An elastic closure, as on a real field notebook.
    draw.rectangle((708, 132, 736, 892), fill=FIELD)
    # Ruled lines.
    for y in range(560, 800, 80):
        draw.line((380, y, 650, y), fill=RULE, width=14)
    # Contour lines around a summit, the mark on the cover.
    for inset, width in ((0, 16), (46, 14), (88, 12)):
        draw.ellipse((384 + inset, 228 + inset, 652 - inset, 472 - inset), outline=INK, width=width)
    draw.ellipse((504, 340, 532, 368), fill=SPINE)
    return icon


if __name__ == "__main__":
    draw_icon().save(Path(__file__).with_name("icon.png"))
