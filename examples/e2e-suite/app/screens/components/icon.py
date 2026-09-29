"""Demo screen for [`pn.Icon`][pythonnative.Icon].

Icons come from the bundled Lucide set and are drawn as vectors, so the
same name renders identically on iOS, Android, and in the browser
preview. Maestro asserts the count line and the name-lookup results;
the strokes themselves aren't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section
from pythonnative.icons import icon_names, is_icon_name

NAMES: tuple = ("house", "heart", "search", "settings", "bell", "chevron-right")


@pn.component
def IconDemo() -> pn.Element:
    """Render a row of icons in several sizes, colors, and stroke widths."""
    return demo_screen(
        "Icon",
        "Bundled Lucide icons render as vectors at any size and color.",
        section(
            "Icon row",
            pn.Row(
                *[pn.Icon(name, color="#0F172A") for name in NAMES],
                style=pn.style(spacing=12, align_items="center"),
            ),
            result_text("Icons rendered", len(NAMES)),
        ),
        section(
            "Size, color, fill, stroke width",
            pn.Row(
                pn.Icon("heart", size=16, color="#DC2626"),
                pn.Icon("heart", size=32, color="#DC2626"),
                pn.Icon("heart", size=48, color="#DC2626", fill="#FCA5A5"),
                pn.Icon("heart", size=48, color="#DC2626", stroke_width=1),
                pn.Icon("heart", size=48, color="#DC2626", stroke_width=3, accessibility_label="bold-heart"),
                style=pn.style(spacing=12, align_items="center"),
            ),
            hint("fill= makes a solid variant; stroke_width scales on the 24-unit grid."),
        ),
        section(
            "Name lookup",
            result_text("'house' is an icon", "yes" if is_icon_name("house") else "no"),
            result_text("'not-an-icon' is an icon", "yes" if is_icon_name("not-an-icon") else "no"),
            result_text("Icons available", "1000+" if len(icon_names()) > 1000 else len(icon_names())),
        ),
    )
