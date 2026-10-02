"""Showcase screen: visual primitives (Animated, typography, borders, chips).

Pushed onto the native stack by the Home and Settings tabs with
``nav.push(ShowcaseScreen(message=...))``. The ``message`` parameter is
the screen's route param: screens are ordinary components, so their
params arrive as arguments.
"""

import pythonnative as pn
from app.screens.data import DataScreen
from app.screens.forms import FormsScreen
from app.theme import AppStyles, DemoTheme


class Styles(pn.StyleSheet):
    headline = pn.style(font_size=28, font_weight="700")
    chip = pn.style(padding=8, border_radius=16)
    chip_label = pn.style(font_weight="600", font_size=13)
    chips = pn.style(gap=8)
    typography = pn.style(gap=4)


class ShowcaseStyles:
    """Styles that follow the theme, built once per theme by ``pn.use_styles``."""

    def __init__(self, theme: DemoTheme) -> None:
        colors = theme.colors
        self.animated_card = pn.style(padding=16, gap=6, border_radius=12, background_color=theme.highlight)
        self.body = pn.style(font_size=16, color=colors.text, letter_spacing=0.2, line_height=22)
        self.caption = pn.style(font_size=12, color=colors.text_secondary, text_decoration="underline")
        self.card = pn.style(
            padding=20,
            gap=4,
            background_color=colors.surface,
            border_radius=theme.radii.lg,
            border_width=1,
            border_color=colors.border,
            shadow_color=theme.shadow,
            shadow_offset={"width": 0, "height": 4},
            shadow_opacity=0.06,
            shadow_radius=12,
            elevation=4,
        )
        self.on_color = pn.style(color=theme.on_primary, font_weight="600")
        self.pressable = pn.style(padding=14, border_radius=12, align_items="center")


@pn.component
def AnimatedCard() -> pn.Node:
    """Demonstrates ``Animated.View`` driven by ``use_animated_value``.

    Uses an ``async def`` effect so the parallel enter animation is
    awaited (no callback ladder) and gets automatically cancelled if
    the screen unmounts before it finishes.
    """
    opacity = pn.use_animated_value(0.0)
    scale = pn.use_animated_value(0.9)
    app_styles = pn.use_styles(AppStyles)
    styles = pn.use_styles(ShowcaseStyles)

    async def enter() -> None:
        await pn.Animated.parallel(
            [
                pn.Animated.timing(opacity, to=1.0, duration=400),
                pn.Animated.spring(scale, to=1.0, stiffness=180, damping=14),
            ]
        )

    pn.use_effect(enter, [opacity, scale])

    return pn.Animated.View(
        pn.Text("I faded in", style=app_styles.section_title),
        pn.Text("Awaited Animated.parallel(timing + spring).", style=app_styles.hint),
        style=[styles.animated_card, {"opacity": opacity, "scale": scale}],
    )


@pn.memo
@pn.component
def TypographyDemo() -> pn.Node:
    """Wrapped in [`pn.memo`][pythonnative.memo] so it skips re-rendering when the screen's state changes."""
    print("[TypographyDemo] render (should only appear when the theme changes)")
    app_styles = pn.use_styles(AppStyles)
    styles = pn.use_styles(ShowcaseStyles)
    return pn.Column(
        pn.Text("Headline", style=[app_styles.body, Styles.headline]),
        pn.Text("Body text with letter spacing and a generous line height.", style=styles.body),
        pn.Text("Underlined caption", style=styles.caption),
        style=Styles.typography,
    )


@pn.memo
@pn.component
def BordersAndShadows() -> pn.Node:
    app_styles = pn.use_styles(AppStyles)
    styles = pn.use_styles(ShowcaseStyles)
    return pn.View(
        pn.Text("Card with border + shadow", style=app_styles.section_title),
        pn.Text("border_radius, border_width, shadow_*, elevation all in style.", style=app_styles.hint),
        style=styles.card,
    )


@pn.component
def Chip(label: str, color: pn.Color) -> pn.Node:
    styles = pn.use_styles(ShowcaseStyles)
    return pn.View(
        pn.Text(label, style=[Styles.chip_label, styles.on_color]),
        style=[Styles.chip, {"background_color": color}],
    )


@pn.memo
@pn.component
def Chips() -> pn.Node:
    colors = pn.use_theme().colors
    return pn.Row(
        Chip("New", colors.primary),
        Chip("Trending", colors.success),
        Chip("Sale", colors.error),
        style=Styles.chips,
    )


def section_heading(title: str, hint: str, styles: AppStyles) -> pn.Element:
    """Compose two sibling [`pn.Text`][pythonnative.Text] nodes via [`pn.Fragment`][pythonnative.Fragment].

    Returning a Fragment from a plain helper (not a ``@pn.component``)
    lets the surrounding parent (here a [`pn.Column`][pythonnative.Column])
    flatten the siblings into its own child list without an extra
    wrapper view.
    """
    return pn.Fragment(
        pn.Text(title, style=styles.section_title),
        pn.Text(hint, style=styles.hint),
    )


@pn.component
def ShowcaseScreen(message: str = "Visual showcase") -> pn.Node:
    nav = pn.use_navigation()
    app_styles = pn.use_styles(AppStyles)
    styles = pn.use_styles(ShowcaseStyles)
    colors = pn.use_theme().colors
    print(f"[ShowcaseScreen] render message={message!r}")

    highlighted, set_highlighted = pn.use_state(False)

    return pn.ScrollView(
        pn.Column(
            pn.Text(message, style=app_styles.title),
            AnimatedCard(),
            section_heading("Typography", "Memoized via @pn.memo; renders only once per theme.", app_styles),
            TypographyDemo(),
            BordersAndShadows(),
            section_heading("Chips", "Composed via pn.Fragment without an extra container.", app_styles),
            Chips(),
            pn.Pressable(
                pn.View(
                    pn.Text("Pressable with feedback", style=styles.on_color),
                    style=[styles.pressable, {"background_color": colors.success if highlighted else colors.primary}],
                ),
                on_press=lambda: set_highlighted(not highlighted),
                pressed_opacity=0.7,
            ),
            pn.Button("View Forms", on_press=lambda: nav.push(FormsScreen())),
            pn.Button("View Async Demo", on_press=lambda: nav.push(DataScreen())),
            pn.Button("Back", on_press=nav.go_back),
            style=app_styles.section,
        )
    )
