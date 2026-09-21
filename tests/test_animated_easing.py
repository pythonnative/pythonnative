"""Tests for ``pn.Easing``: descriptors, the Python evaluator, and the wire form."""

from __future__ import annotations

import time
from typing import Any

import pytest

from pythonnative.animated import EASING_NAMES, Animated, AnimatedValue, Easing, EasingSpec
from pythonnative.native_views import set_backend
from pythonnative.testing import FakeBackend

# ======================================================================
# Descriptors
# ======================================================================


def test_easing_namespace_exposes_frozen_specs() -> None:
    assert EASING_NAMES == ("linear", "ease", "ease_in", "ease_out", "ease_in_out", "quad", "cubic", "bounce")
    for name in EASING_NAMES:
        spec = getattr(Easing, name)
        assert isinstance(spec, EasingSpec)
        assert spec.name == name and spec.points is None
        assert spec.to_wire() == name
    with pytest.raises(Exception):
        Easing.linear.name = "other"  # type: ignore[misc]


def test_bezier_descriptor_carries_control_points() -> None:
    spec = Easing.bezier(0.2, 0.8, 0.2, 1.0)
    assert spec == EasingSpec("bezier", (0.2, 0.8, 0.2, 1.0))
    assert spec.to_wire() == [0.2, 0.8, 0.2, 1.0]
    assert repr(spec) == "Easing.bezier(0.2, 0.8, 0.2, 1.0)"
    assert repr(Easing.ease_out) == "Easing.ease_out"


def test_bezier_validation() -> None:
    with pytest.raises(ValueError):
        Easing.bezier(1.5, 0.0, 0.5, 1.0)  # x1 outside [0, 1]
    with pytest.raises(ValueError):
        Easing.bezier(0.5, 0.0, -0.1, 1.0)  # x2 outside [0, 1]
    # y values may overshoot (anticipation and overshoot curves).
    Easing.bezier(0.34, 1.56, 0.64, 1.0)
    with pytest.raises(ValueError):
        EasingSpec("bezier")
    with pytest.raises(ValueError):
        EasingSpec("wobble")
    with pytest.raises(ValueError):
        EasingSpec("linear", (0.0, 0.0, 1.0, 1.0))


# ======================================================================
# Evaluator
# ======================================================================


def test_named_curves_evaluate_to_reference_values() -> None:
    assert Easing.linear.evaluate(0.3) == 0.3
    assert Easing.quad.evaluate(0.5) == 0.25
    assert Easing.cubic.evaluate(0.5) == 0.125
    assert Easing.bounce.evaluate(0.0) == 0.0
    assert abs(Easing.bounce.evaluate(1.0) - 1.0) < 1e-12
    # Penner bounce-out midway through the first arc.
    assert abs(Easing.bounce.evaluate(0.2) - 7.5625 * 0.2 * 0.2) < 1e-12
    for name in EASING_NAMES:
        spec = getattr(Easing, name)
        assert spec.evaluate(0.0) == 0.0
        assert abs(spec.evaluate(1.0) - 1.0) < 1e-9


def test_ease_family_matches_react_native_definitions() -> None:
    # ease == bezier(0.42, 0, 1, 1) (React Native's Easing.ease); in/out/in_out derive from it.
    for t in (0.1, 0.25, 0.5, 0.75, 0.9):
        assert abs(Easing.ease.evaluate(t) - Easing.bezier(0.42, 0.0, 1.0, 1.0).evaluate(t)) < 1e-9
        assert abs(Easing.ease_in.evaluate(t) - Easing.ease.evaluate(t)) < 1e-9
        # Easing.out(f)(t) == 1 - f(1 - t)
        assert abs(Easing.ease_out.evaluate(t) - (1.0 - Easing.ease.evaluate(1.0 - t))) < 1e-6
    assert Easing.ease_in.evaluate(0.5) < 0.5 < Easing.ease_out.evaluate(0.5)
    assert abs(Easing.ease_in_out.evaluate(0.5) - 0.5) < 1e-6
    assert Easing.ease_in_out.evaluate(0.25) < 0.25 and Easing.ease_in_out.evaluate(0.75) > 0.75


