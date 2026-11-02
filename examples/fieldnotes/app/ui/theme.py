"""The app's look: a paper-and-forest palette and the styles shared across screens.

Every color comes from the theme, so the whole app follows the system's appearance
or the setting that overrides it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pythonnative as pn


@dataclass(frozen=True, kw_only=True)
class FieldTheme(pn.Theme):
    """The stock tokens, plus the ones a field journal needs.

    Attributes:
        accent: The warm color of map pins, active chips, and the record light.
        chip: The background of a tag or an inactive filter.
    """

    accent: str = "#B25E35"
    chip: pn.Color = "#E7E1D0"


LIGHT = FieldTheme(
    colors=pn.Colors(
        primary="#1F4D3A",
        background="#F6F3EA",
        surface="#FFFDF7",
        text="#1E2A24",
        text_secondary="#5E6B63",
        border="#E0DACB",
        error="#B3261E",
        success="#2E7D32",
        warning="#A86500",
    ),
)

DARK = FieldTheme(
    dark=True,
    accent="#E0916A",
    chip="#2A3530",
    colors=pn.Colors(
        primary="#8FCBA9",
        background="#121815",
        surface="#1B2420",
        text="#E8EDE9",
        text_secondary="#A3B1A8",
        border="#2C3833",
        error="#F2B8B5",
        success="#81C995",
        warning="#E8B15C",
    ),
)


class Styles:
    """Theme-derived styles, built once per theme by ``pn.use_styles``."""

    def __init__(self, theme: FieldTheme) -> None:
        colors, space, radii, text = theme.colors, theme.spacing, theme.radii, theme.typography
        self.colors = colors
        self.accent = theme.accent
        self.screen = pn.style(flex=1, background_color=colors.background)
        self.content = pn.style(padding=space.md, gap=space.md)
        self.title: pn.Style = {**text.title, "color": colors.text}
        self.heading: pn.Style = {**text.heading, "color": colors.text}
        self.body: pn.Style = {**text.body, "color": colors.text}
        self.label: pn.Style = {**text.label, "color": colors.text}
        self.caption: pn.Style = {**text.caption, "color": colors.text_secondary}
        self.error_text: pn.Style = {**text.caption, "color": colors.error}
        self.section_title: pn.Style = {**text.caption, "font_weight": "600", "color": colors.text_secondary}
        self.header = pn.style(
            flex_direction="row",
            align_items="center",
            justify_content="space_between",
            padding_horizontal=space.md,
            padding_top=space.sm,
            padding_bottom=space.sm,
        )
        self.card = pn.style(
            padding=space.md,
            gap=space.sm,
            background_color=colors.surface,
            border_radius=radii.lg,
            border_width=1,
            border_color=colors.border,
        )
        self.field = pn.style(
            padding=12,
            border_radius=radii.md,
            border_width=1,
            border_color=colors.border,
            background_color=colors.surface,
            color=colors.text,
            font_size=16,
        )
        self.notes_field = pn.style(min_height=160)
        self.row = pn.style(flex_direction="row", align_items="center", gap=space.sm)
        self.spread = pn.style(
            flex_direction="row", align_items="center", justify_content="space_between", gap=space.sm
        )
        self.wrap = pn.style(flex_direction="row", flex_wrap="wrap", gap=space.sm)
        self.grow = pn.style(flex=1)
        self.chip = pn.style(
            padding_horizontal=12,
            padding_vertical=6,
            border_radius=radii.full,
            background_color=theme.chip,
        )
        self.chip_active: pn.Style = {**self.chip, "background_color": colors.primary}
        self.chip_text: pn.Style = {**text.caption, "color": colors.text}
        self.chip_text_active: pn.Style = {**text.caption, "color": colors.surface}
        self.action = pn.style(
            flex_direction="row",
            align_items="center",
            gap=6,
            padding_horizontal=12,
            padding_vertical=10,
            border_radius=radii.md,
            background_color=theme.chip,
        )
        self.primary_action = pn.style(
            flex_direction="row",
            align_items="center",
            justify_content="center",
            gap=6,
            padding_horizontal=16,
            padding_vertical=12,
            border_radius=radii.md,
            background_color=colors.primary,
        )
        self.primary_text: pn.Style = {**text.label, "color": colors.surface}
        self.banner = pn.style(
            flex_direction="row", align_items="center", gap=space.sm, padding=12, border_radius=radii.md
        )
        self.thumbnail = pn.style(
            width=64, height=64, border_radius=radii.md, background_color=theme.chip, overflow="hidden"
        )
        self.photo = pn.style(
            width=104, height=104, border_radius=radii.md, background_color=theme.chip, overflow="hidden"
        )
        self.tile = pn.style(
            width=104,
            height=104,
            border_radius=radii.md,
            background_color=theme.chip,
            align_items="center",
            justify_content="center",
            gap=4,
        )
        self.entry_row = pn.style(
            flex_direction="row",
            gap=12,
            padding=space.md,
            background_color=colors.surface,
            border_bottom_width=1,
            border_color=colors.border,
        )
        self.entry_row_column: pn.Style = {**self.entry_row, "flex_direction": "column", "gap": 4}
        self.empty = pn.style(padding=space.xl, gap=space.sm, align_items="center")
        self.center = pn.style(flex=1, align_items="center", justify_content="center", gap=space.md, padding=space.lg)
        self.center_text: pn.Style = {**text.body, "color": colors.text_secondary, "text_align": "center"}
