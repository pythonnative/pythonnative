"""Showcase screen: visual primitives — Animated, typography, borders, chips.

Pushed onto the native stack by tapping "View Showcase" on the Home
tab. Receives a ``message`` param via ``nav.get_params()`` to
demonstrate route parameters.
"""

import pythonnative as pn
from app.theme import styles

local_styles = pn.StyleSheet.create(
    card={
        "padding": 20,
        "background_color": "#FFFFFF",
        "border_radius": 16,
        "border_width": 1,
        "border_color": "#E5E7EB",
        "shadow_color": "#000000",
        "shadow_offset": {"width": 0, "height": 4},
        "shadow_opacity": 0.06,
        "shadow_radius": 12,
        "elevation": 4,
    },
    chip={
        "padding": 8,
        "border_radius": 16,
        "background_color": "#0EA5E9",
    },
    chip_label={"color": "#FFFFFF", "font_weight": "600", "font_size": 13},
)


@pn.component
def AnimatedCard() -> pn.Element:
    """Demonstrates ``Animated.View`` driven by ``AnimatedValue`` + ``use_memo``."""
    opacity = pn.use_memo(lambda: pn.Animated.Value(0.0), [])
    scale = pn.use_memo(lambda: pn.Animated.Value(0.9), [])

    def _enter() -> None:
        pn.Animated.parallel(
            [
                pn.Animated.timing(opacity, to=1.0, duration=400),
                pn.Animated.spring(scale, to=1.0, stiffness=180, damping=14),
            ]
        ).start()

    pn.use_effect(_enter, [])

    return pn.Animated.View(
        pn.Text("I faded in", style={"font_size": 18, "font_weight": "600"}),
        pn.Text(
            "Animated.parallel with timing + spring drives this card.",
            style={"font_size": 13, "color": "#6B7280"},
        ),
        style={
            "opacity": opacity,
            "scale": scale,
            "padding": 16,
            "background_color": "#FEF3C7",
            "border_radius": 12,
            "spacing": 6,
        },
    )


@pn.component
def TypographyDemo() -> pn.Element:
    return pn.Column(
        pn.Text("Headline", style={"font_size": 28, "font_weight": "700"}),
        pn.Text(
            "Body text with letter spacing and a generous line height.",
            style={
                "font_size": 16,
                "color": "#1F2937",
                "letter_spacing": 0.2,
                "line_height": 22,
            },
        ),
        pn.Text(
            "Underlined caption",
            style={"font_size": 12, "color": "#6B7280", "text_decoration": "underline"},
        ),
        style={"spacing": 4},
    )


@pn.component
def BordersAndShadows() -> pn.Element:
    return pn.View(
        pn.Text("Card with border + shadow", style=styles["section_title"]),
        pn.Text(
            "border_radius, border_width, shadow_*, elevation all in style.",
            style=styles["hint"],
        ),
        style=local_styles["card"],
    )


@pn.component
def Chips() -> pn.Element:
    return pn.Row(
        pn.View(pn.Text("New", style=local_styles["chip_label"]), style=local_styles["chip"]),
        pn.View(
            pn.Text("Trending", style=local_styles["chip_label"]),
            style={**local_styles["chip"], "background_color": "#22C55E"},
        ),
        pn.View(
            pn.Text("Sale", style=local_styles["chip_label"]),
            style={**local_styles["chip"], "background_color": "#EF4444"},
        ),
        style={"spacing": 8},
    )


@pn.component
def ShowcaseScreen() -> pn.Element:
    nav = pn.use_navigation()
    message = nav.get_params().get("message", "Visual showcase")
    print(f"[ShowcaseScreen] render message={message!r}")

    pressed_color, set_pressed_color = pn.use_state("#0EA5E9")

    def _toggle_color() -> None:
        set_pressed_color("#10B981" if pressed_color == "#0EA5E9" else "#0EA5E9")

    def view_forms() -> None:
        nav.navigate("Forms")

    def go_back() -> None:
        nav.go_back()

    return pn.ScrollView(
        pn.Column(
            pn.Text(message, style=styles["title"]),
            AnimatedCard(),
            pn.Text("Typography", style=styles["section_title"]),
            TypographyDemo(),
            BordersAndShadows(),
            pn.Text("Chips", style=styles["section_title"]),
            Chips(),
            pn.Pressable(
                pn.View(
                    pn.Text(
                        "Pressable with feedback",
                        style={"color": "#FFFFFF", "font_weight": "600"},
                    ),
                    style={
                        "padding": 14,
                        "background_color": pressed_color,
                        "border_radius": 12,
                        "align_items": "center",
                    },
                ),
                on_press=_toggle_color,
                pressed_opacity=0.7,
            ),
            pn.Button("View Forms", on_click=view_forms),
            pn.Button("Back", on_click=go_back),
            style=styles["section"],
        )
    )
