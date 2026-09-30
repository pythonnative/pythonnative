"""Layout tab: a tour of the flex engine.

Shows three things the engine does that mobile devs typically need:

- ``flex: 1`` to split a row between fixed and stretching children.
- ``aspect_ratio`` to size a box from a single dimension and a ratio.
- ``position: "absolute"`` with edge anchors, including percentage
  offsets for centering.

Styles are composed with lists: ``style=[styles.box, {"width": 80}]``
layers the second dict over the first.
"""

import pythonnative as pn
from app.theme import AppStyles, DemoTheme


class Styles(pn.StyleSheet):
    row = pn.style(gap=12, padding=16)
    top_left = pn.style(top=8, left=8)
    top_right = pn.style(top=8, right=8)
    bottom_left = pn.style(bottom=8, left=8)
    bottom_right = pn.style(bottom=8, right=8)
    centered = pn.style(left="30%", right="30%", top="40%")


class LayoutStyles:
    def __init__(self, theme: DemoTheme) -> None:
        colors = theme.colors
        self.flex_demo = pn.style(gap=8, padding=16, height=80, background_color=colors.surface)
        self.box = pn.style(padding=12, background_color=colors.primary)
        self.box_alt = pn.style(padding=12, background_color=colors.success)
        self.box_label = pn.style(color=theme.on_primary, bold=True, text_align="center")
        # The canvas inverts the page colors so the pins stand out in either theme.
        self.canvas = pn.style(height=200, background_color=colors.text)
        self.pin = pn.style(position="absolute", padding=8, background_color=theme.accent)
        self.pin_label = pn.style(color=theme.on_accent, bold=True)


@pn.component
def Box(label: str, size: pn.Style, alt: bool = False) -> pn.Node:
    """A labeled box; ``size`` holds the layout keys being demonstrated."""
    styles = pn.use_styles(LayoutStyles)
    return pn.View(pn.Text(label, style=styles.box_label), style=[styles.box_alt if alt else styles.box, size])


@pn.component
def Pin(label: str, position: pn.Style, color: pn.Color | None = None) -> pn.Node:
    """An absolutely positioned tag; ``position`` holds its edge anchors."""
    styles = pn.use_styles(LayoutStyles)
    return pn.View(
        pn.Text(label, style=styles.pin_label),
        style=[styles.pin, position, {"background_color": color} if color else None],
    )


@pn.component
def LayoutScreen() -> pn.Node:
    app_styles = pn.use_styles(AppStyles)
    styles = pn.use_styles(LayoutStyles)
    theme = pn.use_theme(DemoTheme)
    return pn.ScrollView(
        pn.Column(
            pn.Text("Flex layout", style=app_styles.title),
            pn.Text(
                "Three siblings sharing a row; the middle one expands with `flex: 1`.",
                style=app_styles.hint,
            ),
            pn.Row(
                Box("80px", {"width": 80}),
                Box("flex: 1", {"flex": 1}),
                Box("60px", {"width": 60}, alt=True),
                style=styles.flex_demo,
            ),
            pn.Text("Aspect ratio", style=app_styles.title),
            pn.Text(
                "A square (1:1) and a 16:9 box, both sized purely by `aspect_ratio`.",
                style=app_styles.hint,
            ),
            pn.Row(
                Box("1:1", {"width": 80, "aspect_ratio": 1.0}),
                Box("16:9", {"width": 144, "aspect_ratio": 16 / 9}, alt=True),
                style=Styles.row,
            ),
            pn.Text("Absolute positioning", style=app_styles.title),
            pn.Text(
                "The pinned tags are positioned absolutely against this canvas.",
                style=app_styles.hint,
            ),
            pn.View(
                Pin("top-left", Styles.top_left),
                Pin("top-right", Styles.top_right),
                Pin("bottom-left", Styles.bottom_left),
                Pin("bottom-right", Styles.bottom_right),
                Pin("centered", Styles.centered, color=theme.colors.warning),
                style=styles.canvas,
            ),
            style=app_styles.section,
        )
    )