def test_cubic_bezier_solver_inverts_the_parametric_curve() -> None:
    """For sampled parameter values, evaluate(x(t)) must return y(t)."""

    def component(t: float, p1: float, p2: float) -> float:
        inv = 1.0 - t
        return 3 * inv * inv * t * p1 + 3 * inv * t * t * p2 + t * t * t

    curves = [
        (0.2, 0.8, 0.2, 1.0),
        (0.42, 0.0, 0.58, 1.0),
        (0.34, 1.56, 0.64, 1.0),
        (1.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
    ]
    for x1, y1, x2, y2 in curves:
        spec = Easing.bezier(x1, y1, x2, y2)
        for i in range(1, 50):
            t = i / 50
            x = component(t, x1, x2)
            y = component(t, y1, y2)
            assert abs(spec.evaluate(x) - y) < 1e-5, (x1, y1, x2, y2, t)


def test_bezier_clamps_progress_outside_unit_interval() -> None:
    spec = Easing.bezier(0.2, 0.8, 0.2, 1.0)
    assert spec.evaluate(-0.5) == 0.0
    assert spec.evaluate(1.5) == 1.0


# ======================================================================
# Animated.timing integration
# ======================================================================


class _RecordingBackend(FakeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.native_started: list = []

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Any) -> bool:
        self.native_started.append((tag, anim_id, prop_name, dict(spec)))
        return True

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        return None


@pytest.fixture
def backend():  # type: ignore[no-untyped-def]
    backend = _RecordingBackend()
    set_backend(backend)
    try:
        yield backend
    finally:
        set_backend(None)


def test_timing_rejects_unknown_easing_names() -> None:
    v = AnimatedValue(0.0)
    with pytest.raises(ValueError, match="Unknown easing"):
        Animated.timing(v, to=1.0, easing="ease_in_quad")
    with pytest.raises(ValueError):
        Animated.timing(v, to=1.0, easing="eas_in_out")
    with pytest.raises(TypeError):
        Animated.timing(v, to=1.0, easing=42)  # type: ignore[arg-type]


def test_timing_serializes_named_and_bezier_easings(backend: _RecordingBackend) -> None:
    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    Animated.timing(v, to=1.0, duration=500, easing="ease_out").start()
    Animated.timing(v, to=1.0, duration=500, easing=Easing.bounce).start()
    Animated.timing(v, to=1.0, duration=500, easing=Easing.bezier(0.2, 0.8, 0.2, 1.0)).start()
    Animated.timing(v, to=1.0, duration=500).start()
    wire = [spec["easing"] for _tag, _id, _prop, spec in backend.native_started]
    assert wire == ["ease_out", "bounce", [0.2, 0.8, 0.2, 1.0], "ease_in_out"]


def test_callable_easing_disables_the_native_driver(backend: _RecordingBackend) -> None:
    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    handle = Animated.timing(v, to=1.0, duration=30, easing=lambda t: t * t)
    handle.start()
    assert backend.native_started == []
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and v.value < 0.99:
        time.sleep(0.01)
    assert abs(v.value - 1.0) < 0.05


@pytest.mark.asyncio
async def test_timing_with_bezier_easing_runs_on_python_ticker() -> None:
    v = AnimatedValue(0.0)
    seen: list = []
    v.add_listener("x", seen.append)
    result = await Animated.timing(v, to=1.0, duration=60, easing=Easing.bezier(0.2, 0.8, 0.2, 1.0))
    assert result.finished is True
    assert abs(v.value - 1.0) < 1e-9
    assert seen == sorted(seen), "an ease-out style bezier should be monotonic"
