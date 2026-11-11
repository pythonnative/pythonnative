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
from pythonnative.testing import FakeClock, RenderResult, render

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
    _nav_ref().navigate(demo.component())
    result.settle()
    assert _nav_ref().get_state().current.name == demo.id
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
    app_theme = importlib.import_module("app.app_theme")
    _open(suite, "navigation_theme")
    assert suite.get_by_text("Theme: light")
    assert suite.get_by_text("Matches preset: yes")
    suite.press(suite.get_by_text("Use dark theme"))
    assert suite.get_by_text("Theme: dark")
    assert suite.get_by_text("Preset: dark")
    assert suite.get_by_text("Matches preset: yes")
    assert suite.get_by_text(f"Surface: {app_theme.SUITE_DARK.colors.surface}")
    # The shared styles follow the provider too.
    assert suite.get_by_text("Demo: Navigation theme").props["color"] == app_theme.SUITE_DARK.colors.text
    suite.press(suite.get_by_text("Use light theme"))
    assert suite.get_by_text("Theme: light")
    assert suite.back()
    suite.settle()
    assert appearance.get_color_scheme() == appearance.get_system_color_scheme()


def test_use_theme_demo_follows_the_scheme(suite: RenderResult) -> None:
    _open(suite, "use_theme")
    suite.press(suite.get_by_text("Force light"))
    assert suite.get_by_text("Theme background: #FFFFFF")
    assert suite.get_by_text("Theme primary: #007AFF")
    suite.press(suite.get_by_text("Force dark"))
    assert suite.get_by_text("Theme background: #000000")
    assert suite.get_by_text("Theme primary: #0A84FF")
    suite.press(suite.get_by_text("Follow system"))


def test_use_store_demo_rerenders_only_the_selected_slice(suite: RenderResult) -> None:
    _open(suite, "use_store")
    assert suite.get_by_text("Items: 0")
    assert suite.get_by_text("Count renders: 1")
    assert suite.get_by_text("Note: (empty)")
    suite.press(suite.get_by_text("Add item"))
    assert suite.get_by_text("Items: 1")
    assert suite.get_by_text("Count renders: 2")
    suite.press(suite.get_by_text("Set note"))
    assert suite.get_by_text("Note: hello")
    assert suite.get_by_text("Count renders: 2")
    suite.press(suite.get_by_text("Add two"))
    assert suite.get_by_text("Items: 3")
    assert suite.get_by_text("Count renders: 3")
    suite.press(suite.get_by_text("Reset store"))
    assert suite.get_by_text("Items: 0")
    assert suite.back()
    suite.settle()
    assert importlib.import_module("app.screens.hooks.use_store").cart.get().items == ()


def test_tab_navigator_demo_reaches_the_statically_nested_stack(suite: RenderResult) -> None:
    _open(suite, "tab_navigator")
    assert suite.get_by_text("Tab Alpha body")
    suite.press(suite.get_by_text("Open Gamma detail"))
    assert suite.get_by_text("Gamma detail: 7")
    assert suite.get_by_type("TabBar").props["active_tab"] == "Gamma"
    suite.press(suite.get_by_text("Back to Gamma"))
    assert suite.get_by_text("Tab Gamma body")


def test_params_passing_demo_pushes_typed_params(suite: RenderResult) -> None:
    _open(suite, "params_passing")
    assert suite.get_by_text("Param 'value': (none)")
    suite.press(suite.get_by_text("Push value=alpha"))
    assert suite.get_by_text("Param 'value': alpha")
    assert _nav_ref().get_state().current.params == {"value": "alpha"}
    suite.press(suite.get_by_text("Push value=beta"))
    assert suite.get_by_text("Param 'value': beta")
    assert suite.back()
    suite.settle()
    assert suite.get_by_text("Param 'value': alpha")


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


def test_scroll_listeners_receive_typed_scroll_events(suite: RenderResult) -> None:
    """A Python ``on_scroll`` listener reads ``ScrollEvent`` fields, never dict keys."""
    from pythonnative.events import get_event_registry

    _open(suite, "scroll_view")
    registry = get_event_registry()
    scrollers = [v for v in suite.get_all_by_type("ScrollView") if registry.has(v.tag, "on_scroll")]
    assert scrollers
    payload = {"x": 0.0, "y": 240.0, "content_width": 300.0, "content_height": 2400.0}
    suite.fire(scrollers[-1], "on_scroll", {**payload, "viewport_width": 300.0, "viewport_height": 400.0})
    assert suite.get_by_text("Offset y positive: yes")


