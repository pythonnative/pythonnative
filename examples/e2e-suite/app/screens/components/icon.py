"""Demo screen for [`pn.Icon`][pythonnative.Icon].

Icons come from the bundled Lucide set and are drawn as vectors, so the
same name renders identically on iOS, Android, and in the browser
preview. Maestro asserts the count line and the name-lookup results;
the strokes themselves aren't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText
from pythonnative.icons import icon_names, is_icon_name

NAMES: tuple[pn.IconName, ...] = ("house", "heart", "search", "settings", "bell", "chevron-right")


@pn.component
def IconDemo() -> pn.Node:
    """Render a row of icons in several sizes, colors, and stroke widths."""
    return DemoScreen(
        "Icon",
        "Bundled Lucide icons render as vectors at any size and color.",
        DemoSection(
            "Icon row",
            pn.Row(
                *[pn.Icon(name, color="#0F172A") for name in NAMES],
                style=pn.style(gap=12, align_items="center"),
            ),
            ResultText("Icons rendered", len(NAMES)),
        ),
        DemoSection(
            "Size, color, fill, stroke width",
            pn.Row(
                pn.Icon("heart", size=16, color="#DC2626"),
                pn.Icon("heart", size=32, color="#DC2626"),
                pn.Icon("heart", size=48, color="#DC2626", fill="#FCA5A5"),
                pn.Icon("heart", size=48, color="#DC2626", stroke_width=1),
                pn.Icon("heart", size=48, color="#DC2626", stroke_width=3, accessibility_label="bold-heart"),
                style=pn.style(gap=12, align_items="center"),
            ),
            Hint("fill= makes a solid variant; stroke_width scales on the 24-unit grid."),
        ),
        DemoSection(
            "Name lookup",
            ResultText("'house' is an icon", "yes" if is_icon_name("house") else "no"),
            ResultText("'not-an-icon' is an icon", "yes" if is_icon_name("not-an-icon") else "no"),
            ResultText("Icons available", "1000+" if len(icon_names()) > 1000 else len(icon_names())),
        ),
    )
