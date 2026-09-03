"""Unit tests for the appearance module, use_color_scheme, and use_theme."""

from __future__ import annotations

from typing import Any, Dict, Generator, List

import pytest

from pythonnative import appearance
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.hooks import use_color_scheme
from pythonnative.reconciler import Reconciler
from pythonnative.style import (
    DEFAULT_DARK_THEME,
    DEFAULT_LIGHT_THEME,
    ThemeContext,
    default_theme,
    use_theme,
)
from pythonnative.testing import FakeBackend


@pytest.fixture(autouse=True)
def _reset_appearance() -> Generator[None, None, None]:
    appearance.reset_color_scheme()
    yield
    appearance.reset_color_scheme()


# ======================================================================
# appearance module
# ======================================================================


def test_default_scheme_is_light() -> None:
    assert appearance.get_color_scheme() == "light"
    assert appearance.get_system_color_scheme() == "light"


def test_system_scheme_publish_and_read() -> None:
    appearance.set_system_color_scheme("dark")
    assert appearance.get_color_scheme() == "dark"
    assert appearance.get_system_color_scheme() == "dark"


def test_invalid_scheme_ignored() -> None:
    appearance.set_system_color_scheme("sepia")
    assert appearance.get_color_scheme() == "light"
    appearance.set_color_scheme("sepia")
    assert appearance.get_color_scheme() == "light"


def test_override_wins_over_system() -> None:
    appearance.set_system_color_scheme("dark")
    appearance.set_color_scheme("light")
    assert appearance.get_color_scheme() == "light"
    assert appearance.get_system_color_scheme() == "dark"
    appearance.set_color_scheme(None)
    assert appearance.get_color_scheme() == "dark"


def test_subscribers_fire_only_on_effective_change() -> None:
    calls: List[int] = []
    unsub = appearance.subscribe(lambda: calls.append(1))
    try:
        appearance.set_system_color_scheme("dark")
        assert len(calls) == 1
        # Override to the same effective value: no notification.
        appearance.set_color_scheme("dark")
        assert len(calls) == 1
        # System flips underneath the override: effective unchanged.
        appearance.set_system_color_scheme("light")
        assert len(calls) == 1
        # Clearing the override now changes the effective value.
        appearance.set_color_scheme(None)
        assert len(calls) == 2
    finally:
        unsub()


def test_unsubscribe_stops_notifications() -> None:
    calls: List[int] = []
    unsub = appearance.subscribe(lambda: calls.append(1))
    unsub()
    appearance.set_system_color_scheme("dark")
    assert calls == []


# ======================================================================
# use_color_scheme
# ======================================================================


def test_use_color_scheme_returns_current_value() -> None:
    appearance.set_system_color_scheme("dark")
    seen: List[str] = []

    @component
    def comp() -> Element:
        seen.append(use_color_scheme())
        return Element("Text", {"text": "ok"}, [])

    Reconciler(FakeBackend()).mount(comp())
    assert seen[0] == "dark"


def test_use_color_scheme_re_renders_on_change() -> None:
    seen: List[str] = []

    @component
    def comp() -> Element:
        seen.append(use_color_scheme())
        return Element("Text", {"text": "ok"}, [])

    rec = Reconciler(FakeBackend())
    rec.on_render_requested = lambda: None
    rec.mount(comp())
    before = len(seen)

    appearance.set_system_color_scheme("dark")
    rec.flush_dirty()
    assert len(seen) > before
    assert seen[-1] == "dark"


def test_use_color_scheme_outside_component_raises() -> None:
    with pytest.raises(RuntimeError):
        use_color_scheme()


# ======================================================================
# use_theme / default_theme
# ======================================================================


def test_default_theme_selects_by_scheme() -> None:
    assert default_theme("light") is DEFAULT_LIGHT_THEME
    assert default_theme("dark") is DEFAULT_DARK_THEME
    assert default_theme("unknown") is DEFAULT_LIGHT_THEME


def test_use_theme_follows_system_scheme() -> None:
    seen: List[Dict[str, Any]] = []

    @component
    def comp() -> Element:
        seen.append(use_theme())
        return Element("Text", {"text": "ok"}, [])

    rec = Reconciler(FakeBackend())
    rec.on_render_requested = lambda: None
    rec.mount(comp())
    assert seen[-1] is DEFAULT_LIGHT_THEME

    appearance.set_system_color_scheme("dark")
    rec.flush_dirty()
    assert seen[-1] is DEFAULT_DARK_THEME


def test_use_theme_provider_pins_explicit_theme() -> None:
    custom = {"text_color": "#ABCDEF"}
    seen: List[Dict[str, Any]] = []

    @component
    def consumer() -> Element:
        seen.append(use_theme())
        return Element("Text", {"text": "ok"}, [])

    @component
    def app() -> Element:
        return ThemeContext.Provider(custom, consumer())

    rec = Reconciler(FakeBackend())
    rec.on_render_requested = lambda: None
    rec.mount(app())
    assert seen[-1] is custom

    # A scheme flip must not displace an explicitly provided theme.
    appearance.set_system_color_scheme("dark")
    rec.flush_dirty()
    assert seen[-1] is custom
