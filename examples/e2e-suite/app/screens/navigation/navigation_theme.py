"""Demo screen for [`pn.use_navigation_theme`][pythonnative.use_navigation_theme].

The root container's theme comes from :mod:`app.app_theme`; this demo
flips it between [`DEFAULT_NAVIGATION_THEME`][pythonnative.DEFAULT_NAVIGATION_THEME]
and [`DARK_NAVIGATION_THEME`][pythonnative.DARK_NAVIGATION_THEME] and
mirrors what ``use_navigation_theme()`` returns: the ``dark`` flag and the
[`NavigationColors`][pythonnative.NavigationColors] the native header and
Python-drawn chrome use. A card painted from the theme colors shows the
palette on screen. The theme is restored to the light preset when the
demo unmounts so later flows see the default chrome.
"""

from __future__ import annotations

import pythonnative as pn
from app.app_theme import ThemeSwitchContext
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def NavigationThemeDemo() -> pn.Element:
    """Render the active navigation theme and switch the root preset."""
    theme = pn.use_navigation_theme()
    switch = pn.use_context(ThemeSwitchContext)
    local_name, set_local_name = pn.use_state("light")
    name, set_name = switch if switch is not None else (local_name, set_local_name)

    def restore_light():
        return lambda: set_name("light")

    pn.use_effect(restore_light, [])

    preset = pn.DARK_NAVIGATION_THEME if theme.dark else pn.DEFAULT_NAVIGATION_THEME
    colors = theme.colors

    return demo_screen(
        "Navigation theme",
        "use_navigation_theme mirrors the NavigationContainer theme.",
        section(
            "Active theme",
            result_text("Theme", "dark" if theme.dark else "light"),
            result_text("Preset", name),
            result_text("Matches preset", "yes" if theme == preset else "no"),
            result_text("Primary", colors.primary),
            result_text("Card", colors.card),
            result_text("Text", colors.text),
            pn.View(
                pn.Text("themed-card", style=pn.style(color=colors.text, font_weight="700")),
                pn.Text(colors.notification, style=pn.style(color=colors.primary)),
                style=pn.style(
                    padding=14,
                    border_radius=10,
                    background_color=colors.card,
                    border_width=2,
                    border_color=colors.border,
                    spacing=4,
                ),
            ),
            buttons_row(
                pn.Button("Use dark theme", on_press=lambda: set_name("dark")),
                pn.Button("Use light theme", on_press=lambda: set_name("light")),
            ),
            hint("Switching repaints the native header and this card from the theme colors."),
        ),
    )
