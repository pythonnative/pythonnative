"""Tests for the pan activation rules shared by every renderer.

The pure-Python ``GestureArbiter`` is the executable specification the
iOS, Android, and browser recognizers follow, so these scripted pointer
streams pin down exactly when a ``Pan`` with ``active_offset_*``,
``fail_offset_*``, ``max_pointers``, ``min_velocity``, and
``min_distance`` activates, fails, or is cancelled.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from pythonnative.gestures import DEFAULT_PAN_MIN_DISTANCE, GestureArbiter, Pan, serialize_gestures

Emitted = List[Tuple[int, Dict[str, Any]]]


def _pan(**kwargs: Any) -> Tuple[GestureArbiter, Emitted]:
    specs, _events = serialize_gestures([Pan(**kwargs)])
    emitted: Emitted = []
    return GestureArbiter(specs, lambda i, p: emitted.append((i, p))), emitted


def _states(emitted: Emitted) -> List[str]:
    return [p["state"] for _i, p in emitted]


# ======================================================================
# Descriptor normalization and validation
# ======================================================================


def test_pan_config_defaults() -> None:
    config = Pan()._config()
    assert config["min_distance"] == DEFAULT_PAN_MIN_DISTANCE
    assert config["min_pointers"] == 1
    assert config["max_pointers"] is None
    assert config["min_velocity"] is None
    assert all(config[key] is None for key in ("active_offset_x", "active_offset_y", "fail_offset_x", "fail_offset_y"))


def test_pan_offsets_normalize_to_bound_pairs() -> None:
    config = Pan(active_offset_x=30, active_offset_y=-15, fail_offset_x=(-5, 40), fail_offset_y=(-8.0, 8.0))._config()
    # A positive number bounds the positive direction only, a negative one the negative direction only.
    assert config["active_offset_x"] == [None, 30.0]
    assert config["active_offset_y"] == [-15.0, None]
    assert config["fail_offset_x"] == [-5.0, 40.0]
    assert config["fail_offset_y"] == [-8.0, 8.0]


def test_pan_custom_activation_criteria_disable_default_min_distance() -> None:
    assert Pan(active_offset_x=20)._config()["min_distance"] is None
    assert Pan(min_velocity=500)._config()["min_distance"] is None
    assert Pan(fail_offset_y=(-10, 10))._config()["min_distance"] is None
    # An explicit min_distance always survives.
    assert Pan(active_offset_x=20, min_distance=6)._config()["min_distance"] == 6.0


def test_pan_validation_errors() -> None:
    with pytest.raises(ValueError):
        Pan(active_offset_x=(10, 20))  # negative bound must be <= 0
    with pytest.raises(ValueError):
        Pan(fail_offset_y=(-10, -1))  # positive bound must be >= 0
    with pytest.raises(TypeError):
        Pan(active_offset_x="far")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Pan(min_pointers=2, max_pointers=1)
    with pytest.raises(ValueError):
        Pan(min_distance=-1)
    with pytest.raises(ValueError):
        Pan(min_velocity=-1)


# ======================================================================
# active_offset
# ======================================================================


def test_active_offset_x_positive_is_one_sided() -> None:
    arbiter, emitted = _pan(active_offset_x=30)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    # Far beyond the default min_distance, but the offset criterion replaces it.
    arbiter.pointer_move(1, 25.0, 0.0, t=0.01)
    assert emitted == []
    # Moving left never activates a positive-only threshold.
    arbiter.pointer_move(1, -80.0, 0.0, t=0.02)
    assert emitted == []
    # Crossing the bound (strictly greater) activates.
    arbiter.pointer_move(1, 30.0, 0.0, t=0.03)
    assert emitted == []
    arbiter.pointer_move(1, 31.0, 0.0, t=0.04)
    assert _states(emitted) == ["began"]
    # Translation is measured from the activation point.
    arbiter.pointer_move(1, 41.0, 0.0, t=0.05)
    assert emitted[-1][1]["translation_x"] == 10.0


def test_active_offset_x_negative_is_one_sided() -> None:
    arbiter, emitted = _pan(active_offset_x=-30)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 80.0, 0.0, t=0.01)
    assert emitted == []
    arbiter.pointer_move(1, -31.0, 0.0, t=0.02)
    assert _states(emitted) == ["began"]


def test_active_offset_pair_activates_in_either_direction() -> None:
    arbiter, emitted = _pan(active_offset_y=(-20, 40))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 0.0, 30.0, t=0.01)
    assert emitted == []
    arbiter.pointer_move(1, 0.0, -21.0, t=0.02)
    assert _states(emitted) == ["began"]

    arbiter2, emitted2 = _pan(active_offset_y=(-20, 40))
    arbiter2.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter2.pointer_move(1, 0.0, 41.0, t=0.01)
    assert _states(emitted2) == ["began"]


def test_explicit_min_distance_combines_with_offsets() -> None:
    arbiter, emitted = _pan(active_offset_x=100, min_distance=10)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    # Any direction: min_distance is still an activation criterion.
    arbiter.pointer_move(1, 0.0, 12.0, t=0.01)
    assert _states(emitted) == ["began"]


# ======================================================================
# fail_offset
# ======================================================================


def test_fail_offset_y_fails_pan_for_the_interaction() -> None:
    arbiter, emitted = _pan(active_offset_x=20, fail_offset_y=(-15, 15))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 5.0, 16.0, t=0.01)  # vertical travel beyond the fail bound
    assert emitted == []
    # A later horizontal drag would satisfy active_offset_x, but the pan has failed.
    arbiter.pointer_move(1, 60.0, 16.0, t=0.02)
    arbiter.pointer_up(1, 60.0, 16.0, t=0.03)
    assert emitted == []
    # The next interaction starts clean.
    arbiter.pointer_down(1, 0.0, 0.0, t=1.0)
    arbiter.pointer_move(1, 25.0, 0.0, t=1.01)
    assert _states(emitted) == ["began"]


def test_fail_offset_single_number_is_one_sided() -> None:
    arbiter, emitted = _pan(fail_offset_x=-10, min_distance=30)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 20.0, 0.0, t=0.01)  # rightward travel is fine
    arbiter.pointer_move(1, 35.0, 0.0, t=0.02)
    assert _states(emitted) == ["began"]

    arbiter2, emitted2 = _pan(fail_offset_x=-10, min_distance=30)
    arbiter2.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter2.pointer_move(1, -11.0, 0.0, t=0.01)  # leftward travel fails
    arbiter2.pointer_move(1, -50.0, 0.0, t=0.02)
    assert emitted2 == []


def test_fail_offset_does_not_apply_after_activation() -> None:
    arbiter, emitted = _pan(min_distance=10, fail_offset_y=(-15, 15))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 12.0, 0.0, t=0.01)
    assert _states(emitted) == ["began"]
    arbiter.pointer_move(1, 12.0, 80.0, t=0.02)
    assert _states(emitted) == ["began", "changed"]


# ======================================================================
# max_pointers
# ======================================================================


def test_max_pointers_fails_inactive_pan_and_cancels_active_pan() -> None:
    arbiter, emitted = _pan(max_pointers=1, min_distance=10)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_down(2, 50.0, 0.0, t=0.01)  # second finger: too many
    arbiter.pointer_move(1, 40.0, 0.0, t=0.02)
    arbiter.pointer_move(2, 90.0, 0.0, t=0.02)
    assert emitted == []
    arbiter.pointer_up(1, 40.0, 0.0, t=0.03)
    arbiter.pointer_up(2, 90.0, 0.0, t=0.03)
    assert emitted == []

    arbiter2, emitted2 = _pan(max_pointers=1, min_distance=10)
    arbiter2.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter2.pointer_move(1, 20.0, 0.0, t=0.01)
    assert _states(emitted2) == ["began"]
    arbiter2.pointer_down(2, 50.0, 0.0, t=0.02)
    assert _states(emitted2) == ["began", "cancelled"]
    assert arbiter2.has_active_pan() is False


# ======================================================================
# min_velocity
# ======================================================================


def test_min_velocity_activates_on_speed_regardless_of_distance() -> None:
    arbiter, emitted = _pan(min_velocity=500.0)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    # 3 points over 100 ms: 30 pt/s, too slow (and no distance criterion applies).
    arbiter.pointer_move(1, 3.0, 0.0, t=0.1)
    assert emitted == []
    # 6 points in 10 ms on top of the window: fast enough.
    arbiter.pointer_move(1, 9.0, 0.0, t=0.11)
    assert _states(emitted) == ["began"]


def test_min_velocity_alone_ignores_default_min_distance() -> None:
    arbiter, emitted = _pan(min_velocity=500.0)
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 50.0, 0.0, t=1.0)  # 50 pt/s: slow, but far past 10 points
    assert emitted == []


# ======================================================================
# Hand-built specs follow the same defaults
# ======================================================================


def test_hand_built_spec_without_min_distance_uses_default_only_without_criteria() -> None:
    emitted: Emitted = []
    arbiter = GestureArbiter([{"kind": "pan"}], lambda i, p: emitted.append((i, p)))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, 12.0, 0.0, t=0.01)
    assert _states(emitted) == ["began"]

    emitted2: Emitted = []
    arbiter2 = GestureArbiter([{"kind": "pan", "active_offset_x": 30}], lambda i, p: emitted2.append((i, p)))
    arbiter2.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter2.pointer_move(1, 12.0, 0.0, t=0.01)
    assert emitted2 == []
    arbiter2.pointer_move(1, 31.0, 0.0, t=0.02)
    assert _states(emitted2) == ["began"]


def test_hand_built_spec_accepts_wire_form_bounds() -> None:
    emitted: Emitted = []
    arbiter = GestureArbiter([{"kind": "pan", "active_offset_x": [None, 30.0]}], lambda i, p: emitted.append((i, p)))
    arbiter.pointer_down(1, 0.0, 0.0, t=0.0)
    arbiter.pointer_move(1, -40.0, 0.0, t=0.01)
    assert emitted == []
    arbiter.pointer_move(1, 31.0, 0.0, t=0.02)
    assert _states(emitted) == ["began"]
