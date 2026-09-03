"""Unit tests for the animated-node graph: interpolate, operators,
diff_clamp, Animated.event, loop, stagger, and transform bindings."""

from __future__ import annotations

import math
import time
from typing import Any, List

import pytest

from pythonnative.animated import (
    Animated,
    AnimatedInterpolation,
    AnimatedValue,
    _resolve_style_with_values,
)
from pythonnative.gestures import GestureEvent
from pythonnative.native_views import set_registry
from pythonnative.testing import FakeBackend

# ======================================================================
# interpolate: numbers
# ======================================================================


def test_interpolate_linear_segment() -> None:
    v = AnimatedValue(0.5)
    iv = v.interpolate([0, 1], [0, 100])
    assert iv.value == 50.0


def test_interpolate_multi_segment() -> None:
    v = AnimatedValue(0.0)
    iv = v.interpolate([0, 10, 20], [0, 100, 0])
    v.set_value(5.0)
    assert iv.value == 50.0
    v.set_value(15.0)
    assert iv.value == 50.0
    v.set_value(10.0)
    assert iv.value == 100.0


def test_interpolate_extend_is_default() -> None:
    v = AnimatedValue(2.0)
    iv = v.interpolate([0, 1], [0, 100])
    assert iv.value == 200.0
    v.set_value(-1.0)
    assert iv.value == -100.0


def test_interpolate_clamp() -> None:
    v = AnimatedValue(5.0)
    iv = v.interpolate([0, 1], [0, 100], extrapolate="clamp")
    assert iv.value == 100.0
    v.set_value(-5.0)
    assert iv.value == 0.0


def test_interpolate_identity() -> None:
    v = AnimatedValue(7.0)
    iv = v.interpolate([0, 1], [0, 100], extrapolate="identity")
    assert iv.value == 7.0


def test_interpolate_per_side_extrapolate() -> None:
    v = AnimatedValue(-1.0)
    iv = v.interpolate([0, 1], [0, 100], extrapolate_left="clamp", extrapolate_right="extend")
    assert iv.value == 0.0
    v.set_value(2.0)
    assert iv.value == 200.0


def test_interpolate_validation() -> None:
    v = AnimatedValue(0.0)
    with pytest.raises(ValueError):
        v.interpolate([0], [0])
    with pytest.raises(ValueError):
        v.interpolate([0, 1], [0])
    with pytest.raises(ValueError):
        v.interpolate([1, 0], [0, 1])


def test_interpolate_chains() -> None:
    v = AnimatedValue(0.5)
    second = v.interpolate([0, 1], [0, 10]).interpolate([0, 10], [100, 0])
    assert second.value == 50.0
    v.set_value(1.0)
    assert second.value == 0.0


# ======================================================================
# interpolate: colors and angles
# ======================================================================


def test_interpolate_colors() -> None:
    v = AnimatedValue(0.0)
    iv = v.interpolate([0, 1], ["#000000", "#FFFFFF"])
    assert iv.value == "#FF000000"
    v.set_value(1.0)
    assert iv.value == "#FFFFFFFF"
    v.set_value(0.5)
    assert iv.value == "#FF808080"


def test_interpolate_colors_with_alpha() -> None:
    v = AnimatedValue(0.5)
    iv = v.interpolate([0, 1], ["#00FF0000", "#FFFF0000"])
    assert iv.value == "#80FF0000"


def test_interpolate_degrees() -> None:
    v = AnimatedValue(0.5)
    iv = v.interpolate([0, 1], ["0deg", "180deg"])
    assert iv.value == 90.0


def test_interpolate_radians_convert_to_degrees() -> None:
    v = AnimatedValue(0.5)
    iv = v.interpolate([0, 1], ["0rad", f"{math.pi}rad"])
    assert abs(iv.value - 90.0) < 1e-9


# ======================================================================
# Arithmetic operators
# ======================================================================


def test_operator_add_sub_mul_div() -> None:
    v = AnimatedValue(10.0)
    assert (v + 5).value == 15.0
    assert (5 + v).value == 15.0
    assert (v - 4).value == 6.0
    assert (20 - v).value == 10.0
    assert (v * 2).value == 20.0
    assert (v / 4).value == 2.5
    assert (v % 3).value == 1.0
    assert (-v).value == -10.0


