"""Tests for the gesture system: descriptors, serialization, and the
pure-Python `GestureArbiter` used by the browser preview (and as the reference semantics).

The arbiter tests drive scripted pointer streams (positions in points,
times in seconds) and assert on the emitted payloads, which is exactly
the contract the platform handlers rely on.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Tuple

import pytest

from pythonnative.gestures import (
    GestureArbiter,
    GestureEvent,
    GestureState,
    Pan,
    Tap,
    serialize_gestures,
)

Emitted = Tuple[int, Dict[str, Any]]


def _arbiter(*specs: Dict[str, Any]) -> Tuple[GestureArbiter, List[Emitted]]:
    emitted: List[Emitted] = []
    arbiter = GestureArbiter(list(specs), lambda i, payload: emitted.append((i, payload)))
    return arbiter, emitted


def _states(emitted: List[Emitted]) -> List[str]:
    return [payload["state"] for _i, payload in emitted]


# ======================================================================
# Descriptors and serialization
# ======================================================================


def test_serialize_gestures_emits_config_and_routers() -> None:
    pans: List[GestureEvent] = []
    specs, events = serialize_gestures(
        [
            Tap(on_tap=lambda e: None),
            Pan(on_change=pans.append, min_distance=4.0),
        ]
    )
    assert specs == [
        {"kind": "tap", "n_taps": 1, "max_distance": 12.0, "simultaneous": [1], "wait_for": []},
        {"kind": "pan", "min_distance": 4.0, "min_pointers": 1, "simultaneous": [0], "wait_for": []},
    ]
    assert set(events) == {"gesture:0", "gesture:1"}

    events["gesture:1"]({"kind": "pan", "state": "changed", "translation_x": 9.0})
    assert len(pans) == 1 and pans[0].translation_x == 9.0


def test_serialize_passes_plain_dicts_through() -> None:
    specs, events = serialize_gestures([{"kind": "tap", "n_taps": 3}])
    assert specs == [{"kind": "tap", "n_taps": 3, "simultaneous": [], "wait_for": []}]
    assert events == {}


def test_router_drops_unknown_payload_keys() -> None:
    seen: List[GestureEvent] = []
    _specs, events = serialize_gestures([Tap(on_tap=seen.append)])
    events["gesture:0"]({"kind": "tap", "state": "ended", "x": 1.0, "_debug": "extra"})
    assert seen[0].x == 1.0


def test_gesture_state_is_a_str_enum_coerced_from_wire_strings() -> None:
    event = GestureEvent(kind="tap", state="ended")  # type: ignore[arg-type]
    assert event.state is GestureState.ENDED
    assert event.state == "ended"
    assert str(GestureState.BEGAN) == "began"
    assert json.dumps({"state": GestureState.CANCELLED}) == '{"state": "cancelled"}'
    with pytest.raises(ValueError):
        GestureEvent(kind="tap", state="exploded")  # type: ignore[arg-type]


def test_arbiter_emits_plain_string_states() -> None:
    arbiter, emitted = _arbiter({"kind": "tap"})
    arbiter.pointer_down(0, 10.0, 10.0, 0.0)
    arbiter.pointer_up(0, 10.0, 10.0, 0.05)
    assert emitted and all(type(p["state"]) is str for _i, p in emitted)


def test_descriptor_callback_routing_by_state() -> None:
    log: List[str] = []
    pan = Pan(
        on_begin=lambda e: log.append("begin"),
        on_change=lambda e: log.append("change"),
        on_end=lambda e: log.append("end"),
    )
    _specs, events = serialize_gestures([pan])
    router = events["gesture:0"]
    router({"kind": "pan", "state": "began"})
    router({"kind": "pan", "state": "changed"})
    router({"kind": "pan", "state": "ended"})
    router({"kind": "pan", "state": "cancelled"})
    assert log == ["begin", "change", "end", "end"]


# ======================================================================
# Tap recognition
# ======================================================================


def test_tap_recognized_on_quick_release() -> None:
    arbiter, emitted = _arbiter({"kind": "tap"})
    arbiter.pointer_down(1, 10.0, 20.0, t=0.0)
    arbiter.pointer_up(1, 10.0, 20.0, t=0.1)

    assert len(emitted) == 1
    index, payload = emitted[0]
    assert index == 0
    assert payload["state"] == "ended"
    assert payload["x"] == 10.0 and payload["y"] == 20.0


def test_tap_fails_when_pointer_travels_beyond_slop() -> None:
    arbiter, emitted = _arbiter({"kind": "tap", "max_distance": 12.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 30.0, 0.0, t=0.05)
    arbiter.pointer_up(1, 30.0, 0.0, t=0.1)
    assert emitted == []


def test_tap_fails_when_held_too_long() -> None:
    arbiter, emitted = _arbiter({"kind": "tap"})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=1.0)
    assert emitted == []


def test_double_tap_requires_two_quick_taps() -> None:
    arbiter, emitted = _arbiter({"kind": "tap", "n_taps": 2})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=0.05)
    assert emitted == [], "first tap alone must not fire a double-tap"
    arbiter.pointer_down(1, 0.0, 0.0, t=0.15)
    arbiter.pointer_up(1, 0.0, 0.0, t=0.2)
    assert _states(emitted) == ["ended"]


def test_double_tap_resets_after_gap() -> None:
    arbiter, emitted = _arbiter({"kind": "tap", "n_taps": 2})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=0.05)
    # Second tap arrives way past the multi-tap window.
    arbiter.pointer_down(1, 0.0, 0.0, t=2.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=2.05)
    assert emitted == []


# ======================================================================
# Long press
# ======================================================================


def test_long_press_activates_after_deadline_poll() -> None:
    arbiter, emitted = _arbiter({"kind": "long_press", "min_duration_ms": 100.0})
    arbiter.pointer_down(1, 5.0, 5.0, t=0.0)
    assert arbiter.next_deadline() == 0.1

    arbiter.poll(0.05)
    assert emitted == []

    arbiter.poll(0.12)
    assert _states(emitted) == ["began"]
    assert arbiter.next_deadline() is None

    arbiter.pointer_up(1, 5.0, 5.0, t=0.3)
    assert _states(emitted) == ["began", "ended"]


def test_long_press_cancelled_by_drift_after_activation() -> None:
    arbiter, emitted = _arbiter({"kind": "long_press", "min_duration_ms": 100.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.poll(0.15)
    arbiter.pointer_move(1, 50.0, 0.0, t=0.2)
    assert _states(emitted) == ["began", "cancelled"]


def test_long_press_never_fires_on_quick_release() -> None:
    arbiter, emitted = _arbiter({"kind": "long_press", "min_duration_ms": 100.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=0.05)
    arbiter.poll(0.2)
    assert emitted == []


# ======================================================================
# Pan
# ======================================================================


def test_pan_activates_after_min_distance_and_tracks_translation() -> None:
    arbiter, emitted = _arbiter({"kind": "pan", "min_distance": 10.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 5.0, 0.0, t=0.01)
    assert emitted == [], "below min_distance the pan must stay silent"
    assert arbiter.has_active_pan() is False

    arbiter.pointer_move(1, 20.0, 0.0, t=0.02)
    assert _states(emitted) == ["began"]
    assert arbiter.has_active_pan() is True

    arbiter.pointer_move(1, 32.0, 7.0, t=0.03)
    state = emitted[-1][1]
    assert state["state"] == "changed"
    # Translation is measured from the activation anchor (20, 0).
    assert state["translation_x"] == 12.0
    assert state["translation_y"] == 7.0
    assert state["velocity_x"] > 0.0

    arbiter.pointer_up(1, 40.0, 7.0, t=0.04)
    end = emitted[-1][1]
    assert end["state"] == "ended"
    assert end["translation_x"] == 20.0
    assert end["velocity_x"] > 0.0
    assert arbiter.has_active_pan() is False


def test_pan_cancel_emits_cancelled_when_active() -> None:
    arbiter, emitted = _arbiter({"kind": "pan", "min_distance": 5.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 20.0, 0.0, t=0.01)
    arbiter.cancel(t=0.02)
    assert _states(emitted) == ["began", "cancelled"]
    assert arbiter.has_active_pan() is False


# ======================================================================
# Swipe
# ======================================================================


def test_swipe_resolves_direction_from_release_velocity() -> None:
    arbiter, emitted = _arbiter({"kind": "swipe", "min_velocity": 300.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 60.0, 0.0, t=0.05)
    arbiter.pointer_up(1, 120.0, 0.0, t=0.1)

    assert len(emitted) == 1
    payload = emitted[0][1]
    assert payload["state"] == "ended"
    assert payload["direction"] == "right"
    assert payload["velocity_x"] > 300.0


def test_swipe_below_min_velocity_is_ignored() -> None:
    arbiter, emitted = _arbiter({"kind": "swipe", "min_velocity": 300.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 5.0, 0.0, t=0.5)
    arbiter.pointer_up(1, 10.0, 0.0, t=1.0)
    assert emitted == []


def test_swipe_direction_filter_rejects_other_axes() -> None:
    arbiter, emitted = _arbiter({"kind": "swipe", "direction": "up", "min_velocity": 100.0})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 200.0, 0.0, t=0.1)  # fast *rightward* flick
    assert emitted == []

    arbiter.pointer_down(1, 0.0, 200.0, t=1.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=1.1)  # fast upward flick
    assert [p["direction"] for _i, p in emitted] == ["up"]


# ======================================================================
# Pinch and rotation
# ======================================================================


def test_pinch_reports_scale_relative_to_initial_span() -> None:
    arbiter, emitted = _arbiter({"kind": "pinch"})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    assert emitted == [], "pinch needs two pointers"
    arbiter.pointer_down(2, 100.0, 0.0, t=0.01)
    assert _states(emitted) == ["began"]

    arbiter.pointer_move(2, 200.0, 0.0, t=0.05)
    changed = emitted[-1][1]
    assert changed["state"] == "changed"
    assert abs(changed["scale"] - 2.0) < 1e-9

    arbiter.pointer_up(2, 200.0, 0.0, t=0.1)
    ended = emitted[-1][1]
    assert ended["state"] == "ended"
    assert abs(ended["scale"] - 2.0) < 1e-9


def test_rotation_reports_radians_relative_to_initial_angle() -> None:
    arbiter, emitted = _arbiter({"kind": "rotation"})
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_down(2, 100.0, 0.0, t=0.01)
    assert _states(emitted) == ["began"]

    arbiter.pointer_move(2, 0.0, 100.0, t=0.05)
    changed = emitted[-1][1]
    assert abs(changed["rotation"] - math.pi / 2) < 1e-9


def test_multiple_gestures_recognize_simultaneously() -> None:
    arbiter, emitted = _arbiter(
        {"kind": "tap"},
        {"kind": "swipe", "min_velocity": 100.0},
    )
    # A slow, stationary tap: tap fires, swipe stays silent.
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 0.0, 0.0, t=0.05)
    assert [i for i, _p in emitted] == [0]

    # A fast flick: swipe fires (the movement makes the tap fail).
    arbiter.pointer_down(1, 0.0, 0.0, t=1.0)
    arbiter.pointer_move(1, 100.0, 0.0, t=1.05)
    arbiter.pointer_up(1, 200.0, 0.0, t=1.1)
    assert [i for i, _p in emitted] == [0, 1]


# ======================================================================
# End-to-end: gestures prop through the reconciler
# ======================================================================


def test_gesture_events_route_through_view_tag() -> None:
    from pythonnative.element import Element
    from pythonnative.events import dispatch_event
    from pythonnative.reconciler import Reconciler
    from pythonnative.testing import FakeBackend

    taps: List[GestureEvent] = []
    el = Element("View", {"gestures": [Tap(on_tap=taps.append)]}, [])
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    rec.mount(el)
    tag = rec.root_tag
    assert tag is not None

    # The native payload received serialized specs (no closures).
    view = backend.views[tag]
    assert view.props["gestures"] == [
        {"kind": "tap", "n_taps": 1, "max_distance": 12.0, "simultaneous": [], "wait_for": []}
    ]

    # A handler-side arbiter (as the browser preview runs) feeds dispatch_event.
    def _emit(i: int, payload: Dict[str, Any]) -> None:
        dispatch_event(tag, f"gesture:{i}", payload)

    arbiter = GestureArbiter(view.props["gestures"], _emit)
    arbiter.pointer_down(1, 3.0, 4.0, t=0.0)
    arbiter.pointer_up(1, 3.0, 4.0, t=0.1)

    assert len(taps) == 1
    assert isinstance(taps[0], GestureEvent)
    assert taps[0].x == 3.0 and taps[0].y == 4.0
