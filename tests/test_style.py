"""Unit tests for StyleSheet, resolve_style, theming, and typed Style."""

from pythonnative.style import (
    DEFAULT_DARK_THEME,
    DEFAULT_LIGHT_THEME,
    Style,
    StyleSheet,
    ThemeContext,
    resolve_style,
    style,
)


def test_resolve_style_none() -> None:
    assert resolve_style(None) == {}


def test_resolve_style_dict() -> None:
    result = resolve_style({"font_size": 20, "color": "#000"})
    assert result == {"font_size": 20, "color": "#000"}


def test_resolve_style_list() -> None:
    base = {"font_size": 16, "color": "#000"}
    override = {"color": "#FFF", "bold": True}
    result = resolve_style([base, override])
    assert result == {"font_size": 16, "color": "#FFF", "bold": True}


def test_resolve_style_list_with_none_entries() -> None:
    result = resolve_style([None, {"a": 1}, None, {"b": 2}])
    assert result == {"a": 1, "b": 2}


def test_stylesheet_create() -> None:
    styles = StyleSheet.create(
        heading={"font_size": 28, "bold": True},
        body={"font_size": 16},
    )
    assert "heading" in styles
    assert styles["heading"]["font_size"] == 28
    assert styles["body"]["font_size"] == 16


def test_stylesheet_compose() -> None:
    base = {"font_size": 16, "color": "#000"}
    override = {"color": "#FFF", "bold": True}
    merged = StyleSheet.compose(base, override)
    assert merged["font_size"] == 16
    assert merged["color"] == "#FFF"
    assert merged["bold"] is True


def test_stylesheet_compose_none_safe() -> None:
    result = StyleSheet.compose(None, {"a": 1}, None)
    assert result == {"a": 1}


def test_stylesheet_flatten_dict() -> None:
    result = StyleSheet.flatten({"font_size": 20})
    assert result == {"font_size": 20}


def test_stylesheet_flatten_list() -> None:
    result = StyleSheet.flatten([{"a": 1}, {"b": 2}])
    assert result == {"a": 1, "b": 2}


def test_stylesheet_flatten_none() -> None:
    result = StyleSheet.flatten(None)
    assert result == {}


def test_theme_context_defaults_to_follow_system_sentinel() -> None:
    # Without a Provider, the raw context value is the follow-system
    # sentinel; `use_theme` resolves it against the color scheme.
    from pythonnative.style import _FOLLOW_SYSTEM_THEME

    assert ThemeContext._current() is _FOLLOW_SYSTEM_THEME


def test_light_and_dark_themes_differ() -> None:
    assert DEFAULT_LIGHT_THEME["background_color"] != DEFAULT_DARK_THEME["background_color"]
    assert DEFAULT_LIGHT_THEME["text_color"] != DEFAULT_DARK_THEME["text_color"]


# ---------------------------------------------------------------------------
# Typed Style + style() helper
# ---------------------------------------------------------------------------


def test_style_helper_returns_dict() -> None:
    s = style(font_size=18, color="#FF0000")
    assert s == {"font_size": 18, "color": "#FF0000"}
    assert isinstance(s, dict)


def test_style_helper_empty() -> None:
    assert style() == {}


def test_style_typeddict_is_runtime_dict() -> None:
    """Style is a TypedDict: at runtime values are plain dicts."""
    title: Style = {"font_size": 24, "bold": True, "color": "#000"}
    assert isinstance(title, dict)
    # ``Style`` is total=False so any subset is valid; here we just want
    # to confirm the values flow through resolve_style unchanged.
    assert resolve_style(title) == title


def test_style_helper_used_with_text_factory() -> None:
    from pythonnative.components import Text

    el = Text("Hello", style=style(font_size=18, bold=True))
    assert el.props["text"] == "Hello"
    assert el.props["font_size"] == 18
    assert el.props["bold"] is True


def test_style_helper_used_with_view_factory() -> None:
    from pythonnative.components import View

    el = View(style=style(padding=16, background_color="#fff"))
    assert el.props["padding"] == 16
    assert el.props["background_color"] == "#fff"
    assert el.props["flex_direction"] == "column"


def test_stylesheet_compose_flattens_lists() -> None:
    base = style(font_size=16, color="#000")
    override = style(color="#FFF", bold=True)
    merged = StyleSheet.compose([base, override])
    assert merged["font_size"] == 16
    assert merged["color"] == "#FFF"
    assert merged["bold"] is True


def test_stylesheet_compose_mixed_dict_and_list() -> None:
    merged = StyleSheet.compose(
        style(font_size=14),
        [None, style(color="#0A84FF")],
        style(bold=True),
    )
    assert merged == {"font_size": 14, "color": "#0A84FF", "bold": True}


def test_stylesheet_absolute_fill() -> None:
    fill = StyleSheet.absolute_fill()
    assert fill == {"position": "absolute", "top": 0, "right": 0, "bottom": 0, "left": 0}


def test_stylesheet_absolute_fill_returns_fresh_dict() -> None:
    fill_a = StyleSheet.absolute_fill()
    fill_b = StyleSheet.absolute_fill()
    fill_a["top"] = 99
    assert fill_b["top"] == 0


def test_resolve_style_list_with_typed_styles() -> None:
    """resolve_style accepts a list mixing Style TypedDict entries and ``None``."""
    base: Style = {"font_size": 16}
    override: Style = {"color": "#FFF"}
    result = resolve_style([base, None, override, None])
    assert result == {"font_size": 16, "color": "#FFF"}


def test_resolve_style_returns_fresh_dict() -> None:
    """resolve_style never mutates the caller's dict."""
    src = {"font_size": 16}
    out = resolve_style(src)
    out["font_size"] = 99
    assert src["font_size"] == 16
