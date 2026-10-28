"""The suite's light and dark themes.

``main.py`` wraps the whole app in a [`ThemeProvider`][pythonnative.ThemeProvider]
with :data:`SUITE_LIGHT` and :data:`SUITE_DARK`, so the provider follows
the effective color scheme: the system appearance, or the override a
demo sets with [`appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme].
Navigator chrome (headers, tab bars, the drawer panel) and the shared
styles in :mod:`app.theme` read the same tokens, so flipping the scheme
repaints everything.

:class:`SuiteTheme` subclasses [`Theme`][pythonnative.Theme] to add one
application token, ``hint``, the color of the quiet explanatory lines
every demo shows.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True, kw_only=True)
class SuiteTheme(pn.Theme):
    """The built-in tokens plus the suite's ``hint`` text color."""

    hint: pn.Color = "#6B7280"


SUITE_LIGHT = SuiteTheme(
    colors=replace(
        pn.LIGHT_THEME.colors,
        background="#FFFFFF",
        surface="#F8FAFC",
        text="#0F172A",
        text_secondary="#475569",
        border="#E2E8F0",
        success="#047857",
    ),
)
"""Light preset: the built-in light palette on a white background."""

SUITE_DARK = SuiteTheme(
    dark=True,
    colors=replace(
        pn.DARK_THEME.colors,
        surface="#111827",
        text="#F8FAFC",
        text_secondary="#CBD5E1",
        border="#334155",
        success="#34D399",
    ),
    hint="#9CA3AF",
)
"""Dark preset: the built-in dark palette with slate surfaces."""


def preset_name(theme: pn.Theme) -> str:
    """Return ``"light"`` or ``"dark"`` for a suite preset, or ``"custom"`` for anything else."""
    if theme == SUITE_LIGHT:
        return "light"
    if theme == SUITE_DARK:
        return "dark"
    return "custom"
