"""Unit tests for pn.use_async_effect, pn.use_query, pn.use_mutation."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from fake_backend import FakeBackend as _StubBackend

from pythonnative.element import Element
from pythonnative.hooks import (
    MutationCall,
    QueryResult,
    component,
    use_async_effect,
    use_mutation,
    use_query,
    use_state,
)
from pythonnative.reconciler import Reconciler


def _wait_for(predicate: Any, timeout: float = 2.0) -> bool:
    """Spin until ``predicate`` returns truthy, or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ======================================================================
# use_async_effect
# ======================================================================


def test_use_async_effect_runs_on_mount() -> None:
    fired = threading.Event()

    @component
    def screen() -> Element:
        async def effect() -> None:
            fired.set()

        use_async_effect(effect, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert fired.wait(2.0)


def test_use_async_effect_cancels_on_unmount() -> None:
    cancelled = threading.Event()
    started = threading.Event()

    @component
    def screen() -> Element:
        async def effect() -> None:
            started.set()
            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        use_async_effect(effect, [])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert started.wait(2.0)
    # The reconciler exposes destruction via the internal walker;
    # public-API unmount is the host's responsibility on real screens.
    assert rec._tree is not None
    rec._destroy_tree(rec._tree)
    assert cancelled.wait(2.0)


def test_use_async_effect_reruns_on_deps_change() -> None:
    fired_with: list = []

    @component
    def screen(value: int = 0) -> Element:
        async def effect() -> None:
            fired_with.append(value)

        use_async_effect(effect, [value])
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen(0))
    assert _wait_for(lambda: fired_with == [0])
    rec.reconcile(screen(1))
    assert _wait_for(lambda: fired_with == [0, 1])
    rec.reconcile(screen(1))
    # Same value → no rerun.
    time.sleep(0.1)
    assert fired_with == [0, 1]


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

    # Drive the runtime + reconciler until the fetch lands.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rec.reconcile(screen())
        if captured[-1].data == "hello":
            break
        time.sleep(0.01)

    assert captured[-1].data == "hello"
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

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rec.reconcile(screen())
        if captured[-1].error is not None:
            break
        time.sleep(0.01)

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

    # First fetch.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rec.reconcile(screen())
        if captured[-1].data == 1:
            break
        time.sleep(0.01)
    assert captured[-1].data == 1

    # Trigger refetch.
    captured[-1].refetch()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rec.reconcile(screen())
        if captured[-1].data == 2:
            break
        time.sleep(0.01)
    assert captured[-1].data == 2


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

    mutate = triggered[-1]
    call = mutate(7)
    assert isinstance(call, MutationCall)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rec.reconcile(screen())
        if captured_state[-1].data == 14:
            break
        time.sleep(0.01)
    assert captured_state[-1].data == 14
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

    assert asyncio.run(call_and_await()) == 42


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
    mutate = triggered[-1]
    call = mutate()
    # Discarding the call is fine; the state will reflect the failure.

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rec.reconcile(screen())
        if captured_state[-1].error is not None:
            break
        time.sleep(0.01)
    assert isinstance(captured_state[-1].error, ValueError)
    assert call.done() is True


# Suppress unused-import lint when running just the file.
_ = use_state, pytest
