"""Unit tests for the platform-metric hooks.

Covers ``use_window_dimensions``, ``use_safe_area_insets``, and
``use_keyboard_height``. Each hook subscribes to ``platform_metrics``
and re-renders when the value changes.
"""

from __future__ import annotations

from typing import Dict, Generator, List

import pytest
from fake_backend import FakeBackend as MockBackend

from pythonnative import platform_metrics as pm
from pythonnative.element import Element
from pythonnative.hooks import (
    component,
    use_keyboard_height,
    use_safe_area_insets,
    use_window_dimensions,
)
from pythonnative.reconciler import Reconciler


@pytest.fixture(autouse=True)
def _reset_metrics() -> Generator[None, None, None]:
    pm.reset_window_dimensions()
    pm.reset_safe_area_insets()
    pm.reset_keyboard_height()
    yield
    pm.reset_window_dimensions()
    pm.reset_safe_area_insets()
    pm.reset_keyboard_height()


def test_use_window_dimensions_returns_current_value() -> None:
    pm.set_window_dimensions(390.0, 844.0)
    rendered: List[Dict[str, float]] = []

    @component
    def comp() -> Element:
        rendered.append(use_window_dimensions())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    Reconciler(backend).mount(comp())
    assert rendered[0] == {"width": 390.0, "height": 844.0}


def test_use_window_dimensions_re_renders_on_change() -> None:
    rendered: List[Dict[str, float]] = []

    @component
    def comp() -> Element:
        rendered.append(use_window_dimensions())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: rec.reconcile(comp())
    rec.mount(comp())
    initial_render_count = len(rendered)

    pm.set_window_dimensions(800.0, 600.0)

    assert len(rendered) > initial_render_count
    assert rendered[-1] == {"width": 800.0, "height": 600.0}


def test_use_safe_area_insets_returns_current_value() -> None:
    pm.set_safe_area_insets(top=44.0, left=0.0, bottom=34.0, right=0.0)
    rendered: List[Dict[str, float]] = []

    @component
    def comp() -> Element:
        rendered.append(use_safe_area_insets())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    Reconciler(backend).mount(comp())
    assert rendered[0] == {"top": 44.0, "left": 0.0, "bottom": 34.0, "right": 0.0}


def test_use_safe_area_insets_re_renders_on_change() -> None:
    rendered: List[Dict[str, float]] = []

    @component
    def comp() -> Element:
        rendered.append(use_safe_area_insets())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: rec.reconcile(comp())
    rec.mount(comp())
    before = len(rendered)

    pm.set_safe_area_insets(top=20.0, left=0.0, bottom=10.0, right=0.0)
    assert len(rendered) > before
    assert rendered[-1]["top"] == 20.0


def test_use_keyboard_height_returns_current_value() -> None:
    pm.set_keyboard_height(280.0)
    rendered: List[float] = []

    @component
    def comp() -> Element:
        rendered.append(use_keyboard_height())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    Reconciler(backend).mount(comp())
    assert rendered[0] == 280.0


def test_use_keyboard_height_re_renders_on_change() -> None:
    rendered: List[float] = []

    @component
    def comp() -> Element:
        rendered.append(use_keyboard_height())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: rec.reconcile(comp())
    rec.mount(comp())
    before = len(rendered)

    pm.set_keyboard_height(300.0)
    assert len(rendered) > before
    assert rendered[-1] == 300.0


# ======================================================================
# SafeAreaView (inset padding driven by the metric hooks)
# ======================================================================


def _safe_area_props(backend: MockBackend) -> Dict[str, object]:
    view = next(v for v in backend.views.values() if v.type_name == "SafeAreaView")
    return view.props


def test_safe_area_view_pads_all_edges_by_default() -> None:
    from pythonnative.components import SafeAreaView, Text

    pm.set_safe_area_insets(top=44.0, left=2.0, bottom=34.0, right=3.0)
    backend = MockBackend()
    Reconciler(backend).mount(SafeAreaView(Text("safe")))
    props = _safe_area_props(backend)
    assert props.get("padding_top") == 44.0
    assert props.get("padding_left") == 2.0
    assert props.get("padding_bottom") == 34.0
    assert props.get("padding_right") == 3.0


def test_safe_area_view_edges_subset_and_user_padding_added() -> None:
    from pythonnative.components import SafeAreaView, Text

    pm.set_safe_area_insets(top=44.0, left=0.0, bottom=34.0, right=0.0)
    backend = MockBackend()
    Reconciler(backend).mount(SafeAreaView(Text("safe"), edges=("top",), style={"padding": 16}))
    props = _safe_area_props(backend)
    assert props.get("padding_top") == 60.0  # 16 user + 44 inset
    assert props.get("padding") == 16
    assert "padding_bottom" not in props


def test_safe_area_view_updates_when_insets_change() -> None:
    from pythonnative.components import SafeAreaView, Text

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None
    rec.mount(SafeAreaView(Text("safe")))
    assert "padding_top" not in _safe_area_props(backend)

    pm.set_safe_area_insets(top=20.0, left=0.0, bottom=0.0, right=0.0)
    rec.flush_dirty()
    assert _safe_area_props(backend).get("padding_top") == 20.0
