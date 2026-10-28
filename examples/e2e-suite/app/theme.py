"""Shared styles for the E2E suite app.

Every demo screen reuses the same handful of styles so flows can rely
on consistent layout (no surprise scrolling, predictable gaps). The
exact visual style is unimportant; what matters is that text labels
are large enough for Maestro to find them and that controls don't
overlap.

Layout-only styles live on :class:`Layout`, a
[`StyleSheet`][pythonnative.StyleSheet] namespace. Styles that take
colors from the theme live on :class:`AppStyles`, which components
build with [`use_styles`][pythonnative.use_styles] so they're derived
once per theme and follow the dark-mode switch.
"""

from __future__ import annotations

import pythonnative as pn
from app.app_theme import SuiteTheme


class Layout(pn.StyleSheet):
    """Theme-independent layout styles."""

    screen = pn.style(gap=12, padding=16, align_items="stretch")
    row = pn.style(gap=8, align_items="center")
    stack = pn.style(gap=4)


class AppStyles:
    """Text and card styles derived from a [`SuiteTheme`][app.app_theme.SuiteTheme]."""

    def __init__(self, theme: SuiteTheme) -> None:
        colors = theme.colors
        self.title = pn.style(font_size=22, bold=True, color=colors.text)
        self.subtitle = pn.style(font_size=14, color=colors.text_secondary)
        self.section_title = pn.style(font_size=16, font_weight="600", color=colors.text)
        self.label = pn.style(font_size=14, color=colors.text)
        self.result = pn.style(font_size=15, font_weight="600", color=colors.success)
        self.hint = pn.style(font_size=12, color=theme.hint)
        self.card = pn.style(
            padding=12,
            gap=8,
            background_color=colors.surface,
            border_radius=theme.radii.md,
            border_width=1,
            border_color=colors.border,
        )
