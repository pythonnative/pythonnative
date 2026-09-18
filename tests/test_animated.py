"""Unit tests for the Animated API (AnimatedValue, timing, sequence, etc.)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from pythonnative.animated import Animated, AnimatedValue, use_animated_value
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend as _StubBackend

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


@pytest.mark.asyncio
async def test_timing_completes_at_target() -> None:
    v = AnimatedValue(0.0)
    await Animated.timing(v, to=10.0, duration=80, easing="linear")
    assert abs(v.value - 10.0) < 0.05


@pytest.mark.asyncio
async def test_timing_progress_fires_listener() -> None:
    v = AnimatedValue(0.0)
    received: list = []
    v.add_listener("opacity", lambda x: received.append(x))
    await Animated.timing(v, to=1.0, duration=120, easing="linear")
    # Should have received intermediate values, not just the final.
    assert len(received) >= 3
    assert received[0] > 0.0
    assert received[-1] == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize("easing", ["linear", "ease_in", "ease_out", "ease_in_out", "bounce"])
async def test_timing_easing_curves(easing: str) -> None:
    v = AnimatedValue(0.0)
    await Animated.timing(v, to=1.0, duration=40, easing=easing)
    assert abs(v.value - 1.0) < 0.05


def test_start_is_fire_and_forget() -> None:
    """``handle.start()`` returns immediately and runs in the background."""
    v = AnimatedValue(0.0)
    handle = Animated.timing(v, to=10.0, duration=80, easing="linear")
    started = time.monotonic()
    handle.start()
    # The call returns well before the animation completes.
    assert (time.monotonic() - started) < 0.02
    # Wait for completion by polling.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and v.value < 9.9:
        time.sleep(0.02)
    assert abs(v.value - 10.0) < 0.1


# ======================================================================
# Spring animation
# ======================================================================


@pytest.mark.asyncio
async def test_spring_settles() -> None:
    v = AnimatedValue(0.0)
    await Animated.spring(v, to=5.0, stiffness=200, damping=20, mass=1.0)
    assert abs(v.value - 5.0) < 0.1


# ======================================================================
# Composition: sequence and parallel
# ======================================================================


@pytest.mark.asyncio
async def test_sequence_runs_in_order() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    await Animated.sequence(
        [
            Animated.timing(v1, to=1.0, duration=40, easing="linear"),
            Animated.timing(v2, to=2.0, duration=40, easing="linear"),
        ]
    )
    assert abs(v1.value - 1.0) < 0.1
    assert abs(v2.value - 2.0) < 0.1


@pytest.mark.asyncio
async def test_parallel_runs_concurrently() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    started = time.monotonic()
    await Animated.parallel(
        [
            Animated.timing(v1, to=1.0, duration=120, easing="linear"),
            Animated.timing(v2, to=2.0, duration=120, easing="linear"),
        ]
    )
    elapsed = time.monotonic() - started
    # Two parallel 120ms animations should take ~120ms, not 240ms.
    assert elapsed < 0.5
    assert abs(v1.value - 1.0) < 0.1
    assert abs(v2.value - 2.0) < 0.1


@pytest.mark.asyncio
async def test_delay_waits_then_completes() -> None:
    started = time.monotonic()
    await Animated.delay(80)
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


@pytest.mark.asyncio
async def test_cancelling_await_stops_animation() -> None:
    """Cancelling the awaiting task should freeze the in-flight animation."""
    v = AnimatedValue(0.0)
    handle = Animated.timing(v, to=10.0, duration=400, easing="linear")

    async def run() -> None:
        await handle

    task = asyncio.create_task(run())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    snapshot = v.value
    await asyncio.sleep(0.2)
    assert abs(v.value - snapshot) < 0.1
    assert v.value < 9.0


# ======================================================================
# use_animated_value
# ======================================================================


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


def test_animated_components_mount_through_reconciler() -> None:
    """Regression: ``@component`` packs positional children into the
    ``children`` prop; the Animated wrappers must unpack it instead of
    forwarding it to ``View()`` (pre-fix this raised ``TypeError:
    View() got an unexpected keyword argument 'children'``)."""
    from pythonnative.components import Column, Text
    from pythonnative.native_views import set_backend

    backend = _StubBackend()
    set_backend(backend)
    try:

        @component
        def app() -> Element:
            v = use_animated_value(0.25)
            return Column(
                Animated.View(Text("boxed"), style={"opacity": v, "padding": 4}),
                Animated.Text("fading", style={"opacity": v}),
                Animated.Image("https://example.com/i.png", style={"opacity": v}),
            )

        rec = Reconciler(backend)
        rec.mount(app())

        texts = {view.props.get("text") for view in backend.views.values()}
        assert {"boxed", "fading"} <= texts
        # Each wrapper attached its binding and pushed the initial value.
        opacity_pushes = [(tag, val) for tag, prop, val in backend.animated if prop == "opacity"]
        assert len(opacity_pushes) == 3
        assert all(val == 0.25 for _tag, val in opacity_pushes)
    finally:
        set_backend(None)


# ======================================================================
# Native driver
# ======================================================================


class _NativeBackend(_StubBackend):
    """FakeBackend that accepts native animations for chosen tags."""

    def __init__(self, accept_tags: Any = None) -> None:
        super().__init__()
        self.accept_tags = accept_tags  # None => accept everything
        self.native_started: list = []  # (tag, anim_id, prop, spec)
        self.native_cancelled: list = []  # (tag, anim_id)
        self.presentation_value: Any = None

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: dict) -> bool:
        if self.accept_tags is not None and tag not in self.accept_tags:
            return False
        self.native_started.append((tag, anim_id, prop_name, dict(spec)))
        return True

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        self.native_cancelled.append((tag, anim_id))
        return self.presentation_value


@pytest.fixture
def native_backend():  # type: ignore[no-untyped-def]
    from pythonnative.native_views import set_backend

    backend = _NativeBackend()
    set_backend(backend)
    try:
        yield backend
    finally:
        set_backend(None)


def test_attach_pushes_current_value_natively(native_backend: _NativeBackend) -> None:
    v = AnimatedValue(0.25)
    v.attach(7, "opacity")
    assert native_backend.animated[-1] == (7, "opacity", 0.25)

    v.set_value(0.75)
    assert native_backend.animated[-1] == (7, "opacity", 0.75)


def test_native_driver_offloads_attached_animation(native_backend: _NativeBackend) -> None:
    from pythonnative.animated import native_animation_completed

    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    Animated.timing(v, to=1.0, duration=5000, easing="linear").start()

    assert len(native_backend.native_started) == 1
    tag, anim_id, prop, spec = native_backend.native_started[0]
    assert (tag, prop) == (7, "opacity")
    assert spec["kind"] == "timing" and spec["to"] == 1.0 and spec["from"] == 0.0

    # No Python ticker is driving the value while the platform animates.
    time.sleep(0.05)
    assert v.value == 0.0

    # The platform's completion callback settles the Python cell.
    native_animation_completed(anim_id, finished=True)
    assert v.value == 1.0


def test_native_driver_fans_out_to_every_binding(native_backend: _NativeBackend) -> None:
    from pythonnative.animated import native_animation_completed

    v = AnimatedValue(0.0)
    v.attach(1, "opacity")
    v.attach(2, "opacity")
    Animated.timing(v, to=1.0, duration=5000).start()

    assert len(native_backend.native_started) == 2
    ids = [entry[1] for entry in native_backend.native_started]

    # The group settles only after *all* targets complete.
    native_animation_completed(ids[0])
    assert v.value == 0.0
    native_animation_completed(ids[1])
    assert v.value == 1.0


def test_python_listeners_force_python_driver(native_backend: _NativeBackend) -> None:
    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    v.add_listener("opacity", lambda _x: None)

    handle = Animated.timing(v, to=1.0, duration=30, easing="linear")
    handle.start()
    assert native_backend.native_started == []

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and v.value < 0.99:
        time.sleep(0.01)
    assert abs(v.value - 1.0) < 0.05


def test_unattached_value_uses_python_driver(native_backend: _NativeBackend) -> None:
    v = AnimatedValue(0.0)
    handle = Animated.timing(v, to=1.0, duration=30, easing="linear")
    handle.start()
    assert native_backend.native_started == []
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and v.value < 0.99:
        time.sleep(0.01)
    assert abs(v.value - 1.0) < 0.05


def test_partial_native_acceptance_rolls_back_and_falls_back() -> None:
    from pythonnative.native_views import set_backend

    backend = _NativeBackend(accept_tags={1})
    set_backend(backend)
    try:
        v = AnimatedValue(0.0)
        v.attach(1, "opacity")
        v.attach(2, "opacity")  # the backend rejects tag 2
        Animated.timing(v, to=1.0, duration=30, easing="linear").start()

        # The accepted target was cancelled so views can't drift apart.
        assert len(backend.native_started) == 1
        assert backend.native_cancelled == [(1, backend.native_started[0][1])]

        # And the Python ticker still finishes the job.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and v.value < 0.99:
            time.sleep(0.01)
        assert abs(v.value - 1.0) < 0.05
    finally:
        set_backend(None)


def test_native_stop_syncs_to_presentation_value(native_backend: _NativeBackend) -> None:
    native_backend.presentation_value = 0.42

    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    handle = Animated.timing(v, to=1.0, duration=5000).start()
    assert len(native_backend.native_started) == 1

    handle.stop()
    assert len(native_backend.native_cancelled) == 1
    # The value lands wherever the view visually was mid-flight.
    assert v.value == 0.42


def test_set_value_cancels_inflight_native_animation(native_backend: _NativeBackend) -> None:
    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    Animated.timing(v, to=1.0, duration=5000).start()
    assert len(native_backend.native_started) == 1

    v.stop_animation()
    assert len(native_backend.native_cancelled) == 1


def test_decay_settles_at_projected_final_value(native_backend: _NativeBackend) -> None:
    from pythonnative.animated import native_animation_completed

    v = AnimatedValue(10.0)
    v.attach(7, "translate_x")
    Animated.decay(v, velocity=0.5, deceleration=0.998).start()

    assert len(native_backend.native_started) == 1
    _tag, anim_id, _prop, spec = native_backend.native_started[0]
    # The wire spec the native decay drivers integrate: velocity in
    # points per millisecond, deceleration per millisecond.
    assert spec == {"kind": "decay", "from": 10.0, "velocity": 0.5, "deceleration": 0.998}

    native_animation_completed(anim_id)
    # React Native's closed form: x_final = from + v0 / (1 - deceleration)
    assert abs(v.value - (10.0 + 0.5 / (1.0 - 0.998))) < 1e-9
    assert abs(v.value - 260.0) < 1e-9


def test_decay_defaults_to_react_native_deceleration() -> None:
    from pythonnative.animated import DEFAULT_DECAY_DECELERATION

    assert DEFAULT_DECAY_DECELERATION == 0.998
    handle = Animated.decay(AnimatedValue(0.0), velocity=1.0)
    assert handle._spec_factory()["deceleration"] == 0.998


def test_decay_rejects_deceleration_outside_unit_interval() -> None:
    v = AnimatedValue(0.0)
    with pytest.raises(ValueError):
        Animated.decay(v, velocity=1.0, deceleration=1.0)
    with pytest.raises(ValueError):
        Animated.decay(v, velocity=1.0, deceleration=0.0)
    with pytest.raises(ValueError):
        Animated.decay(v, velocity=1.0, deceleration=1.5)


def test_decay_closed_form_matches_react_native_model() -> None:
    """The reference formula every decay driver (Python, Swift, Kotlin, browser) must reproduce."""
    from pythonnative.animated import _DecayAnimation

    v = AnimatedValue(100.0)
    anim = _DecayAnimation(v, velocity=2.0, deceleration=0.998)
    # Advance 250 ms in one step and compare with x(t) = x0 + v0 * (1 - d^t) / (1 - d).
    anim.advance(0.25)
    expected = 100.0 + 2.0 * (1.0 - 0.998**250.0) / (1.0 - 0.998)
    assert abs(v.value - expected) < 1e-9
    # Velocity after 250 ms is v0 * d^t; the animation is still moving.
    assert abs(2.0 * 0.998**250.0) > 0.001 and not anim._completed


@pytest.mark.asyncio
async def test_decay_python_ticker_settles_on_projected_value() -> None:
    v = AnimatedValue(0.0)
    seen: list = []
    v.add_listener("x", seen.append)
    # v0 = 0.5 pt/ms with deceleration 0.9 rests within about 60 ms.
    result = await Animated.decay(v, velocity=0.5, deceleration=0.9)
    assert result.finished is True
    assert abs(v.value - 0.5 / (1.0 - 0.9)) < 1e-9
    # Motion is monotonic toward the projection and never overshoots it.
    assert seen == sorted(seen)
    assert seen[-1] == v.value and all(x <= v.value + 1e-9 for x in seen)


def test_unfinished_native_completion_keeps_python_value(native_backend: _NativeBackend) -> None:
    from pythonnative.animated import AnimationResult, native_animation_completed

    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    results: list = []
    Animated.timing(v, to=1.0, duration=5000).start(results.append)
    _tag, anim_id, _prop, _spec = native_backend.native_started[0]

    # finished=False means the platform interrupted the animation; the
    # value must not jump to the target.
    native_animation_completed(anim_id, finished=False)
    assert v.value == 0.0
    _wait_until(lambda: bool(results))
    assert results == [AnimationResult(finished=False)]


# ======================================================================
# AnimationResult
# ======================================================================


def _wait_until(predicate: Any, timeout: float = 2.0) -> None:
    """Poll ``predicate``; completion callbacks are queued on the headless loop, so drain it while waiting."""
    from pythonnative import runtime

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        runtime.drain(timeout=0.02)
        time.sleep(0.005)
    assert predicate(), "condition not met in time"


@pytest.mark.asyncio
async def test_await_returns_finished_result() -> None:
    from pythonnative.animated import AnimationResult

    v = AnimatedValue(0.0)
    result = await Animated.timing(v, to=1.0, duration=30, easing="linear")
    assert result == AnimationResult(finished=True)
    assert result.finished is True
    assert (await Animated.delay(10)).finished is True
    assert (await Animated.spring(v, to=0.0, stiffness=300, damping=30)).finished is True


@pytest.mark.asyncio
async def test_stopped_animation_reports_unfinished() -> None:
    v = AnimatedValue(0.0)
    handle = Animated.timing(v, to=10.0, duration=1000, easing="linear")
    task = asyncio.create_task(_await(handle))
    await asyncio.sleep(0.05)
    handle.stop()
    result = await task
    assert result.finished is False
    assert v.value < 10.0


async def _await(handle: Any) -> Any:
    return await handle


@pytest.mark.asyncio
async def test_superseding_animation_reports_unfinished() -> None:
    v = AnimatedValue(0.0)
    first = Animated.timing(v, to=10.0, duration=1000, easing="linear")
    task = asyncio.create_task(_await(first))
    await asyncio.sleep(0.03)
    # Starting another animation on the same value interrupts the first.
    v.stop_animation()
    assert (await task).finished is False


def test_start_callback_receives_result() -> None:
    from pythonnative.animated import AnimationResult

    v = AnimatedValue(0.0)
    results: list = []
    Animated.timing(v, to=1.0, duration=30, easing="linear").start(results.append)
    _wait_until(lambda: bool(results))
    assert results == [AnimationResult(finished=True)]

    stopped: list = []
    handle = Animated.timing(v, to=5.0, duration=2000, easing="linear").start(stopped.append)
    handle.stop()
    _wait_until(lambda: bool(stopped))
    assert stopped == [AnimationResult(finished=False)]


def test_native_start_callback_receives_result(native_backend: _NativeBackend) -> None:
    from pythonnative.animated import AnimationResult, native_animation_completed

    v = AnimatedValue(0.0)
    v.attach(7, "opacity")
    results: list = []
    Animated.timing(v, to=1.0, duration=5000).start(results.append)
    _tag, anim_id, _prop, _spec = native_backend.native_started[0]
    native_animation_completed(anim_id, finished=True)
    _wait_until(lambda: bool(results))
    assert results == [AnimationResult(finished=True)]

    cancelled: list = []
    handle = Animated.timing(v, to=0.0, duration=5000).start(cancelled.append)
    handle.stop()
    _wait_until(lambda: bool(cancelled))
    assert cancelled == [AnimationResult(finished=False)]


@pytest.mark.asyncio
async def test_sequence_stops_early_and_reports_unfinished() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    first = Animated.timing(v1, to=1.0, duration=1000, easing="linear")
    second = Animated.timing(v2, to=1.0, duration=30, easing="linear")
    sequence = Animated.sequence([first, second])
    task = asyncio.create_task(_await(sequence))
    await asyncio.sleep(0.05)
    sequence.stop()
    result = await task
    assert result.finished is False
    # The interrupted step ends the sequence; the second step never ran.
    await asyncio.sleep(0.1)
    assert v2.value == 0.0


@pytest.mark.asyncio
async def test_parallel_and_stagger_finish_only_when_every_child_finishes() -> None:
    v1 = AnimatedValue(0.0)
    v2 = AnimatedValue(0.0)
    result = await Animated.parallel(
        [
            Animated.timing(v1, to=1.0, duration=30, easing="linear"),
            Animated.timing(v2, to=1.0, duration=30, easing="linear"),
        ]
    )
    assert result.finished is True

    slow = Animated.timing(v1, to=5.0, duration=1000, easing="linear")
    fast = Animated.timing(v2, to=5.0, duration=20, easing="linear")
    parallel = Animated.parallel([slow, fast])
    task = asyncio.create_task(_await(parallel))
    await asyncio.sleep(0.08)
    slow.stop()
    assert (await task).finished is False

    stagger = await Animated.stagger(10, [Animated.timing(v1, to=0.0, duration=20), Animated.delay(5)])
    assert stagger.finished is True


@pytest.mark.asyncio
async def test_loop_reports_finished_or_stopped() -> None:
    v = AnimatedValue(0.0)
    result = await Animated.loop(Animated.timing(v, to=1.0, duration=20, easing="linear"), iterations=2)
    assert result.finished is True

    loop = Animated.loop(Animated.timing(v, to=1.0, duration=20, easing="linear"))
    task = asyncio.create_task(_await(loop))
    await asyncio.sleep(0.06)
    loop.stop()
    assert (await task).finished is False


@pytest.mark.asyncio
async def test_composite_start_callback_receives_result() -> None:
    from pythonnative.animated import AnimationResult

    v = AnimatedValue(0.0)
    results: list = []
    Animated.sequence([Animated.timing(v, to=1.0, duration=20, easing="linear"), Animated.delay(5)]).start(
        results.append
    )
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not results:
        await asyncio.sleep(0.01)
    assert results == [AnimationResult(finished=True)]

    stopped: list = []
    loop = Animated.loop(Animated.timing(v, to=1.0, duration=20, easing="linear")).start(stopped.append)
    await asyncio.sleep(0.05)
    loop.stop()
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not stopped:
        await asyncio.sleep(0.01)
    assert stopped == [AnimationResult(finished=False)]


# ======================================================================
# Animatable props
# ======================================================================


def test_binding_non_animatable_style_key_raises() -> None:
    from pythonnative.animated import ANIMATABLE_PROPS, _resolve_style_with_values

    assert ANIMATABLE_PROPS == frozenset(
        {
            "opacity",
            "background_color",
            "color",
            "translate_x",
            "translate_y",
            "scale",
            "scale_x",
            "scale_y",
            "rotate",
            "rotate_x",
            "rotate_y",
        }
    )
    v = AnimatedValue(0.0)
    with pytest.raises(ValueError) as excinfo:
        _resolve_style_with_values({"width": v})
    message = str(excinfo.value)
    assert "'width'" in message and "opacity" in message and "translate_x" in message
    with pytest.raises(ValueError):
        _resolve_style_with_values({"margin": v})
    with pytest.raises(ValueError):
        _resolve_style_with_values({"transform": [{"skew_x": v}]})


def test_binding_animatable_keys_is_accepted() -> None:
    from pythonnative.animated import _resolve_style_with_values

    v = AnimatedValue(0.5)
    plain, bindings = _resolve_style_with_values({"opacity": v, "rotate_x": v, "transform": [{"rotate_y": v}]})
    assert set(bindings) == {"opacity", "rotate_x", "rotate_y"}
    assert plain["transform"] == [{"rotate_y": 0.5}, {"rotate_x": 0.5}]


# Suppress unused-import lint for the typing helper.
_ = Any
