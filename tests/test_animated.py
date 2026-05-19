"""Unit tests for the Animated API (AnimatedValue, timing, sequence, etc.)."""

from __future__ import annotations

import threading
import time
from typing import Any

from pythonnative.animated import Animated, AnimatedValue, use_animated_value
from pythonnative.element import Element
from pythonnative.hooks import component
from pythonnative.reconciler import Reconciler

# ======================================================================
# AnimatedValue
# ======================================================================


def test_animated_value_initial() -> None:
    v = AnimatedValue(3.14)
    assert v.value == 3.14
    assert float(v) == 3.14


def test_animated_value_set_value_fires_subscribers() -> None:
    v = AnimatedValue(0.0)
    received: list = []
    unsub = v.add_listener("opacity", lambda new_val: received.append(new_val))
    v.set_value(0.5)
    v.set_value(1.0)
    assert received == [0.5, 1.0]
    unsub()
    v.set_value(0.0)
    assert received == [0.5, 1.0]


def test_animated_value_subscriber_exception_isolated() -> None:
    v = AnimatedValue(0.0)

    def boom(_: float) -> None:
        raise RuntimeError("oops")

    received: list = []
    v.add_listener("a", boom)
    v.add_listener("b", lambda x: received.append(x))
    v.set_value(1.0)
    assert received == [1.0]


# ======================================================================
# Timing animation
# ======================================================================


def _run_until(predicate: Any, timeout: float = 2.0) -> bool:
    """Spin until ``predicate`` returns True or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_timing_completes_at_target() -> None:
    v = AnimatedValue(0.0)
    completed = threading.Event()
    Animated.timing(v, to=10.0, duration=80, easing="linear").start(on_complete=completed.set)
    assert completed.wait(2.0), "animation never completed"
    assert abs(v.value - 10.0) < 0.05


def test_timing_progress_fires_listener() -> None:
    v = AnimatedValue(0.0)
    received: list = []
    v.add_listener("opacity", lambda x: received.append(x))
    completed = threading.Event()
    Animated.timing(v, to=1.0, duration=120, easing="linear").start(on_complete=completed.set)
    assert completed.wait(2.0)
    # Should have received intermediate values, not just the final.
    assert len(received) >= 3
    assert received[0] > 0.0
    assert received[-1] == 1.0


def test_timing_easing_curves() -> None:
    """Easing curves change intermediate values; we just smoke-test the API."""
    for easing in ("linear", "ease_in", "ease_out", "ease_in_out", "bounce"):
        v = AnimatedValue(0.0)
        completed = threading.Event()
        Animated.timing(v, to=1.0, duration=40, easing=easing).start(on_complete=completed.set)
        assert completed.wait(2.0), f"easing {easing} did not finish"
        assert abs(v.value - 1.0) < 0.05


# ======================================================================
# Spring animation
# ======================================================================


def test_spring_settles() -> None:
    v = AnimatedValue(0.0)
    completed = threading.Event()
    Animated.spring(v, to=5.0, stiffness=200, damping=20, mass=1.0).start(on_complete=completed.set)
    assert completed.wait(3.0)
    assert abs(v.value - 5.0) < 0.1


# ======================================================================
# Composition: sequence and parallel
# ======================================================================


def test_sequence_runs_in_order() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    completed = threading.Event()
    Animated.sequence(
        [
            Animated.timing(v1, to=1.0, duration=40, easing="linear"),
            Animated.timing(v2, to=2.0, duration=40, easing="linear"),
        ]
    ).start(on_complete=completed.set)
    assert completed.wait(3.0)
    assert abs(v1.value - 1.0) < 0.1
    assert abs(v2.value - 2.0) < 0.1


def test_parallel_runs_concurrently() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    completed = threading.Event()
    started = time.monotonic()
    Animated.parallel(
        [
            Animated.timing(v1, to=1.0, duration=120, easing="linear"),
            Animated.timing(v2, to=2.0, duration=120, easing="linear"),
        ]
    ).start(on_complete=completed.set)
    assert completed.wait(3.0)
    elapsed = time.monotonic() - started
    # Two parallel 120ms animations should take ~120ms, not 240ms.
    assert elapsed < 0.5
    assert abs(v1.value - 1.0) < 0.1
    assert abs(v2.value - 2.0) < 0.1


def test_delay_waits_then_completes() -> None:
    completed = threading.Event()
    started = time.monotonic()
    Animated.delay(80).start(on_complete=completed.set)
    assert completed.wait(2.0)
    assert (time.monotonic() - started) >= 0.05


# ======================================================================
# Stop
# ======================================================================


def test_stop_freezes_value() -> None:
    v = AnimatedValue(0.0)
    handle = Animated.timing(v, to=10.0, duration=400, easing="linear")
    handle.start()
    time.sleep(0.05)
    handle.stop()
    snapshot = v.value
    time.sleep(0.2)
    # After stop, value should not advance further toward 10.
    assert abs(v.value - snapshot) < 0.1
    assert v.value < 9.0


# ======================================================================
# use_animated_value
# ======================================================================


class _Stub:
    def __init__(self, type_name: str, props: dict) -> None:
        self.type_name = type_name
        self.props = props
        self.children: list = []


class _StubBackend:
    def create_view(self, type_name: str, props: dict) -> _Stub:
        return _Stub(type_name, props)

    def update_view(self, view: _Stub, type_name: str, changed: dict) -> None:
        view.props.update(changed)

    def add_child(self, parent: _Stub, child: _Stub, parent_type: str) -> None:
        parent.children.append(child)

    def remove_child(self, parent: _Stub, child: _Stub, parent_type: str) -> None:
        parent.children = [c for c in parent.children if c is not child]

    def insert_child(self, parent: _Stub, child: _Stub, parent_type: str, index: int) -> None:
        parent.children.insert(index, child)


def test_use_animated_value_returns_animated_value() -> None:
    captured: list = []

    @component
    def view() -> Element:
        v = use_animated_value(0.5)
        captured.append(v)
        return Element("View", {"opacity": v}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(view())
    assert isinstance(captured[0], AnimatedValue)
    assert captured[0].value == 0.5


def test_use_animated_value_stable_across_renders() -> None:
    captured: list = []

    @component
    def view() -> Element:
        v = use_animated_value(0.0)
        captured.append(v)
        return Element("View", {"opacity": v}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(view())
    rec.reconcile(view())
    rec.reconcile(view())
    assert captured[0] is captured[1] is captured[2]


def test_use_animated_value_default_initial_zero() -> None:
    captured: list = []

    @component
    def view() -> Element:
        v = use_animated_value()
        captured.append(v)
        return Element("View", {"opacity": v}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(view())
    assert captured[0].value == 0.0
