"""Unit tests for gesture composition (Simultaneous / Race / Exclusive),
Fling, and the arbiter's cross-gesture arbitration."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pythonnative.gestures import (
    Exclusive,
    Fling,
    GestureArbiter,
    LongPress,
    Pan,
    Pinch,
    Race,
    Rotation,
    Simultaneous,
    Tap,
    serialize_gestures,
)

Emitted = List[Tuple[int, Dict[str, Any]]]


def _arbiter(*specs: Dict[str, Any]) -> Tuple[GestureArbiter, Emitted]:
    emitted: Emitted = []
    arbiter = GestureArbiter(list(specs), lambda i, p: emitted.append((i, p)))
    return arbiter, emitted


def _compose(*nodes: Any) -> Tuple[GestureArbiter, Emitted, List[Dict[str, Any]]]:
    specs, _events = serialize_gestures(list(nodes))
    emitted: Emitted = []
    arbiter = GestureArbiter(specs, lambda i, p: emitted.append((i, p)))
    return arbiter, emitted, specs


# ======================================================================
# Serialization: relationship metadata
# ======================================================================


def test_flat_list_is_mutually_simultaneous() -> None:
    specs, _ = serialize_gestures([Tap(), Pan(), Pinch()])
    assert specs[0]["simultaneous"] == [1, 2]
    assert specs[1]["simultaneous"] == [0, 2]
    assert specs[2]["simultaneous"] == [0, 1]
    assert all(s["wait_for"] == [] for s in specs)


def test_race_members_are_exclusive() -> None:
    specs, _ = serialize_gestures([Race(Pan(), LongPress())])
    assert specs[0]["simultaneous"] == []
    assert specs[1]["simultaneous"] == []
    assert all(s["wait_for"] == [] for s in specs)


def test_exclusive_orders_by_priority() -> None:
    specs, _ = serialize_gestures([Exclusive(Tap(n_taps=2), Tap())])
    assert specs[0]["wait_for"] == []
    assert specs[1]["wait_for"] == [0]
    assert specs[0]["simultaneous"] == []
    assert specs[1]["simultaneous"] == []


def test_simultaneous_nested_in_race() -> None:
    specs, _ = serialize_gestures([Race(Simultaneous(Pinch(), Rotation()), Pan())])
    # Pinch and rotation recognize together but both race the pan.
    assert specs[0]["simultaneous"] == [1]
    assert specs[1]["simultaneous"] == [0]
    assert specs[2]["simultaneous"] == []


def test_top_level_siblings_are_simultaneous_with_group_leaves() -> None:
    specs, _ = serialize_gestures([Race(Pan(), LongPress()), Tap()])
    # The tap is simultaneous with both raced gestures; the raced pair
    # stays exclusive.
    assert specs[0]["simultaneous"] == [2]
    assert specs[1]["simultaneous"] == [2]
    assert specs[2]["simultaneous"] == [0, 1]


def test_routers_cover_all_leaves() -> None:
    _specs, events = serialize_gestures([Race(Pan(), Exclusive(Tap(n_taps=2), Tap()))])
    assert set(events) == {"gesture:0", "gesture:1", "gesture:2"}


# ======================================================================
# Race arbitration
# ======================================================================


def test_race_pan_activation_blocks_long_press() -> None:
    arbiter, emitted, _ = _compose(Race(Pan(min_distance=10.0), LongPress(min_duration_ms=100.0)))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 30.0, 0.0, t=0.05)  # pan activates
    assert [(i, p["state"]) for i, p in emitted] == [(0, "began")]
    # Long-press deadline passes, but it already lost the race.
    arbiter.poll(t=0.5)
    assert [(i, p["state"]) for i, p in emitted] == [(0, "began")]


def test_race_long_press_activation_blocks_pan() -> None:
    arbiter, emitted, _ = _compose(Race(Pan(min_distance=10.0), LongPress(min_duration_ms=100.0)))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.poll(t=0.2)  # long-press activates
    assert [(i, p["state"]) for i, p in emitted] == [(1, "began")]
    # A drag afterward must not start the pan.
    arbiter.pointer_move(1, 40.0, 0.0, t=0.3)
    states = [(i, p["state"]) for i, p in emitted]
    assert (0, "began") not in states


def test_race_resets_for_next_interaction() -> None:
    arbiter, emitted, _ = _compose(Race(Pan(min_distance=10.0), LongPress(min_duration_ms=100.0)))
    # First interaction: pan wins.
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 30.0, 0.0, t=0.05)
    arbiter.pointer_up(1, 30.0, 0.0, t=0.1)
    emitted.clear()
    # Second interaction: long-press can win now.
    arbiter.pointer_down(1, 0.0, 0.0, t=1.0)
    arbiter.poll(t=1.2)
    assert [(i, p["state"]) for i, p in emitted] == [(1, "began")]


def test_flat_list_still_recognizes_simultaneously() -> None:
    arbiter, emitted, _ = _compose(Pinch(), Rotation())
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_down(2, 100.0, 0.0, t=0.01)
    arbiter.pointer_move(2, 0.0, 100.0, t=0.05)
    indices = {i for i, _p in emitted}
    assert indices == {0, 1}


# ======================================================================
# Exclusive: double tap vs single tap
# ======================================================================


def test_exclusive_single_tap_waits_out_double_tap_window() -> None:
    arbiter, emitted, _ = _compose(Exclusive(Tap(n_taps=2), Tap()))
    arbiter.pointer_down(1, 5.0, 5.0, t=0.0)
    arbiter.pointer_up(1, 5.0, 5.0, t=0.05)
    # The single tap completed but is parked while the double tap is
    # still possible.
    assert emitted == []
    # The double-tap window expires; the buffered single tap flushes.
    arbiter.poll(t=0.5)
    assert [(i, p["state"]) for i, p in emitted] == [(1, "ended")]


def test_exclusive_double_tap_wins_and_silences_single() -> None:
    arbiter, emitted, _ = _compose(Exclusive(Tap(n_taps=2), Tap()))
    arbiter.pointer_down(1, 5.0, 5.0, t=0.0)
    arbiter.pointer_up(1, 5.0, 5.0, t=0.05)
    arbiter.pointer_down(1, 5.0, 5.0, t=0.15)
    arbiter.pointer_up(1, 5.0, 5.0, t=0.2)
    assert [(i, p["state"]) for i, p in emitted] == [(0, "ended")]
    # Later polling flushes nothing (the single tap was discarded).
    arbiter.poll(t=1.0)
    assert len(emitted) == 1


def test_exclusive_next_interaction_works_after_flush() -> None:
    arbiter, emitted, _ = _compose(Exclusive(Tap(n_taps=2), Tap()))
    arbiter.pointer_down(1, 5.0, 5.0, t=0.0)
    arbiter.pointer_up(1, 5.0, 5.0, t=0.05)
    arbiter.poll(t=0.5)
    emitted.clear()
    # A fresh double tap in the next interaction still wins.
    arbiter.pointer_down(1, 5.0, 5.0, t=2.0)
    arbiter.pointer_up(1, 5.0, 5.0, t=2.05)
    arbiter.pointer_down(1, 5.0, 5.0, t=2.15)
    arbiter.pointer_up(1, 5.0, 5.0, t=2.2)
    assert [(i, p["state"]) for i, p in emitted] == [(0, "ended")]


# ======================================================================
# Fling
# ======================================================================


def test_fling_single_pointer_matches_direction() -> None:
    specs, _ = serialize_gestures([Fling(direction="right", min_velocity=100.0)])
    arbiter, emitted = _arbiter(*specs)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 200.0, 0.0, t=0.1)
    assert len(emitted) == 1
    assert emitted[0][1]["direction"] == "right"


def test_fling_requires_pointer_count() -> None:
    specs, _ = serialize_gestures([Fling(direction="down", n_pointers=2, min_velocity=100.0)])
    arbiter, emitted = _arbiter(*specs)
    # One-finger flick: too few pointers.
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_up(1, 0.0, 200.0, t=0.1)
    assert emitted == []
    # Two-finger flick fires.
    arbiter.pointer_down(1, 0.0, 0.0, t=1.0)
    arbiter.pointer_down(2, 30.0, 0.0, t=1.01)
    arbiter.pointer_move(1, 0.0, 100.0, t=1.05)
    arbiter.pointer_move(2, 30.0, 100.0, t=1.05)
    arbiter.pointer_up(1, 0.0, 200.0, t=1.1)
    arbiter.pointer_up(2, 30.0, 200.0, t=1.1)
    assert len(emitted) == 1
    payload = emitted[0][1]
    assert payload["kind"] == "fling"
    assert payload["direction"] == "down"
    assert payload["pointer_count"] == 2


def test_fling_dispatch_routes_on_fling() -> None:
    seen: List[Any] = []
    _specs, events = serialize_gestures([Fling(on_fling=seen.append, min_velocity=100.0)])
    events["gesture:0"]({"kind": "fling", "state": "ended", "direction": "left"})
    assert len(seen) == 1 and seen[0].direction == "left"


# ======================================================================
# Wait-for with continuous gestures
# ======================================================================


def test_exclusive_pan_waits_for_long_press_failure() -> None:
    # Pan yields to long-press: it may only start once the press fails
    # (finger moved beyond the press slop).
    arbiter, emitted, _ = _compose(
        Exclusive(LongPress(min_duration_ms=500.0, max_distance=12.0), Pan(min_distance=5.0))
    )
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    # 8 points of travel: pan wants to activate (min 5) but the
    # long-press hasn't failed yet (slop 12), so output is parked.
    arbiter.pointer_move(1, 8.0, 0.0, t=0.02)
    assert emitted == []
    # 20 points: the long-press fails; the pan's buffered began/changed
    # stream flushes in order.
    arbiter.pointer_move(1, 20.0, 0.0, t=0.04)
    states = [(i, p["state"]) for i, p in emitted]
    assert states[0] == (1, "began")
    assert (1, "changed") in states


def test_cancel_discards_parked_activations() -> None:
    arbiter, emitted, _ = _compose(Exclusive(Tap(n_taps=2), Tap()))
    arbiter.pointer_down(1, 5.0, 5.0, t=0.0)
    arbiter.pointer_up(1, 5.0, 5.0, t=0.05)
    assert emitted == []
    arbiter.cancel(t=0.1)
    arbiter.poll(t=1.0)
    assert emitted == []
