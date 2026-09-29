"""Tests for navigation themes: presets, the hook, container override, and themed chrome."""

import dataclasses
from typing import Any, Dict, Iterator

import pytest

from pythonnative import appearance
from pythonnative.component import component
from pythonnative.components import Column, Text
from pythonnative.navigation import (
    DARK_NAVIGATION_THEME,
    DEFAULT_NAVIGATION_THEME,
    NavigationColors,
    NavigationContainer,
    NavigationTheme,
    create_drawer_navigator,
    create_stack_navigator,
    create_tab_navigator,
    use_navigation,
    use_navigation_theme,
)
from pythonnative.testing import FakeHost, render, render_hook


@pytest.fixture(autouse=True)
def _light_scheme() -> Iterator[None]:
    appearance.reset_color_scheme()
    yield
    appearance.reset_color_scheme()


def _capturing_screen(label: str, box: Dict[str, Any]) -> Any:
    @component
    def Screen() -> Any:
        box[label] = use_navigation()
        return Column(Text(label))

    return Screen


# ======================================================================
# Records and presets
# ======================================================================


def test_theme_presets_are_frozen_records_with_six_colors() -> None:
    assert DEFAULT_NAVIGATION_THEME.dark is False
    assert DARK_NAVIGATION_THEME.dark is True
    assert isinstance(DEFAULT_NAVIGATION_THEME.colors, NavigationColors)
    assert [f.name for f in dataclasses.fields(NavigationColors)] == [
        "primary",
        "background",
        "card",
        "text",
        "border",
        "notification",
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_NAVIGATION_THEME.dark = True  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_NAVIGATION_THEME.colors.primary = "#000"  # type: ignore[misc]
    brand = dataclasses.replace(
        DEFAULT_NAVIGATION_THEME,
        colors=dataclasses.replace(DEFAULT_NAVIGATION_THEME.colors, primary="#FF2D55"),
    )
    assert isinstance(brand, NavigationTheme)
    assert brand.colors.primary == "#FF2D55"
    assert brand.colors.card == DEFAULT_NAVIGATION_THEME.colors.card


# ======================================================================
# use_navigation_theme
# ======================================================================


def test_use_navigation_theme_follows_the_color_scheme_without_a_container() -> None:
    hook = render_hook(use_navigation_theme)
    assert hook.current is DEFAULT_NAVIGATION_THEME
    appearance.set_color_scheme("dark")
    hook.settle()
    assert hook.current is DARK_NAVIGATION_THEME
    appearance.set_color_scheme("light")
    hook.settle()
    assert hook.current is DEFAULT_NAVIGATION_THEME


def test_container_theme_wins_over_the_color_scheme() -> None:
    seen: list = []

    @component
    def Probe() -> Any:
        seen.append(use_navigation_theme())
        return Text("probe")

    appearance.set_color_scheme("dark")
    render(NavigationContainer(Probe(), theme=DEFAULT_NAVIGATION_THEME))
    assert seen[-1] is DEFAULT_NAVIGATION_THEME
    render(NavigationContainer(Probe()))
    assert seen[-1] is DARK_NAVIGATION_THEME


# ======================================================================
# Python-drawn chrome
# ======================================================================


def test_python_stack_header_and_back_label_use_the_theme() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    result = render(
        NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", _capturing_screen("home", box), title="Welcome"),
                Stack.Screen("Detail", _capturing_screen("detail", box), title="Detail"),
            ),
            theme=DARK_NAVIGATION_THEME,
        )
    )
    colors = DARK_NAVIGATION_THEME.colors
    title = result.get_by_text("Welcome")
    assert title.props["color"] == colors.text
    header = title.parent
    assert header.props["background_color"] == colors.card
    assert header.props["border_color"] == colors.border

    box["home"].push("Detail")
    result.settle()
    assert result.get_by_text("‹ Back").props["color"] == colors.primary


def test_python_stack_header_user_options_override_theme_defaults() -> None:
    Stack = create_stack_navigator()
    result = render(
        Stack.Navigator(
            Stack.Screen(
                "Home",
                _capturing_screen("home", {}),
                title="Welcome",
                header_style={"background_color": "#123456"},
                header_title_style={"color": "#ABCDEF"},
            )
        )
    )
    title = result.get_by_text("Welcome")
    assert title.props["color"] == "#ABCDEF"
    assert title.parent.props["background_color"] == "#123456"