def test_operator_combines_two_animated_values() -> None:
    a = AnimatedValue(3.0)
    b = AnimatedValue(4.0)
    total = a + b
    assert total.value == 7.0
    a.set_value(10.0)
    assert total.value == 14.0


def test_operator_divide_by_zero_is_safe() -> None:
    a = AnimatedValue(3.0)
    b = AnimatedValue(0.0)
    assert (a / b).value == 0.0


# ======================================================================
# Propagation to native attachments
# ======================================================================


def test_derived_node_pushes_to_native_attachment() -> None:
    backend = FakeBackend()
    set_registry(backend)
    try:
        v = AnimatedValue(0.0)
        iv = v.interpolate([0, 1], [0, 100])
        iv.attach(9, "translate_y")
        backend.animated.clear()
        v.set_value(0.5)
        assert (9, "translate_y", 50.0) in backend.animated
    finally:
        set_registry(None)


def test_derived_chain_pushes_through_operators() -> None:
    backend = FakeBackend()
    set_registry(backend)
    try:
        v = AnimatedValue(1.0)
        node = v * 10 + 5
        node.attach(3, "translate_x")
        backend.animated.clear()
        v.set_value(2.0)
        assert (3, "translate_x", 25.0) in backend.animated
    finally:
        set_registry(None)


# ======================================================================
# diff_clamp
# ======================================================================


def test_diff_clamp_tracks_deltas_not_absolutes() -> None:
    v = AnimatedValue(0.0)
    d = Animated.diff_clamp(v, 0, 50)
    v.set_value(100.0)
    assert d.value == 50.0
    # Scrolling "back up" by 40 immediately reduces the output even
    # though the absolute input is still far beyond the range.
    v.set_value(60.0)
    assert d.value == 10.0
    v.set_value(80.0)
    assert d.value == 30.0


def test_diff_clamp_validation() -> None:
    v = AnimatedValue(0.0)
    with pytest.raises(ValueError):
        Animated.diff_clamp(v, 10, 0)


# ======================================================================
# Animated.event
# ======================================================================


def test_event_binds_dict_payload_fields() -> None:
    y = AnimatedValue(0.0)
    handler = Animated.event(y=y)
    handler({"x": 3.0, "y": 42.0})
    assert y.value == 42.0


def test_event_binds_gesture_event_attributes() -> None:
    tx = AnimatedValue(0.0)
    handler = Animated.event(translation_x=tx)
    handler(GestureEvent(kind="pan", state="changed", translation_x=7.0))
    assert tx.value == 7.0


def test_event_invokes_listener_after_update() -> None:
    y = AnimatedValue(0.0)
    seen: List[Any] = []
    handler = Animated.event(lambda payload: seen.append((payload, y.value)), y=y)
    handler({"y": 5.0})
    assert seen == [({"y": 5.0}, 5.0)]


def test_event_rejects_read_only_nodes() -> None:
    v = AnimatedValue(0.0)
    with pytest.raises(TypeError):
        Animated.event(y=v.interpolate([0, 1], [0, 1]))  # type: ignore[arg-type]


def test_event_ignores_missing_fields() -> None:
    y = AnimatedValue(1.0)
    Animated.event(y=y)({"x": 9.0})
    assert y.value == 1.0


# ======================================================================
# Native driver eligibility
# ======================================================================


class _AcceptingBackend(FakeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.native_started: List[Any] = []

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Any) -> bool:
        self.native_started.append((tag, anim_id, prop_name))
        return True

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        return None


def test_values_with_derived_dependents_stay_on_python_driver() -> None:
    backend = _AcceptingBackend()
    set_registry(backend)
    try:
        v = AnimatedValue(0.0)
        v.attach(1, "translate_y")
        iv = v.interpolate([0, 100], [1, 0])
        iv.attach(2, "opacity")

        Animated.timing(v, to=100.0, duration=30, easing="linear").start()
        # The interpolation needs per-frame Python evaluation, so the
        # native driver must decline.
        assert backend.native_started == []

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and v.value < 99.9:
            time.sleep(0.01)
        assert abs(v.value - 100.0) < 0.1
        assert abs(float(iv.value) - 0.0) < 0.01
        # The interpolated attachment was driven too.
        opacity_values = [val for tag, prop, val in backend.animated if (tag, prop) == (2, "opacity")]
        assert opacity_values and abs(opacity_values[-1]) < 0.01
    finally:
        set_registry(None)