# ----------------------------------------------------------------------
# Motion: the virtual clock drives the core's frame clock, so awaited
# animations, worklets, and layout animations run here as on a device.
# ----------------------------------------------------------------------


def _advance(suite: RenderResult, clock: FakeClock, seconds: float = 2.0) -> None:
    clock.advance(seconds)
    suite.settle()


def _box(suite: RenderResult, label: str) -> Any:
    """The animated view around a demo's ``label`` text."""
    return suite.get_by_text(label).parent


def test_with_timing_demo_awaits_and_reports_interruption(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "with_timing")
    box = _box(suite, "timing-box label")
    assert suite.presented_style(box)["opacity"] == 0.2
    suite.press(suite.get_by_text("Run timing"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Status: done")
    assert suite.get_by_text("Finished: yes")
    assert suite.presented_style(box)["opacity"] == 1.0
    suite.press(suite.get_by_text("Interrupt timing"))
    _advance(suite, pn_clock, 3.0)
    assert suite.get_by_text("Status: interrupted")
    assert suite.get_by_text("Finished: no")
    assert suite.presented_style(box)["opacity"] == 0.5
    suite.press(suite.get_by_text("Reset"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Status: idle")


def test_easing_demo_runs_every_curve(pn_clock: FakeClock, suite: RenderResult) -> None:
    curves = importlib.import_module("app.screens.motion.easing")._CURVES
    _open(suite, "easing")
    assert suite.get_by_text("Rejects unknown easing: yes")
    suite.press(suite.get_by_text("Run all curves"))
    _advance(suite, pn_clock, 10.0)
    assert suite.get_by_text(f"Curves run: {len(curves)}")
    assert suite.get_by_text("Status: done")
    assert suite.get_by_text("Last curve: custom")


def test_spring_and_decay_demos_settle_where_expected(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "with_spring")
    suite.press(suite.get_by_text("Run spring"))
    _advance(suite, pn_clock, 4.0)
    assert suite.get_by_text("Status: done")
    assert suite.get_by_text("Scale: 1.00")
    suite.press(suite.get_by_text("Run timed spring"))
    _advance(suite, pn_clock, 4.0)
    assert suite.get_by_text("Scale: 0.50")
    assert suite.back()

    _open(suite, "with_decay")
    assert suite.get_by_text("Expected x: 150")
    suite.press(suite.get_by_text("Fling"))
    _advance(suite, pn_clock, 6.0)
    assert suite.get_by_text("Finished: yes")
    assert suite.get_by_text("Settled x: 150")
    assert suite.get_by_text("Status: done")
    suite.press(suite.get_by_text("Fling clamped"))
    _advance(suite, pn_clock, 6.0)
    assert suite.get_by_text("Settled x: 100")
    assert suite.get_by_text("Status: done")
    suite.press(suite.get_by_text("Reset decay"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Status: idle")


def test_composition_demo_sequences_repeats_and_loops(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "composition")
    suite.press(suite.get_by_text("Run sequence"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Sequence: done")
    suite.press(suite.get_by_text("Run repeat"))
    assert suite.get_by_text("Repeat: running")
    _advance(suite, pn_clock)
    assert suite.get_by_text("Repeat: finished")
    assert suite.presented_style(_box(suite, "pulse-box"))["opacity"] == 1.0
    suite.press(suite.get_by_text("Start loop"))
    _advance(suite, pn_clock, 0.5)
    suite.press(suite.get_by_text("Stop loop"))
    assert suite.get_by_text("Loop: stopped")
    assert suite.get_by_text("Loop moved: yes")


def test_interpolate_demo_matches_python_helpers(pn_clock: FakeClock, suite: RenderResult) -> None:
    demo = importlib.import_module("app.screens.motion.interpolate")
    end = pn.interpolate_color(1.0, demo._STOPS, demo._COLORS)
    _open(suite, "interpolate")
    assert suite.get_by_text(f"Midpoint color: {pn.interpolate_color(0.5, demo._STOPS, demo._COLORS)}")
    assert suite.get_by_text("Clamped past the end: 160")
    assert suite.get_by_text("Extended past the end: 320")
    suite.press(suite.get_by_text("Run interpolate"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Status: done")
    assert suite.get_by_text(f"End color: {end}")
    assert suite.get_by_text("Colors match: yes")
    presented = suite.presented_style(_box(suite, "interp-box"))
    assert presented["background_color"] == end
    assert presented["transform"] == [{"translate_x": 160.0}]
    assert presented["opacity"] == 1


def test_collapsing_header_runs_its_scroll_worklet_in_the_core(pn_clock: FakeClock, suite: RenderResult) -> None:
    from pythonnative.events import get_event_registry

    _open(suite, "collapsing_header")
    assert suite.get_by_text("Header state: expanded")
    scroller = next(
        view
        for view in suite.get_all_by_type("ScrollView")
        if "on_scroll" in ((view.props.get("_pn_motion") or {}).get("events") or {})
    )
    # The worklet replaces the Python listener: nothing is registered for Python.
    assert not get_event_registry().has(scroller.tag, "on_scroll")
    header = _box(suite, "Collapsing toolbar")
    payload = {"x": 0.0, "content_width": 300.0, "content_height": 2400.0}
    payload.update(viewport_width=300.0, viewport_height=400.0)
    suite.fire(scroller, "on_scroll", {**payload, "y": 240.0})
    assert suite.get_by_text("Header state: collapsed")
    assert suite.presented_style(header)["opacity"] == 0
    assert suite.presented_style(header)["transform"] == [{"translate_y": -56.0}]
    suite.fire(scroller, "on_scroll", {**payload, "y": 0.0})
    assert suite.get_by_text("Header state: expanded")


def test_drag_under_load_releases_on_the_ui_thread(
    pn_clock: FakeClock, suite: RenderResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    demo = importlib.import_module("app.screens.motion.drag_under_load")
    monkeypatch.setattr(demo, "BLOCK_SECONDS", 0.0)
    _open(suite, "drag_under_load")
    card = suite.get_by_label("Drag card")
    suite.press(suite.get_by_text("Block Python"))
    assert suite.get_by_text("Python busy: yes")
    # The handler is parked before its blocking loop; the drag runs entirely in the core.
    suite.drag(card, dx=140, duration=0.2)
    assert suite.get_by_text("Released while busy: yes")
    assert suite.get_by_text("Side: right")
    _advance(suite, pn_clock)
    assert suite.get_by_text("Python busy: no")
    assert suite.get_by_text("Blocks: 1")
    transform = suite.presented_style(card)["transform"]
    assert transform[0]["translate_x"] == pytest.approx(demo.TRACK, abs=0.5)
    assert transform[1]["rotate"] == pytest.approx(6.0, abs=0.1)
    suite.drag(card, dx=-140, duration=0.2)
    _advance(suite, pn_clock)
    assert suite.get_by_text("Side: left")
    assert suite.get_by_text("Released while busy: no")
    assert suite.get_by_text("Releases: 2")


def test_layout_animations_demo_enters_exits_and_moves(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "layout_animations")
    assert suite.get_by_text("Chips: 3")
    # The chips mounted with the screen skip their entering animation.
    assert "transform" not in suite.presented_style(_box(suite, "Chip 1"))
    suite.press(suite.get_by_text("Add chip"))
    assert suite.get_by_text("Chips: 4")
    chip4 = _box(suite, "Chip 4")
    assert suite.presented_style(chip4)["transform"] != [{"scale": 1}]
    _advance(suite, pn_clock)
    assert "transform" not in suite.presented_style(chip4)
    chip1 = _box(suite, "Chip 1")
    chip2 = _box(suite, "Chip 2")
    settled_x = suite.presented_frame(chip2)[0]
    suite.press(suite.get_by_text("Remove first chip"))
    assert suite.get_by_text("Last removed: Chip 1")
    assert suite.query_by_text("Chip 1") is None  # the component unmounted at once
    assert chip1.tag in suite.backend.native.views  # but its native view is fading out
    _advance(suite, pn_clock)
    assert chip1.tag not in suite.backend.native.views
    assert suite.presented_frame(chip2)[0] < settled_x  # Chip 2 slid into Chip 1's place


def test_list_item_animations_demo_sends_presets_to_the_native_list(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "list_item_animations")
    native = suite.backend.native.find("VirtualList")[-1]
    assert native.props["item_entering"]["type"] == "slide_in"
    assert native.props["item_entering"]["edge"] == "right"
    assert native.props["item_exiting"]["type"] == "fade_out"
    assert native.props["item_layout"]["type"] == "linear"
    suite.press(suite.get_by_text("Add row"))
    assert suite.get_by_text("Rows: 6")
    assert suite.get_by_text("Top row: ItemRow 6")
    suite.press(suite.get_by_text("Remove top row"))
    assert suite.get_by_text("Rows: 5")
    assert suite.get_by_text("Top row: ItemRow 5")


def test_shared_element_demo_pairs_tags_across_a_push(suite: RenderResult) -> None:
    demo = importlib.import_module("app.screens.motion.shared_element")
    _open(suite, "shared_element")
    assert suite.get_by_text("Showing: list")
    suite.press(suite.get_by_text("Open detail"))
    assert suite.get_by_text("Showing: detail")
    assert _nav_ref().get_state().current.params == {"detail": True}
    tagged = [v for v in suite.backend.native.views.values() if v.props.get("shared_tag") == demo.SHARED_TAG]
    assert len(tagged) == 2  # the outgoing thumbnail and the incoming hero
    hero = next(v for v in tagged if v.props.get("shared_transition"))
    assert hero.props["shared_transition"]["spring"]["damping_ratio"] == 0.9
    suite.press(suite.get_by_text("Back to list"))
    assert suite.get_by_text("Showing: list")


def test_bottom_sheet_demo_drags_between_detents(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "bottom_sheet")
    handle = suite.get_by_label("Sheet handle")
    surface = handle.parent
    assert surface is not None
    assert suite.get_by_text("Sheet index: closed")
    suite.press(suite.get_by_text("Open sheet"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Last request: open")
    assert suite.presented_style(surface)["transform"] == [{"translate_y": 200.0}]
    suite.drag(handle, dy=-150, duration=0.3)
    _advance(suite, pn_clock)
    assert suite.get_by_text("Sheet index: 1")
    assert suite.get_by_text("Sheet changes: 2")  # the handle's open, then the drag
    assert suite.presented_style(surface)["transform"] == [{"translate_y": 0}]
    suite.press(suite.get_by_text("Sheet collapse"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Last request: collapse")
    assert suite.presented_style(surface)["transform"] == [{"translate_y": 200}]
    suite.drag(handle, dy=500, duration=0.1)
    _advance(suite, pn_clock)
    assert suite.get_by_text("Sheet index: closed")


def test_swipeable_demo_opens_both_sides(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "swipeable")
    row = _box(suite, "Swipe this row").parent  # the Swipeable's sliding view
    suite.drag(row, dx=-70, duration=0.2)
    _advance(suite, pn_clock)
    assert suite.get_by_text("Opened: right")
    assert suite.presented_style(row)["transform"] == [{"translate_x": -80.0}]
    suite.press(_box(suite, "Delete"))
    assert suite.get_by_text("Action: delete")
    suite.press(suite.get_by_text("Close via ref"))
    _advance(suite, pn_clock)
    assert suite.get_by_text("Last request: close")
    assert suite.presented_style(row)["transform"] == [{"translate_x": 0}]
    suite.drag(row, dx=70, duration=0.2)
    _advance(suite, pn_clock)
    assert suite.get_by_text("Opened: left")
    suite.press(_box(suite, "Pin"))
    assert suite.get_by_text("Action: pin")


def test_frame_callback_demo_advances_only_while_active(pn_clock: FakeClock, suite: RenderResult) -> None:
    _open(suite, "frame_callback")
    suite.press(suite.get_by_text("Read elapsed"))
    assert suite.get_by_text("Elapsed advanced: no")
    suite.press(suite.get_by_text("Start frames"))
    assert suite.get_by_text("Frames running: yes")
    _advance(suite, pn_clock, 0.5)
    suite.press(suite.get_by_text("Read elapsed"))
    assert suite.get_by_text("Elapsed advanced: yes")
    suite.press(suite.get_by_text("Pause frames"))
    _advance(suite, pn_clock, 0.1)
    suite.press(suite.get_by_text("Check paused"))
    _advance(suite, pn_clock, 0.5)
    assert suite.get_by_text("Paused stays still: yes")
