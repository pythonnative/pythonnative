"""Layout tab: a tour of the pure-Python flex engine.

Shows three things the engine does that mobile devs typically need:

- ``flex: 1`` to split a row between fixed and stretching children.
- ``aspect_ratio`` to size a box from a single dimension + ratio.
- ``position: "absolute"`` with edge anchors, including percentage
  offsets for centering.
"""

import pythonnative as pn
from app.theme import styles

local_styles = pn.StyleSheet.create(
    flex_demo={
        "flex_direction": "row",
        "spacing": 8,
        "padding": 16,
        "background_color": "#EDF2F7",
        "height": 80,
    },
    flex_box={"background_color": "#4299E1", "padding": 12},
    flex_box_alt={"background_color": "#48BB78", "padding": 12},
    flex_box_label={"color": "#FFFFFF", "bold": True, "text_align": "center"},
    abs_canvas={
        "background_color": "#1A202C",
        "height": 200,
        "padding": 0,
    },
    abs_pin={
        "position": "absolute",
        "background_color": "#F6AD55",
        "padding": 8,
    },
    abs_label={"color": "#1A202C", "bold": True},
)


@pn.component
def LayoutScreen() -> pn.Element:
    return pn.ScrollView(
        pn.Column(
            pn.Text("Flex layout", style=styles["title"]),
            pn.Text(
                "Three siblings sharing a row; the middle one expands with `flex: 1`.",
                style=styles["hint"],
            ),
            pn.Row(
                pn.View(
                    pn.Text("80px", style=local_styles["flex_box_label"]),
                    style={**local_styles["flex_box"], "width": 80},
                ),
                pn.View(
                    pn.Text("flex: 1", style=local_styles["flex_box_label"]),
                    style={**local_styles["flex_box"], "flex": 1},
                ),
                pn.View(
                    pn.Text("60px", style=local_styles["flex_box_label"]),
                    style={**local_styles["flex_box_alt"], "width": 60},
                ),
                style=local_styles["flex_demo"],
            ),
            pn.Text("Aspect ratio", style=styles["title"]),
            pn.Text(
                "A square (1:1) and a 16:9 box, both sized purely by `aspect_ratio`.",
                style=styles["hint"],
            ),
            pn.Row(
                pn.View(
                    pn.Text("1:1", style=local_styles["flex_box_label"]),
                    style={**local_styles["flex_box"], "width": 80, "aspect_ratio": 1.0},
                ),
                pn.View(
                    pn.Text("16:9", style=local_styles["flex_box_label"]),
                    style={
                        **local_styles["flex_box_alt"],
                        "width": 144,
                        "aspect_ratio": 16 / 9,
                    },
                ),
                style={"flex_direction": "row", "spacing": 12, "padding": 16},
            ),
            pn.Text("Absolute positioning", style=styles["title"]),
            pn.Text(
                "The four pinned tags are positioned absolutely against this dark canvas.",
                style=styles["hint"],
            ),
            pn.View(
                pn.View(
                    pn.Text("top-left", style=local_styles["abs_label"]),
                    style={**local_styles["abs_pin"], "top": 8, "left": 8},
                ),
                pn.View(
                    pn.Text("top-right", style=local_styles["abs_label"]),
                    style={**local_styles["abs_pin"], "top": 8, "right": 8},
                ),
                pn.View(
                    pn.Text("bottom-left", style=local_styles["abs_label"]),
                    style={**local_styles["abs_pin"], "bottom": 8, "left": 8},
                ),
                pn.View(
                    pn.Text("bottom-right", style=local_styles["abs_label"]),
                    style={**local_styles["abs_pin"], "bottom": 8, "right": 8},
                ),
                pn.View(
                    pn.Text("centered", style=local_styles["abs_label"]),
                    style={
                        **local_styles["abs_pin"],
                        "background_color": "#FBD38D",
                        "left": "30%",
                        "right": "30%",
                        "top": "40%",
                    },
                ),
                style=local_styles["abs_canvas"],
            ),
            style=styles["section"],
        )
    )