# ======================================================================
# Reusable handles, loop, stagger
# ======================================================================


@pytest.mark.asyncio
async def test_awaiting_same_handle_twice_reruns_animation() -> None:
    v = AnimatedValue(0.0)
    handle = Animated.timing(v, to=1.0, duration=30, easing="linear")
    await handle
    assert abs(v.value - 1.0) < 0.05
    v.set_value(0.0)
    await handle
    assert abs(v.value - 1.0) < 0.05


@pytest.mark.asyncio
async def test_loop_runs_fixed_iterations_with_reset() -> None:
    v = AnimatedValue(0.0)
    seen: List[float] = []
    v.add_listener("x", seen.append)
    await Animated.loop(
        Animated.timing(v, to=1.0, duration=30, easing="linear"),
        iterations=2,
    )
    assert abs(v.value - 1.0) < 0.05
    # The value was reset to its origin before the second iteration:
    # somewhere after nearly reaching 1.0 it dropped back below 0.5.
    peak_hit = False
    reset_seen = False
    for value in seen:
        if value > 0.9:
            peak_hit = True
        elif peak_hit and value < 0.5:
            reset_seen = True
            break
    assert reset_seen, f"expected a reset between iterations, saw {seen[:20]}..."


@pytest.mark.asyncio
async def test_loop_stop_ends_infinite_loop() -> None:
    import asyncio

    v = AnimatedValue(0.0)
    loop = Animated.loop(Animated.timing(v, to=1.0, duration=20, easing="linear"))
    loop.start()
    await asyncio.sleep(0.1)
    loop.stop()
    await asyncio.sleep(0.05)
    snapshot = v.value
    await asyncio.sleep(0.1)
    assert v.value == snapshot


@pytest.mark.asyncio
async def test_stagger_offsets_start_times() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    first_change: dict = {}

    v1.add_listener("x", lambda _v: first_change.setdefault("v1", time.monotonic()))
    v2.add_listener("x", lambda _v: first_change.setdefault("v2", time.monotonic()))

    await Animated.stagger(
        100,
        [
            Animated.timing(v1, to=1.0, duration=30, easing="linear"),
            Animated.timing(v2, to=1.0, duration=30, easing="linear"),
        ],
    )
    assert abs(v1.value - 1.0) < 0.05
    assert abs(v2.value - 1.0) < 0.05
    assert first_change["v2"] - first_change["v1"] >= 0.05


# ======================================================================
# Style resolution with animated nodes
# ======================================================================


def test_resolve_style_extracts_top_level_bindings() -> None:
    v = AnimatedValue(0.4)
    plain, bindings = _resolve_style_with_values({"opacity": v, "padding": 8})
    assert plain == {"opacity": 0.4, "padding": 8}
    assert bindings == {"opacity": v}


def test_resolve_style_extracts_transform_bindings() -> None:
    tx = AnimatedValue(5.0)
    scale = AnimatedValue(2.0)
    plain, bindings = _resolve_style_with_values(
        {"transform": [{"translate_x": tx}, {"scale": scale}, {"rotate": 45.0}]}
    )
    assert plain["transform"] == [{"translate_x": 5.0}, {"scale": 2.0}, {"rotate": 45.0}]
    assert bindings == {"translate_x": tx, "scale": scale}


def test_resolve_style_extracts_interpolation_in_transform() -> None:
    v = AnimatedValue(0.5)
    iv = v.interpolate([0, 1], [0, 200])
    plain, bindings = _resolve_style_with_values({"transform": [{"translate_y": iv}]})
    assert plain["transform"] == [{"translate_y": 100.0}]
    assert bindings["translate_y"] is iv
    assert isinstance(bindings["translate_y"], AnimatedInterpolation)
