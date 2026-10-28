"""Tests for the theme (pn.Theme, ThemeProvider, use_theme, use_styles) and pn.StyleSheet."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, replace
from typing import Any, Iterator, List

import pytest

import pythonnative as pn
from pythonnative import appearance, diagnostics
from pythonnative.hooks import StateSetter
from pythonnative.testing import FakeView, render


@pytest.fixture(autouse=True)
def _light_scheme() -> Iterator[None]:
    """Start every test with the light scheme and drop any app override afterwards."""
    appearance.reset_color_scheme()
    yield
    appearance.reset_color_scheme()


@dataclass(frozen=True, kw_only=True)
class BrandTheme(pn.Theme):
    accent: pn.Color = "#FF2D55"


BRAND_LIGHT = BrandTheme(colors=replace(pn.LIGHT_THEME.colors, primary="#5B21B6"))
BRAND_DARK = BrandTheme(dark=True, colors=replace(pn.DARK_THEME.colors, primary="#A78BFA"), accent="#FF6482")


def _theme_probe(seen: List[pn.Theme]) -> pn.Component[[]]:
    @pn.component
    def Probe() -> pn.Node:
        theme = pn.use_theme()
        seen.append(theme)
        return pn.Text(str(theme.colors.primary))

    return Probe


# ======================================================================
# Theme values
# ======================================================================


def test_token_defaults() -> None:
    assert pn.Spacing() == pn.Spacing(xs=4, sm=8, md=16, lg=24, xl=32)
    assert pn.Radii() == pn.Radii(sm=4, md=8, lg=16, full=9999)
    typography = pn.Typography()
    assert typography.title == {"font_size": 28, "font_weight": "700"}
    assert typography.body == {"font_size": 16}
    assert {f.name for f in dataclasses.fields(pn.Colors)} == {
        "primary",
        "background",
        "surface",
        "text",
        "text_secondary",
        "border",
        "error",
        "success",
        "warning",
    }


def test_typography_defaults_are_not_shared_between_instances() -> None:
    first = pn.Typography()
    second = pn.Typography()
    assert first.title == second.title
    assert first.title is not second.title


def test_builtin_themes() -> None:
    assert pn.LIGHT_THEME.dark is False
    assert pn.DARK_THEME.dark is True
    assert pn.LIGHT_THEME.colors.background != pn.DARK_THEME.colors.background
    assert pn.LIGHT_THEME.spacing == pn.Spacing()
    assert pn.DARK_THEME.radii == pn.Radii()


def test_theme_is_frozen_and_keyword_only() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(pn.LIGHT_THEME, "dark", True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(pn.LIGHT_THEME.colors, "primary", "#000000")
    theme_type: Any = pn.Theme
    with pytest.raises(TypeError):
        theme_type(False, pn.LIGHT_THEME.colors)


def test_theme_can_be_subclassed_with_extra_tokens() -> None:
    assert isinstance(BRAND_LIGHT, pn.Theme)
    assert BRAND_LIGHT.accent == "#FF2D55"
    assert BRAND_DARK.accent == "#FF6482"
    assert BRAND_LIGHT.spacing == pn.Spacing()
    derived = replace(BRAND_LIGHT, accent="#000000")
    assert isinstance(derived, BrandTheme)
    assert derived.colors == BRAND_LIGHT.colors


# ======================================================================
# Default theme and ThemeProvider
# ======================================================================


def test_default_theme_follows_the_color_scheme() -> None:
    seen: List[pn.Theme] = []
    result = render(_theme_probe(seen)())
    assert seen[-1] is pn.LIGHT_THEME

    result.act(lambda: appearance.set_color_scheme("dark"))
    assert seen[-1] is pn.DARK_THEME
    assert result.text() == [pn.DARK_THEME.colors.primary]

    result.act(lambda: appearance.set_color_scheme(None))
    assert seen[-1] is pn.LIGHT_THEME


def test_default_theme_follows_the_system_scheme() -> None:
    appearance.set_system_color_scheme("dark")
    seen: List[pn.Theme] = []
    render(_theme_probe(seen)())
    assert seen[-1] is pn.DARK_THEME


def test_theme_provider_picks_by_scheme() -> None:
    seen: List[pn.Theme] = []
    result = render(pn.ThemeProvider(_theme_probe(seen)(), light=BRAND_LIGHT, dark=BRAND_DARK))
    assert seen[-1] is BRAND_LIGHT

    result.act(lambda: appearance.set_color_scheme("dark"))
    assert seen[-1] is BRAND_DARK
    assert result.text() == ["#A78BFA"]


def test_theme_provider_defaults_to_the_builtin_pair() -> None:
    seen: List[pn.Theme] = []
    result = render(pn.ThemeProvider(_theme_probe(seen)()))
    assert seen[-1] is pn.LIGHT_THEME
    result.act(lambda: appearance.set_color_scheme("dark"))
    assert seen[-1] is pn.DARK_THEME


def test_theme_provider_with_the_same_theme_twice_pins_it() -> None:
    seen: List[pn.Theme] = []
    result = render(pn.ThemeProvider(_theme_probe(seen)(), light=BRAND_DARK, dark=BRAND_DARK))
    assert seen[-1] is BRAND_DARK

    renders = len(seen)
    result.act(lambda: appearance.set_color_scheme("dark"))
    assert seen[-1] is BRAND_DARK
    result.act(lambda: appearance.set_color_scheme("light"))
    assert seen[-1] is BRAND_DARK
    assert set(map(id, seen[renders:])) <= {id(BRAND_DARK)}


def test_nested_theme_providers_innermost_wins() -> None:
    seen: List[pn.Theme] = []
    render(
        pn.ThemeProvider(
            pn.ThemeProvider(_theme_probe(seen)(), light=BRAND_DARK, dark=BRAND_DARK),
            light=BRAND_LIGHT,
            dark=BRAND_LIGHT,
        )
    )
    assert seen[-1] is BRAND_DARK


def test_use_theme_with_a_subclass_returns_it() -> None:
    accents: List[pn.Color] = []

    @pn.component
    def Accent() -> pn.Node:
        theme = pn.use_theme(BrandTheme)
        accents.append(theme.accent)
        return pn.Text(theme.accent)

    result = render(pn.ThemeProvider(Accent(), light=BRAND_LIGHT, dark=BRAND_DARK))
    assert result.text() == ["#FF2D55"]
    result.act(lambda: appearance.set_color_scheme("dark"))
    assert accents == ["#FF2D55", "#FF6482"]


def test_use_theme_with_a_subclass_raises_without_a_matching_provider() -> None:
    @pn.component
    def Accent() -> pn.Node:
        return pn.Text(pn.use_theme(BrandTheme).accent)

    with pytest.raises(TypeError, match="BrandTheme"):
        render(Accent())

    with pytest.raises(TypeError, match="ThemeProvider"):
        render(pn.ThemeProvider(Accent(), light=pn.LIGHT_THEME, dark=pn.DARK_THEME))


def test_use_theme_with_the_base_class_accepts_any_theme() -> None:
    seen: List[pn.Theme] = []

    @pn.component
    def Probe() -> pn.Node:
        seen.append(pn.use_theme(pn.Theme))
        return None

    render(pn.ThemeProvider(Probe(), light=BRAND_LIGHT, dark=BRAND_DARK))
    assert seen == [BRAND_LIGHT]


# ======================================================================
# use_styles
# ======================================================================


class CardStyles:
    calls: List[pn.Theme] = []

    def __init__(self, theme: pn.Theme) -> None:
        CardStyles.calls.append(theme)
        self.card = pn.style(background_color=theme.colors.surface, border_radius=theme.radii.md)
        self.title = theme.typography.heading


@pytest.fixture
def card_styles() -> Iterator[List[pn.Theme]]:
    CardStyles.calls = []
    yield CardStyles.calls
    CardStyles.calls = []


def test_use_styles_is_memoized_per_theme(card_styles: List[pn.Theme]) -> None:
    setters: List[StateSetter[int]] = []
    backgrounds: List[Any] = []

    @pn.component
    def Card() -> pn.Node:
        tick, set_tick = pn.use_state(0)
        setters.append(set_tick)
        styles = pn.use_styles(CardStyles)
        backgrounds.append(styles.card["background_color"])
        return pn.View(pn.Text(str(tick), style=styles.title), style=styles.card)

    result = render(Card())
    for n in range(1, 4):
        result.act(lambda n=n: setters[-1](n))  # type: ignore[misc]

    assert len(backgrounds) == 4
    assert card_styles == [pn.LIGHT_THEME]

    result.act(lambda: appearance.set_color_scheme("dark"))
    assert card_styles == [pn.LIGHT_THEME, pn.DARK_THEME]
    assert backgrounds[-1] == pn.DARK_THEME.colors.surface

    result.act(lambda: setters[-1](10))
    assert len(card_styles) == 2


def test_use_styles_accepts_a_plain_function() -> None:
    calls: List[pn.Theme] = []

    def styles_for(theme: pn.Theme) -> pn.Style:
        calls.append(theme)
        return pn.style(color=theme.colors.text)

    colors: List[Any] = []

    @pn.component
    def Label() -> pn.Node:
        style = pn.use_styles(styles_for)
        colors.append(style["color"])
        return pn.Text("x", style=style)

    result = render(pn.ThemeProvider(Label(), light=BRAND_LIGHT, dark=BRAND_DARK))
    assert colors == [BRAND_LIGHT.colors.text]
    result.act(lambda: appearance.set_color_scheme("dark"))
    assert colors[-1] == BRAND_DARK.colors.text
    assert calls == [BRAND_LIGHT, BRAND_DARK]


# ======================================================================
# StyleSheet
# ======================================================================


class Styles(pn.StyleSheet):
    card = pn.style(padding=16, border_radius=12)
    title = pn.style(font_size=17, font_weight="600")


def test_stylesheet_attributes_are_the_style_dicts() -> None:
    assert Styles.card == {"padding": 16, "border_radius": 12}
    assert isinstance(Styles.title, dict)
    assert Styles.title["font_size"] == 17


def test_stylesheet_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="namespace"):
        Styles()
    with pytest.raises(TypeError):
        pn.StyleSheet()


def test_stylesheet_warns_once_about_an_unknown_key_in_dev_mode() -> None:
    diagnostics.clear_warnings()
    bad: Any = {"colour": "red", "padding": 4}

    class Bad(pn.StyleSheet):
        label = bad
        _private = {"not_checked": 1}

    warnings = diagnostics.get_warnings()
    assert len(warnings) == 1
    assert "'colour'" in warnings[0]
    assert "Bad.label" in warnings[0]
    assert "'color'" in warnings[0]  # did-you-mean suggestion
    assert Bad.label is bad


def test_stylesheet_warns_about_a_bad_enum_value() -> None:
    diagnostics.clear_warnings()
    bad: Any = {"position": "fixed"}

    class Positions(pn.StyleSheet):
        overlay = bad

    warnings = diagnostics.get_warnings()
    assert len(warnings) == 1
    assert "'fixed'" in warnings[0]


def test_stylesheet_does_not_warn_outside_dev_mode() -> None:
    diagnostics.clear_warnings()
    diagnostics.set_dev_mode(False)
    try:
        bad: Any = {"colour": "red"}

        class Quiet(pn.StyleSheet):
            label = bad

    finally:
        diagnostics.set_dev_mode(True)
    assert diagnostics.get_warnings() == []
    assert Quiet.label == {"colour": "red"}


def test_valid_stylesheet_does_not_warn() -> None:
    diagnostics.clear_warnings()

    class Good(pn.StyleSheet):
        row = pn.style(padding=16, gap=6, border_bottom_width=1)
        fill = pn.ABSOLUTE_FILL

    assert diagnostics.get_warnings() == []
    assert Good.fill is pn.ABSOLUTE_FILL


def test_absolute_fill() -> None:
    assert pn.ABSOLUTE_FILL == {"position": "absolute", "top": 0, "right": 0, "bottom": 0, "left": 0}


def test_style_lists_compose_with_later_entries_winning() -> None:
    resolved = pn.resolve_style([Styles.card, None, {"padding": 4, "opacity": 0.5}])
    assert resolved == {"padding": 4, "border_radius": 12, "opacity": 0.5}
    assert Styles.card == {"padding": 16, "border_radius": 12}  # inputs aren't mutated


def test_style_list_reaches_the_native_view() -> None:
    result = render(pn.View(pn.Text("x"), style=[Styles.card, pn.ABSOLUTE_FILL], test_id="box"))
    props = result.get_by_test_id("box").props
    assert props["padding"] == 16
    assert props["position"] == "absolute"
    assert props["top"] == 0


# ======================================================================
# Navigator chrome
# ======================================================================


@pn.component
def HomeScreen() -> pn.Node:
    return pn.Text("home body")


Root = pn.StackNavigator(pn.Screen(HomeScreen, title="Home"))

CUSTOM = replace(
    pn.LIGHT_THEME,
    colors=replace(pn.LIGHT_THEME.colors, surface="#123456", text="#ABCDEF", border="#FEDCBA"),
)


def _header(result: Any) -> FakeView:
    title = result.get_by_text("Home")
    header = title.parent
    assert header is not None
    return header


def test_stack_header_uses_theme_colors() -> None:
    result = render(pn.ThemeProvider(pn.NavigationContainer(Root), light=CUSTOM, dark=CUSTOM))

    header = _header(result)
    assert header.props["background_color"] == "#123456"
    assert header.props["border_color"] == "#FEDCBA"
    assert result.get_by_text("Home").props["color"] == "#ABCDEF"
    assert result.get_by_text("home body")


def test_stack_header_follows_the_default_theme() -> None:
    result = render(pn.NavigationContainer(Root))
    assert _header(result).props["background_color"] == pn.LIGHT_THEME.colors.surface

    result.act(lambda: appearance.set_color_scheme("dark"))
    assert _header(result).props["background_color"] == pn.DARK_THEME.colors.surface
    assert result.get_by_text("Home").props["color"] == pn.DARK_THEME.colors.text
