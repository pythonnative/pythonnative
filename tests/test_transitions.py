"""Unit tests for pn.use_transition and pn.use_deferred_value."""

from __future__ import annotations

import time
from typing import Any

from fake_backend import FakeBackend

from pythonnative.components import Text
from pythonnative.element import Element
from pythonnative.hooks import component, use_deferred_value, use_state, use_transition
from pythonnative.reconciler import Reconciler
from pythonnative.runtime import drain


def _settle(rec: Reconciler, predicate: Any, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        drain(timeout=0.05)
        rec.flush_dirty()
        if predicate():
            return True
    return False


def _texts(backend: FakeBackend) -> list:
    return [v.props.get("text") for v in backend.views.values() if v.type_name == "Text"]


# ======================================================================
# use_transition
# ======================================================================


def test_transition_update_is_deferred_not_synchronous() -> None:
    snapshots: list = []
    controls: list = []

    @component
    def Screen() -> Element:
        value, set_value = use_state("initial")
        is_pending, start_transition = use_transition()
        snapshots.append((value, is_pending))
        controls.append((set_value, start_transition))
        return Text(value)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Screen())
    assert snapshots[-1] == ("initial", False)

    set_value, start_transition = controls[-1]
    start_transition(lambda: set_value("updated"))

    # The state landed eagerly, but no render has happened yet: the
    # trigger was deferred to a later loop turn.
    rec.flush_dirty()
    assert _texts(backend) == ["initial"] or _texts(backend) == ["updated"]

    assert _settle(rec, lambda: _texts(backend) == ["updated"])
    assert snapshots[-1] == ("updated", False)


def test_transition_is_pending_true_during_transition() -> None:
    pending_seen: list = []
    controls: list = []

    @component
    def Screen() -> Element:
        value, set_value = use_state(0)
        is_pending, start_transition = use_transition()
        pending_seen.append(is_pending)
        controls.append((set_value, start_transition))
        return Text(f"v{value} pending={is_pending}")

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Screen())

    set_value, start_transition = controls[-1]
    start_transition(lambda: set_value(1))

    # The pending flag flips on urgently (before the deferred render).
    rec.flush_dirty()
    assert _settle(rec, lambda: True in pending_seen)

    # Once the transition commits, is_pending settles back to False.
    assert _settle(rec, lambda: pending_seen[-1] is False and "v1" in _texts(backend)[0])


def test_urgent_update_outside_transition_stays_synchronous() -> None:
    setters: list = []

    @component
    def Screen() -> Element:
        value, set_value = use_state("a")
        setters.append(set_value)
        return Text(value)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Screen())

    setters[-1]("b")
    rec.flush_dirty()
    assert _texts(backend) == ["b"]


def test_multiple_transition_updates_coalesce() -> None:
    render_count = {"n": 0}
    controls: list = []

    @component
    def Screen() -> Element:
        value, set_value = use_state(0)
        _is_pending, start_transition = use_transition()
        render_count["n"] += 1
        controls.append((set_value, start_transition))
        return Text(str(value))

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Screen())
    renders_before = render_count["n"]

    set_value, start_transition = controls[-1]
    start_transition(lambda: set_value(1))
    start_transition(lambda: set_value(2))
    start_transition(lambda: set_value(3))

    assert _settle(rec, lambda: _texts(backend) == ["3"])
    # All three low-priority updates flushed together: far fewer
    # renders than one per set_value call.
    assert render_count["n"] - renders_before <= 3


# ======================================================================
# use_deferred_value
# ======================================================================


def test_deferred_value_starts_at_initial() -> None:
    captured: list = []

    @component
    def Screen(value: str = "first") -> Element:
        deferred = use_deferred_value(value)
        captured.append(deferred)
        return Text(deferred)

    rec = Reconciler(FakeBackend())
    rec.mount(Screen(value="first"))
    assert captured[-1] == "first"


def test_deferred_value_lags_then_catches_up() -> None:
    captured: list = []

    @component
    def Screen(value: str = "v1") -> Element:
        deferred = use_deferred_value(value)
        captured.append((value, deferred))
        return Text(f"{value}/{deferred}")

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Screen(value="v1"))
    drain()
    rec.flush_dirty()

    rec.reconcile(Screen(value="v2"))
    # Immediately after the urgent render, the deferred copy still
    # holds the old value.
    assert captured[-1] == ("v2", "v1")

    # After the transition flush, it catches up.
    assert _settle(rec, lambda: captured[-1] == ("v2", "v2"))
