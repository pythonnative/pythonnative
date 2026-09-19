"""Render every ``examples/e2e-suite`` demo headlessly.

The Maestro suite only runs on a booted emulator or simulator, so this
module is the fast guard that keeps the demo app importable and every
registered demo screen renderable: the root ``App`` mounts under the
fake backend, the app-wide :class:`~pythonnative.NavigationRef` opens
each demo by its registry id, and the screen's ``"Demo: <title>"``
anchor (the same text the flows wait on) must appear. A few demos whose
flows assert computed values are also driven here so the expected values
in ``tests/e2e/flows`` are pinned by the reconciler rather than by hand.
"""

from __future__ import annotations

import importlib
import re
import sys
import types
from pathlib import Path
from typing import Any, Iterator

import pytest

import pythonnative as pn
from pythonnative import appearance
from pythonnative.testing import RenderResult, render

_SUITE_DIR = Path(__file__).parents[1] / "examples" / "e2e-suite"

# Parametrize from the registry *text* rather than by importing it: the app's
# modules live under the plain ``app`` package name, and leaving them in
# ``sys.modules`` from collection time onward would leak into unrelated tests
# (``tests/test_devclient.py`` derives its reload list from ``sys.modules``).
# The same regex drives ``scripts/check-e2e-coverage.py``.
_DEMO_IDS = re.findall(r'DemoEntry\(\s*"([^"]+)"', (_SUITE_DIR / "app" / "registry.py").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def suite_app() -> Iterator[types.ModuleType]:
    """Import ``examples/e2e-suite`` once for this module and forget it afterwards."""
    sys.path.insert(0, str(_SUITE_DIR))
    try:
        yield importlib.import_module("app.main")
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                sys.modules.pop(name, None)
        sys.path.remove(str(_SUITE_DIR))


@pytest.fixture
def suite(suite_app: types.ModuleType) -> Iterator[RenderResult]:
    appearance.reset_color_scheme()
    result = render(suite_app.App())
    try:
        yield result
    finally:
        result.unmount()
        appearance.reset_color_scheme()


def _registry() -> Any:
    return importlib.import_module("app.registry")


def _nav_ref() -> pn.NavigationRef:
    return importlib.import_module("app.navigation_ref").nav_ref


def _open(result: RenderResult, demo_id: str) -> Any:
    demo = next(d for d in _registry().DEMOS if d.id == demo_id)
    _nav_ref().navigate(demo.id)
    result.settle()
    assert result.get_by_text(f"Demo: {demo.title}")
    return demo


def test_home_lists_every_category(suite: RenderResult) -> None:
    assert suite.get_by_text("E2E Suite home")
    for demo in _registry().DEMOS:
        assert suite.get_by_text(f"Open {demo.category}")
    assert _nav_ref().is_ready()


def test_registry_ids_and_features_are_unique(suite_app: types.ModuleType) -> None:
    demos = _registry().DEMOS
    ids = [demo.id for demo in demos]
    assert ids == _DEMO_IDS
    assert len(ids) == len(set(ids))
    assert all(demo.id == demo.id.lower() and " " not in demo.id for demo in demos)


@pytest.mark.parametrize("demo_id", _DEMO_IDS)
def test_every_demo_renders(suite: RenderResult, demo_id: str) -> None:
    _open(suite, demo_id)
    assert suite.get_by_text("Back to list")
    assert suite.back()
    suite.settle()
    assert suite.get_by_text("E2E Suite home")


def test_pressable_demo_press_state_and_disabled(suite: RenderResult) -> None:
    _open(suite, "pressable")
    target = suite.get_by_label("pressable-target")
    suite.press(target)
    assert suite.get_by_text("Presses: 1")
    suite.fire(target, "on_long_press")
    assert suite.get_by_text("Long presses: 1")
    suite.press(suite.get_by_text("Disable pressable"))
    assert suite.get_by_text("Disabled: yes")
    with pytest.raises(AssertionError):
        suite.press(suite.get_by_label("pressable-target"))
    assert suite.get_by_text("Presses: 1")


def test_text_demo_label_and_span_presses(suite: RenderResult) -> None:
    _open(suite, "text")
    suite.press(suite.get_by_text("Tap this whole label"))
    assert suite.get_by_text("Label presses: 1")
    span_label = suite.get_by_text("Tap this span")
    suite.fire(span_label, "on_span_press", 0)
    assert suite.get_by_text("Span presses: 1")


def test_text_input_demo_typed_events(suite: RenderResult) -> None:
    _open(suite, "text_input")
    field = suite.get_by_placeholder_text("Type your name here")
    suite.change_text(field, "Maestro")
    assert suite.get_by_text("Echo: Maestro")
    suite.fire(field, "on_key_press", pn.KeyPressEvent("o"))
    assert suite.get_by_text("Last key: o")
    suite.fire(field, "on_selection_change", pn.SelectionEvent(7, 7))
    assert suite.get_by_text("Selection: 7:7")
    suite.press(suite.get_by_text("Select all"))
    assert suite.get_by_placeholder_text("Type your name here").props["selection"] == {"start": 0, "end": 7}


def test_on_layout_demo_reports_handle_frame(suite: RenderResult) -> None:
    _open(suite, "on_layout")
    assert suite.get_by_text("Measured: 120x60")
    assert suite.get_by_text("Handle frame: 120x60")
    suite.press(suite.get_by_text("Widen box"))
    assert suite.get_by_text("Measured: 200x60")
    assert suite.get_by_text("Handle frame: 200x60")


def test_text_input_handle_demo(suite: RenderResult) -> None:
    _open(suite, "text_input_handle")
    suite.press(suite.get_by_text("Focus input"))
    assert suite.get_by_text("Focused: ON")
    assert suite.get_by_text("Handle attached: yes")
    suite.press(suite.get_by_text("Read native value"))
    suite.settle()
    assert suite.get_by_text("Native value: handle text")
    suite.press(suite.get_by_text("Clear input"))
    assert suite.get_by_text("Last call: clear")
    suite.press(suite.get_by_text("Blur input"))
    assert suite.get_by_text("Focused: OFF")


def test_scroll_view_handle_demo(suite: RenderResult) -> None:
    _open(suite, "scroll_view_handle")
    suite.press(suite.get_by_text("Handle scroll to end"))
    assert suite.get_by_text("Last call: scroll_to_end")
    assert suite.get_by_text("Handle attached: yes")
    suite.press(suite.get_by_text("Read offset"))
    suite.settle()
    assert suite.get_by_text("Offset: scrolled")
    suite.press(suite.get_by_text("Handle scroll to top"))
    suite.press(suite.get_by_text("Read offset"))
    suite.settle()
    assert suite.get_by_text("Offset: top")


def test_web_view_handle_demo(suite: RenderResult) -> None:
    _open(suite, "web_view_handle")
    suite.press(suite.get_by_text("Reload page"))
    assert suite.get_by_text("Reloads: 1")
    assert suite.get_by_text("Handle attached: yes")
    suite.press(suite.get_by_text("Evaluate JS"))
    suite.settle()
    assert suite.get_by_text("Can go back: no")
    assert suite.get_by_text("Last call: eval_js")


def test_navigation_theme_demo_switches_root_theme(suite: RenderResult) -> None:
    _open(suite, "navigation_theme")
    assert suite.get_by_text("Theme: light")
    assert suite.get_by_text("Matches preset: yes")
    suite.press(suite.get_by_text("Use dark theme"))
    assert suite.get_by_text("Theme: dark")
    assert suite.get_by_text("Matches preset: yes")
    assert suite.get_by_text(f"Card: {pn.DARK_NAVIGATION_THEME.colors.card}")
    suite.press(suite.get_by_text("Use light theme"))
    assert suite.get_by_text("Theme: light")


def test_navigation_ref_demo_drives_root_stack(suite: RenderResult) -> None:
    _open(suite, "navigation_ref")
    assert suite.get_by_text("Ref ready: yes")
    assert suite.get_by_text("Current route: navigation_ref")
    suite.press(suite.get_by_text("Navigate via ref"))
    assert suite.get_by_text("Param 'value': from-ref")
    suite.press(suite.get_by_text("Back to list"))
    assert suite.get_by_text("Demo: Navigation ref")


def test_stack_options_demo_layers_titles_and_guards_pop_to(suite: RenderResult) -> None:
    _open(suite, "stack_options")
    assert suite.get_by_text("Home!")
    assert suite.get_by_text("Focused route: Home")
    suite.press(suite.get_by_text("Push Compose"))
    assert suite.get_by_text("Grouped")
    assert suite.get_by_text("Focused route: Compose")
    suite.press(suite.get_by_text("Push Preview"))
    assert suite.get_by_text("Preview!")
    suite.press(suite.get_by_text("Push Plain"))
    assert suite.get_by_text("Nav Plain")
    assert suite.get_by_text("Depth: 4")
    suite.press(suite.get_by_text("Pop to Home"))
    assert suite.get_by_text("Focused route: Home")
    assert suite.get_by_text("Depth: 1")
    suite.press(suite.get_by_text("Push Preview"))
    assert suite.get_by_text("Focused route: Preview")
    suite.press(suite.get_by_text("Enable guard"))
    suite.press(suite.get_by_text("Pop to Home"))
    assert suite.get_by_text("Vetoes: 1")
    assert suite.get_by_text("Last veto: pop_to")
    assert suite.get_by_text("Focused route: Preview")
    suite.press(suite.get_by_text("Disable guard"))
    suite.press(suite.get_by_text("Pop to Home"))
    assert suite.get_by_text("Focused route: Home")


def test_tab_options_demo_freezes_blurred_tab(suite: RenderResult) -> None:
    _open(suite, "tab_options")
    assert suite.get_by_text("TabA body")
    assert suite.get_by_text("TabA last tick: 0")
    assert suite.get_by_text("TabB last tick: 0")
    suite.press(suite.get_by_text("Jump to TabB"))
    assert suite.get_by_text("TabB body")
    suite.press(suite.get_by_text("Advance tick"))
    assert suite.get_by_text("Tick: 1")
    assert suite.get_by_text("TabB last tick: 1")
    assert suite.get_by_text("TabA last tick: 0")
    suite.press(suite.get_by_text("Jump to TabA"))
    assert suite.get_by_text("TabA last tick: 1")
    suite.press(suite.get_by_text("Jump to Hidden"))
    assert suite.get_by_text("Hidden body")
    assert suite.query_by_type("TabBar") is None
    suite.press(suite.get_by_text("Jump to TabA"))
    assert suite.get_by_type("TabBar")


def test_presentation_demo_pushes_every_variant(suite: RenderResult) -> None:
    variants = importlib.import_module("app.screens.navigation.presentation").PRESENTATION_VARIANTS
    _open(suite, "presentation")
    for variant in variants:
        suite.press(suite.get_by_text(f"Open {variant.label}"))
        assert suite.get_by_text(f"Presented: {variant.label}")
        suite.press(suite.get_by_text("Dismiss presented"))
        assert suite.get_by_text("Demo: Presentation")
    assert suite.get_by_text(f"Opened: {len(variants)}")


def test_define_component_demo_registers_and_unregisters(suite: RenderResult) -> None:
    _open(suite, "define_component")
    assert suite.get_by_text("Factory type: E2EBadge")
    assert suite.get_by_text("Style accepted: yes")
    assert suite.get_by_text("Rejects unknown prop: yes")
    assert suite.get_by_text("Registered: yes")
    assert "E2EBadge" in pn.sdk.list_components()
    assert suite.back()
    suite.settle()
    assert "E2EBadge" not in pn.sdk.list_components()


def test_dynamic_color_demo_flips_scheme_and_restores(suite: RenderResult) -> None:
    _open(suite, "dynamic_color")
    assert suite.get_by_text("Scheme: light")
    suite.press(suite.get_by_text("Use dark scheme"))
    assert suite.get_by_text("Scheme: dark")
    assert suite.back()
    suite.settle()
    assert appearance.get_color_scheme() == "light"


def test_device_demos_read_fallback_values(suite: RenderResult) -> None:
    _open(suite, "device_info")
    assert suite.get_by_text("Platform: test")
    assert suite.back()
    _open(suite, "localization")
    assert suite.get_by_text("Has locale: yes")
    assert suite.get_by_text("Has timezone: yes")
    assert suite.back()
    _open(suite, "pixel_ratio")
    assert suite.get_by_text("Pixels match ratio: yes")
    assert suite.get_by_text("Snap within a pixel: yes")
    assert suite.back()
    _open(suite, "accessibility_info")
    suite.press(suite.get_by_text("Announce"))
    suite.press(suite.get_by_text("Focus target"))
    assert suite.get_by_text("Announcements: 1")
    assert suite.get_by_text("Focus calls: 1")
    assert suite.back()
    _open(suite, "keyboard")
    suite.press(suite.get_by_text("Dismiss keyboard"))
    assert suite.get_by_text("Dismiss calls: 1")
    assert suite.get_by_text("Keyboard visible: no")


def test_easing_and_decay_demos_complete(suite: RenderResult) -> None:
    _open(suite, "easing")
    assert suite.get_by_text("Rejects unknown easing: yes")
    assert suite.get_by_text(f"Animatable props: {len(pn.ANIMATABLE_PROPS)}")
    suite.press(suite.get_by_text("Run all curves"))
    assert suite.find_by_text("Curves run: 9", timeout=10.0)
    assert suite.get_by_text("Status: done")
    assert suite.back()
    _open(suite, "decay_animation")
    suite.press(suite.get_by_text("Fling"))
    assert suite.find_by_text("Finished: yes", timeout=10.0)
    assert suite.get_by_text("Status: done")
    assert suite.get_by_text("Settled x: 150")


def test_scroll_listeners_receive_typed_scroll_events(suite: RenderResult) -> None:
    """Every demo that scrolls reads ``ScrollEvent`` fields, never dict keys."""
    from pythonnative.events import get_event_registry

    for demo_id, readout in (
        ("collapsing_header", "Header state: collapsed"),
        ("scroll_view", "Offset y positive: yes"),
    ):
        _open(suite, demo_id)
        registry = get_event_registry()
        scrollers = [v for v in suite.get_all_by_type("ScrollView") if registry.has(v.tag, "on_scroll")]
        assert scrollers, demo_id
        payload = {"x": 0.0, "y": 240.0, "content_width": 300.0, "content_height": 2400.0}
        suite.fire(scrollers[-1], "on_scroll", {**payload, "viewport_width": 300.0, "viewport_height": 400.0})
        assert suite.get_by_text(readout), demo_id
