"""Demo screen for [`pn.use_theme`][pythonnative.use_theme].

Without a ``ThemeContext`` provider, ``use_theme`` resolves the
built-in light or dark theme from the effective color scheme. Maestro
forces dark via the appearance override and asserts the theme's
background color flipped, which also observes ``default_theme`` and
the ``DEFAULT_LIGHT_THEME`` / ``DEFAULT_DARK_THEME`` constants.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseThemeDemo() -> pn.Element:
    """Render theme-derived values that flip with the color scheme."""
    theme = pn.use_theme()
    return demo_screen(
        "use_theme",
        "The built-in theme follows the color scheme unless a provider pins one.",
        section(
            "Theme values",
            result_text("Theme background", theme.background_color),
            result_text("Theme primary", theme.primary_color),
            pn.View(
                style=pn.style(
                    width=64,
                    height=24,
                    background_color=theme.primary_color,
                    border_radius=6,
                ),
            ),
            buttons_row(
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
            hint("Maestro flips the scheme and asserts the theme colors follow."),
        ),
    )
