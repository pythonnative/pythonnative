"""Unit tests for the interaction-surface props: on_layout, hit_slop,
pointer_events / z_index style keys, per-corner radii, and the
KeyboardAvoidingView "height" behavior."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pythonnative.components import KeyboardAvoidingView, Pressable, Text, View
from pythonnative.element import Element
from pythonnative.reconciler import Reconciler
from pythonnative.style import Style
from pythonnative.testing import FakeBackend


def _mount(el: Element) -> Tuple[Any, Reconciler, FakeBackend]:
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    root = rec.mount(el)
    # Layout (and therefore on_layout) only runs once the host supplies
    # a viewport size.
    rec.set_viewport_size(320.0, 640.0)
    return root, rec, backend


# ======================================================================
# Style keys
# ======================================================================


def test_new_style_keys_are_declared() -> None:
    keys = set(Style.__annotations__)
    assert {
        "z_index",
        "pointer_events",
        "border_top_left_radius",
        "border_top_right_radius",
        "border_bottom_left_radius",
        "border_bottom_right_radius",
    } <= keys


def test_new_style_keys_flow_to_native_props() -> None:
    _, _, backend = _mount(
        View(
            style={
                "z_index": 3,
                "pointer_events": "box_none",
                "border_top_left_radius": 12,
                "width": 40,
                "height": 40,
            }
        )
    )
    view = next(v for v in backend.views.values() if v.type_name == "View")
    assert view.props["z_index"] == 3
    assert view.props["pointer_events"] == "box_none"
    assert view.props["border_top_left_radius"] == 12


# ======================================================================
# hit_slop
# ======================================================================


def test_hit_slop_passes_through_as_plain_prop() -> None:
    _, _, backend = _mount(Pressable(Text("tiny"), on_press=lambda: None, hit_slop={"top": 8.0, "bottom": 8.0}))
    view = next(v for v in backend.views.values() if v.type_name == "Pressable")
    assert view.props["hit_slop"] == {"top": 8.0, "bottom": 8.0}


def test_uniform_hit_slop_on_view() -> None:
    _, _, backend = _mount(View(hit_slop=10.0))
    view = next(v for v in backend.views.values() if v.type_name == "View")
    assert view.props["hit_slop"] == 10.0


# ======================================================================
# on_layout
# ======================================================================


def test_on_layout_fires_with_frame_after_mount() -> None:
    frames: List[Dict[str, float]] = []
    # The measured view is nested: the native root's frame is owned by
    # the screen host and never collected.
    _, _, backend = _mount(
        View(
            View(
                on_layout=frames.append,
                style={"width": 120, "height": 80},
            )
        )
    )
    assert len(frames) == 1
    assert frames[0]["width"] == 120.0
    assert frames[0]["height"] == 80.0


def test_on_layout_fires_again_only_when_frame_changes() -> None:
    frames: List[Dict[str, float]] = []

    def build(width: float) -> Element:
        return View(View(on_layout=frames.append, style={"width": width, "height": 50}))

    _, rec, _ = _mount(build(100))
    assert len(frames) == 1

    rec.reconcile(build(100))
    assert len(frames) == 1, "unchanged frame must not re-fire on_layout"

    rec.reconcile(build(200))
    assert len(frames) == 2
    assert frames[1]["width"] == 200.0


def test_on_layout_never_reaches_native_props() -> None:
    _, _, backend = _mount(View(on_layout=lambda f: None, style={"width": 10, "height": 10}))
    view = next(v for v in backend.views.values() if v.type_name == "View")
    assert not callable(view.props.get("on_layout"))


# ======================================================================
# KeyboardAvoidingView behavior="height"
# ======================================================================


def test_keyboard_avoiding_height_shrinks_by_keyboard_overlap() -> None:
    from pythonnative import platform_metrics

    platform_metrics.reset_keyboard_height()
    try:
        _, rec, backend = _mount(View(KeyboardAvoidingView(Text("hi"), behavior="height", style={"height": 300})))
        # The mount layout captured the resting height via on_layout.
        rec.flush_dirty()

        platform_metrics.set_keyboard_height(120.0)
        rec.flush_dirty()
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("height") == 180.0

        platform_metrics.set_keyboard_height(0.0)
        rec.flush_dirty()
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("height") == 300
    finally:
        platform_metrics.reset_keyboard_height()


def test_keyboard_avoiding_height_respects_offset() -> None:
    from pythonnative import platform_metrics

    platform_metrics.reset_keyboard_height()
    try:
        _, rec, backend = _mount(
            View(
                KeyboardAvoidingView(
                    Text("hi"),
                    behavior="height",
                    keyboard_vertical_offset=20.0,
                    style={"height": 300},
                )
            )
        )
        rec.flush_dirty()
        platform_metrics.set_keyboard_height(120.0)
        rec.flush_dirty()
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("height") == 200.0
    finally:
        platform_metrics.reset_keyboard_height()