def test_unknown_route_fallback_is_themed() -> None:
    # A screen definition disappears (hot reload) while its route is still in the state.
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}

    def app(*extra: Any) -> Any:
        return NavigationContainer(
            Stack.Navigator(Stack.Screen("Home", _capturing_screen("home", box)), *extra),
            theme=DARK_NAVIGATION_THEME,
        )

    result = render(app(Stack.Screen("Ghost", _capturing_screen("ghost", box), header_shown=False)))
    box["home"].push("Ghost")
    result.settle()
    assert result.get_by_text("ghost")
    result.rerender(app())
    assert result.get_by_text("Unknown route: Ghost").props["color"] == DARK_NAVIGATION_THEME.colors.text


def test_drawer_panel_and_rows_use_the_theme() -> None:
    Drawer = create_drawer_navigator()
    box: Dict[str, Any] = {}
    result = render(
        NavigationContainer(
            Drawer.Navigator(
                Drawer.Screen("Feed", _capturing_screen("feed", box), title="My Feed"),
                Drawer.Screen("Settings", _capturing_screen("settings", box), title="Settings"),
            ),
            theme=DARK_NAVIGATION_THEME,
        )
    )
    box["feed"].open_drawer()
    result.settle()
    colors = DARK_NAVIGATION_THEME.colors
    active_label = result.get_by_text("My Feed")
    inactive_label = result.get_by_text("Settings")
    assert active_label.props["color"] == colors.primary
    assert inactive_label.props["color"] == colors.text
    assert active_label.parent.props["background_color"] == colors.background
    panel = active_label.parent.parent
    assert panel.props["background_color"] == colors.card
    assert panel.props["border_color"] == colors.border


# ======================================================================
# Native Screen and TabBar defaults
# ======================================================================


def test_native_screen_props_default_header_colors_from_theme() -> None:
    Stack = create_stack_navigator()
    result = render(
        NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", _capturing_screen("home", {}), title="Home"),
            ),
            theme=DARK_NAVIGATION_THEME,
        ),
        host=FakeHost(),
    )
    colors = DARK_NAVIGATION_THEME.colors
    screen = result.get_by_type("Screen")
    assert screen.props["header_tint_color"] == colors.primary
    assert screen.props["header_style"] == {"background_color": colors.card}
    assert screen.props["header_title_style"] == {"color": colors.text}


def test_native_screen_props_keep_user_header_colors() -> None:
    Stack = create_stack_navigator()
    result = render(
        Stack.Navigator(
            Stack.Screen(
                "Home",
                _capturing_screen("home", {}),
                header_tint_color="#111111",
                header_style={"background_color": "#222222", "elevation": 2},
                header_title_style={"color": "#333333", "font_size": 20},
            ),
        ),
        host=FakeHost(),
    )
    screen = result.get_by_type("Screen")
    assert screen.props["header_tint_color"] == "#111111"
    assert screen.props["header_style"] == {"background_color": "#222222", "elevation": 2}
    assert screen.props["header_title_style"] == {"color": "#333333", "font_size": 20}


def test_tab_bar_colors_default_from_theme() -> None:
    Tab = create_tab_navigator()
    result = render(
        NavigationContainer(
            Tab.Navigator(
                Tab.Screen("Home", _capturing_screen("home", {})), Tab.Screen("Me", _capturing_screen("me", {}))
            ),
            theme=DARK_NAVIGATION_THEME,
        )
    )
    bar = result.get_by_type("TabBar")
    assert bar.props["tint_color"] == DARK_NAVIGATION_THEME.colors.primary
    assert bar.props["background_color"] == DARK_NAVIGATION_THEME.colors.card
    for key in ("inactive_tint_color", "translucent", "shows_labels"):
        assert key not in bar.props


def test_tab_bar_style_is_forwarded_to_the_native_tab_bar() -> None:
    Tab = create_tab_navigator()
    result = render(
        Tab.Navigator(
            Tab.Screen("Home", _capturing_screen("home", {})),
            Tab.Screen("Me", _capturing_screen("me", {})),
            tab_bar_style={
                "background_color": "#101010",
                "active_tint_color": "#FF2D55",
                "inactive_tint_color": "#8E8E93",
                "translucent": False,
                "show_labels": False,
            },
        )
    )
    bar = result.get_by_type("TabBar")
    assert bar.props["background_color"] == "#101010"
    assert bar.props["tint_color"] == "#FF2D55"
    assert bar.props["inactive_tint_color"] == "#8E8E93"
    assert bar.props["translucent"] is False
    assert bar.props["shows_labels"] is False
