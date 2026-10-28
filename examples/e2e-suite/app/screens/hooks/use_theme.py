"""Demo screen for [`pn.use_theme`][pythonnative.use_theme] and [`pn.use_styles`][pythonnative.use_styles].

``main.py`` provides the suite's light and dark themes (see
:mod:`app.app_theme`) through a [`ThemeProvider`][pythonnative.ThemeProvider],
which follows the effective color scheme. ``use_theme(SuiteTheme)``
returns the active preset typed as the suite's subclass, so its extra
``hint`` token type-checks. Maestro forces dark via the appearance
override and asserts the theme's background and primary colors flipped;
the swatches are styled by ``use_styles``, which rebuilds them once per
theme.
"""

from __future__ import annotations

import pythonnative as pn
from app.app_theme import SuiteTheme
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


class _SwatchStyles:
    """Swatches painted from theme tokens."""

    def __init__(self, theme: SuiteTheme) -> None:
        self.primary = pn.style(
            width=64, height=24, background_color=theme.colors.primary, border_radius=theme.radii.sm
        )
        self.hint = pn.style(width=64, height=24, background_color=theme.hint, border_radius=theme.radii.sm)


@pn.component
def UseThemeDemo() -> pn.Node:
    """Render theme-derived values that flip with the color scheme."""
    theme = pn.use_theme(SuiteTheme)
    styles = pn.use_styles(_SwatchStyles)
    return DemoScreen(
        "use_theme",
        "The provided theme follows the color scheme unless the app pins one.",
        DemoSection(
            "Theme values",
            ResultText("Theme background", theme.colors.background),
            ResultText("Theme primary", theme.colors.primary),
            ResultText("Theme hint", theme.hint),
            ResultText("Theme spacing md", theme.spacing.md),
            pn.Row(pn.View(style=styles.primary), pn.View(style=styles.hint), style=pn.style(gap=theme.spacing.sm)),
            ButtonsRow(
                pn.Button(
                    "Force dark",
                    on_press=lambda: pn.appearance.set_color_scheme("dark"),
                ),
                pn.Button(
                    "Force light",
                    on_press=lambda: pn.appearance.set_color_scheme("light"),
                ),
            ),
            pn.Button(
                "Follow system",
                on_press=lambda: pn.appearance.set_color_scheme(None),
            ),
            Hint("Maestro flips the scheme and asserts the theme colors follow."),
        ),
    )
