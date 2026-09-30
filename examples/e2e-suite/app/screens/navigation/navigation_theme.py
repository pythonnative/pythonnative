"""Demo screen for [`pn.ThemeProvider`][pythonnative.ThemeProvider] driving navigator chrome.

``main.py`` wraps the app in a ``ThemeProvider`` with the suite's light
and dark [`Theme`][pythonnative.Theme]s from :mod:`app.app_theme`, and
the navigators draw their headers, tab bars, and drawer panels from the
same tokens. This demo flips the effective color scheme with
[`appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme],
so the provider switches presets, and mirrors what
``use_theme(SuiteTheme)`` returns: the ``dark`` flag and the
[`Colors`][pythonnative.Colors] the chrome uses. A card painted from
the theme colors shows the palette on screen. The scheme override is
cleared when the demo unmounts so later flows see the default chrome.
"""

from __future__ import annotations

import pythonnative as pn
from app.app_theme import SUITE_DARK, SUITE_LIGHT, SuiteTheme, preset_name
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


def _follow_system() -> None:
    pn.appearance.set_color_scheme(None)


class _CardStyles:
    """The themed card, derived once per theme with ``use_styles``."""

    def __init__(self, theme: SuiteTheme) -> None:
        colors = theme.colors
        self.card = pn.style(
            padding=14,
            border_radius=theme.radii.md,
            background_color=colors.surface,
            border_width=2,
            border_color=colors.border,
            gap=4,
        )
        self.title = pn.style(color=colors.text, font_weight="700")
        self.accent = pn.style(color=colors.primary)


@pn.component
def NavigationThemeDemo() -> pn.Node:
    """Render the active app theme and switch the color scheme the provider follows."""
    theme = pn.use_theme(SuiteTheme)
    styles = pn.use_styles(_CardStyles)
    scheme = pn.use_color_scheme()
    pn.use_effect(lambda: _follow_system, [])

    preset = SUITE_DARK if theme.dark else SUITE_LIGHT
    colors = theme.colors

    return DemoScreen(
        "Navigation theme",
        "One app Theme styles the screens and the navigator chrome.",
        DemoSection(
            "Active theme",
            ResultText("Theme", "dark" if theme.dark else "light"),
            ResultText("Preset", preset_name(theme)),
            ResultText("Scheme", scheme),
            ResultText("Matches preset", "yes" if theme == preset else "no"),
            ResultText("Primary", colors.primary),
            ResultText("Surface", colors.surface),
            ResultText("Text", colors.text),
            pn.View(
                pn.Text("themed-card", style=styles.title),
                pn.Text(colors.error, style=styles.accent),
                style=styles.card,
            ),
            ButtonsRow(
                pn.Button("Use dark theme", on_press=lambda: pn.appearance.set_color_scheme("dark")),
                pn.Button("Use light theme", on_press=lambda: pn.appearance.set_color_scheme("light")),
            ),
            Hint("Switching repaints the native header and this card from the theme colors."),
        ),
    )
