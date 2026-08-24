"""Unit tests for async effects (use_effect), pn.use_query, pn.use_mutation."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fake_backend import FakeBackend as _StubBackend

from pythonnative.element import Element
from pythonnative.hooks import (
    MutationCall,
    QueryResult,
    component,
    use_effect,
    use_mutation,
    use_query,
    use_state,
)
from pythonnative.reconciler import Reconciler
from pythonnative.runtime import drain, run_blocking


def _settle(rec: Reconciler, predicate: Any, timeout: float = 2.0) -> bool:
    """Pump the framework loop and flush renders until ``predicate`` holds."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        drain(timeout=0.05)
        rec.flush_dirty()
        if predicate():
            return True
    return False


# ======================================================================
# Async use_effect (coroutine effects)
# ======================================================================


def test_async_effect_runs_on_mount() -> None:
    fired: list = []

    @component
    def screen() -> Element:
        async def effect() -> None:
            fired.append(True)

        use_effect(effect, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    drain()
    assert fired == [True]


def test_async_effect_cancels_on_unmount() -> None:
    events: list = []

    @component
    def screen() -> Element:
        async def effect() -> None:
            events.append("started")
            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                events.append("cancelled")
                raise

        use_effect(effect, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    drain(until=lambda: "started" in events)
    assert events == ["started"]

    rec.unmount()
    drain(until=lambda: "cancelled" in events)
    assert events == ["cancelled", "started"] or events == ["started", "cancelled"]


def test_async_effect_reruns_on_deps_change() -> None:
    fired_with: list = []

    @component
    def screen(value: int = 0) -> Element:
        async def effect() -> None:
            fired_with.append(value)

        use_effect(effect, [value])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen(0))
    drain()
    assert fired_with == [0]
    rec.reconcile(screen(1))
    drain()
    assert fired_with == [0, 1]
    rec.reconcile(screen(1))
    drain()
    # Same value: no rerun.
    assert fired_with == [0, 1]


def test_async_effect_completed_cleanup_runs() -> None:
    """An async effect that returns a callable gets that callable run
    as its cleanup once the effect re-runs or the component unmounts."""
    events: list = []

    @component
    def screen() -> Element:
        async def effect() -> Any:
            events.append("ran")
            return lambda: events.append("cleaned")

        use_effect(effect, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    drain()
    assert events == ["ran"]
    rec.unmount()
    drain()
    assert events == ["ran", "cleaned"]


def test_sync_effect_still_works() -> None:
    events: list = []

    @component
    def screen() -> Element:
        def effect() -> Any:
            events.append("ran")
            return lambda: events.append("cleaned")

        use_effect(effect, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert events == ["ran"]
    rec.unmount()
    assert events == ["ran", "cleaned"]


def test_async_effect_state_update_triggers_local_rerender() -> None:
    """The core async-first loop: an async effect awaits, sets state,
    and the component re-renders locally, all on one thread."""
    snapshots: list = []

    @component
    def screen() -> Element:
        message, set_message = use_state("loading")
        snapshots.append(message)

        async def load() -> None:
            await asyncio.sleep(0)
            set_message("done")

        use_effect(load, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert snapshots[-1] == "loading"
    assert _settle(rec, lambda: snapshots[-1] == "done")


# ======================================================================
# use_query
# ======================================================================


def test_use_query_resolves_to_data() -> None:
    captured: list = []

    @component
    def screen() -> Element:
        async def fetcher() -> str:
            return "hello"

        q = use_query(fetcher, [])
        captured.append(q)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())

    # First snapshot is loading=True.
    assert captured[0].loading is True
    assert captured[0].data is None

    assert _settle(rec, lambda: captured[-1].data == "hello")
    assert captured[-1].loading is False
    assert captured[-1].error is None


def test_use_query_captures_error() -> None:
    captured: list = []

    @component
    def screen() -> Element:
        async def fetcher() -> str:
            raise RuntimeError("boom")

        q = use_query(fetcher, [])
        captured.append(q)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())

    assert _settle(rec, lambda: captured[-1].error is not None)
    assert isinstance(captured[-1].error, RuntimeError)
    assert captured[-1].loading is False


def test_use_query_refetches_when_called() -> None:
    counter = {"calls": 0}
    captured: list = []

    @component
    def screen() -> Element:
        async def fetcher() -> int:
            counter["calls"] += 1
            return counter["calls"]

        q = use_query(fetcher, [])
        captured.append(q)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())

    assert _settle(rec, lambda: captured[-1].data == 1)

    captured[-1].refetch()
    assert _settle(rec, lambda: captured[-1].data == 2)


def test_use_query_returns_query_result_dataclass() -> None:
    captured: list = []

    @component
    def screen() -> Element:
        q = use_query(lambda: _resolved("x"), [])
        captured.append(q)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert isinstance(captured[0], QueryResult)


async def _resolved(value: Any) -> Any:
    return value


# ======================================================================
# use_mutation
# ======================================================================


def test_use_mutation_runs_and_resolves() -> None:
    captured_state: list = []
    triggered: list = []

    @component
    def screen() -> Element:
        async def mutator(x: int) -> int:
            return x * 2

        state, mutate = use_mutation(mutator)
        captured_state.append(state)
        triggered.append(mutate)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert captured_state[0].loading is False
    assert captured_state[0].data is None

    call = triggered[-1](7)
    assert isinstance(call, MutationCall)

    assert _settle(rec, lambda: captured_state[-1].data == 14)
    assert captured_state[-1].loading is False


def test_use_mutation_awaitable_returns_value() -> None:
    triggered: list = []

    @component
    def screen() -> Element:
        async def mutator(x: int) -> int:
            return x + 1

        _state, mutate = use_mutation(mutator)
        triggered.append(mutate)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    mutate = triggered[-1]

    async def call_and_await() -> int:
        return await mutate(41)

    assert run_blocking(call_and_await(), timeout=2.0) == 42


def test_use_mutation_captures_error() -> None:
    captured_state: list = []
    triggered: list = []

    @component
    def screen() -> Element:
        async def mutator() -> None:
            raise ValueError("fail")

        state, mutate = use_mutation(mutator)
        captured_state.append(state)
        triggered.append(mutate)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    call = triggered[-1]()
    # Discarding the call is fine; the state will reflect the failure.

    assert _settle(rec, lambda: captured_state[-1].error is not None)
    assert isinstance(captured_state[-1].error, ValueError)
    assert call.done() is True


# Suppress unused-import lint when running just the file.
_ = pytest
