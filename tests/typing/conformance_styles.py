"""Typing conformance: styles, style sheets, and themes (checked by mypy, never executed)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pythonnative as pn


class Styles(pn.StyleSheet):
    card = pn.style(padding=16, border_radius=12)
    title = pn.style(font_size=17, font_weight="600")


@dataclass(frozen=True, kw_only=True)
class BrandTheme(pn.Theme):
    accent: pn.Color = "#FF2D55"


LIGHT = BrandTheme(colors=replace(pn.LIGHT_THEME.colors, primary="#5B21B6"))
DARK = BrandTheme(dark=True, colors=pn.DARK_THEME.colors, accent="#FF6482")


class CardStyles:
    def __init__(self, theme: pn.Theme) -> None:
        self.card = pn.style(background_color=theme.colors.surface, border_radius=theme.radii.md)
        self.title = theme.typography.heading


@pn.component
def Card(title: str) -> pn.Node:
    styles = pn.use_styles(CardStyles)
    theme = pn.use_theme(BrandTheme)
    accent: pn.Color = theme.accent
    base = pn.use_theme()
    base.accent  # type: ignore[attr-defined]
    styles.missing  # type: ignore[attr-defined]
    return pn.View(
        pn.Text(title, style=[Styles.title, styles.title, {"color": accent}, None]),
        style=[Styles.card, styles.card, pn.ABSOLUTE_FILL],
    )


app = pn.ThemeProvider(Card(title="x"), light=LIGHT, dark=DARK)
spacing: float = pn.LIGHT_THEME.spacing.md

Styles.titel  # type: ignore[attr-defined]
pn.style(colour="red")  # type: ignore[call-arg]
pn.style(opacity="half")  # type: ignore[arg-type]
pn.style(flex_direction="diagonal")  # type: ignore[arg-type]
misspelled: pn.Style = {"colour": "red"}  # type: ignore[typeddict-unknown-key]
wrong_value: pn.Style = {"opacity": "half"}  # type: ignore[typeddict-item]
pn.Theme(dark=True)  # type: ignore[call-arg]
pn.LIGHT_THEME.dark = True  # type: ignore[misc]
pn.ThemeProvider(Card(title="x"), light="light")  # type: ignore[arg-type]
