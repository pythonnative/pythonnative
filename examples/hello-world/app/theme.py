"""The demo's theme and the styles every screen shares.

``DemoTheme`` extends [`pn.Theme`][pythonnative.Theme] with the few
colors the built-in palette doesn't name. ``App`` hands a light and a
dark variant to [`pn.ThemeProvider`][pythonnative.ThemeProvider], which
picks one from the system appearance (or the override chosen on the
Settings tab), and the navigators draw their bars from the same tokens.

Styles that read the theme are classes whose ``__init__`` takes it;
[`pn.use_styles`][pythonnative.use_styles] builds one per theme, and
attribute access means a misspelled style name is a type error.
Styles that don't depend on the theme are plain
[`pn.StyleSheet`][pythonnative.StyleSheet] namespaces in the screens
that use them.
"""

from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True, kw_only=True)
class DemoTheme(pn.Theme):
    """``pn.Theme`` plus the demo's own tokens.

    Attributes:
        accent: Warm highlight for icons and the absolute-layout pins.
        on_accent: Text drawn on ``accent``.
        on_primary: Text drawn on ``colors.primary``, ``success``, and ``error``.
        highlight: Background of the warm "async" cards.
        shadow: Color of card shadows.
    """

    accent: pn.Color
    on_accent: pn.Color = "#1A202C"
    on_primary: pn.Color = "#FFFFFF"
    highlight: pn.Color
    shadow: pn.Color = "#000000"


LIGHT_THEME = DemoTheme(
    colors=replace(pn.LIGHT_THEME.colors, primary="#0284C7"),
    accent="#F59E0B",
    highlight="#FEF3C7",
)

DARK_THEME = DemoTheme(
    dark=True,
    colors=replace(pn.DARK_THEME.colors, primary="#38BDF8"),
    accent="#FBBF24",
    highlight="#3B2F0B",
)


class AppStyles:
    """Text and layout styles shared by every screen."""

    def __init__(self, theme: DemoTheme) -> None:
        colors, typography = theme.colors, theme.typography
        self.title: pn.Style = {**typography.title, "color": colors.text}
        self.subtitle: pn.Style = {**typography.body, "color": colors.text_secondary}
        self.section_title: pn.Style = {**typography.heading, "color": colors.text}
        self.body: pn.Style = {**typography.body, "color": colors.text}
        self.hint: pn.Style = {**typography.caption, "color": colors.text_secondary}
        self.section = pn.style(gap=theme.spacing.md, padding=20, align_items="stretch")
        self.card = pn.style(
            gap=theme.spacing.sm,
            padding=theme.spacing.md,
            border_radius=theme.radii.lg,
            background_color=colors.surface,
        )
        self.warm_card = pn.style(
            gap=theme.spacing.sm,
            padding=20,
            border_radius=12,
            background_color=theme.highlight,
        )
        self.field = pn.style(
            padding=12,
            border_radius=theme.radii.md,
            border_width=1,
            border_color=colors.border,
            background_color=colors.surface,
            color=colors.text,
            font_size=16,
        )
