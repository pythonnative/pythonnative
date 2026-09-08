"""Unit tests for async components, Suspense, use_resource, and lazy."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from pythonnative.component import component
from pythonnative.components import ErrorBoundary, Suspense, Text, View
from pythonnative.element import Element
from pythonnative.hooks import use_resource, use_state
from pythonnative.reconciler import Reconciler
from pythonnative.runtime import create_future, drain, resolve_future
from pythonnative.suspense import Suspend, lazy, start_resource
from pythonnative.testing import FakeBackend, FakeView


def _settle(rec: Reconciler, predicate: Any, timeout: float = 2.0) -> bool:
    """Pump the framework loop and flush renders until ``predicate`` holds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        drain(timeout=0.05)
        rec.flush_dirty()
        if predicate():
            return True
    return False


def _texts(backend: FakeBackend) -> list:
    """Every live Text view's text prop, in creation order."""
    return [v.props.get("text") for v in backend.views.values() if v.type_name == "Text"]


# ======================================================================
# Resource / start_resource
# ======================================================================


def test_start_resource_sync_fetcher_is_ready_immediately() -> None:
    resource = start_resource(lambda: 42)
    assert resource.ready
    assert resource.read() == 42


def test_resource_read_suspends_while_pending() -> None:
    future = create_future()

    async def fetch() -> str:
        return await future

    resource = start_resource(fetch)
    assert not resource.ready
    with pytest.raises(Suspend):
        resource.read()

    resolve_future(future, "data")
    drain(until=lambda: resource.ready)
    assert resource.read() == "data"


def test_resource_read_reraises_fetcher_error() -> None:
    async def fetch() -> None:
        raise RuntimeError("fetch failed")

    resource = start_resource(fetch)
    drain()
    assert resource.ready
    with pytest.raises(RuntimeError, match="fetch failed"):
        resource.read()


def test_resource_is_awaitable() -> None:
    from pythonnative.runtime import run_blocking

    async def fetch() -> int:
        await asyncio.sleep(0)
        return 9

    resource = start_resource(fetch)

    async def consume() -> int:
        return await resource

    assert run_blocking(consume(), timeout=2.0) == 9


# ======================================================================
# Async components
# ======================================================================


def test_async_component_runs_as_a_task() -> None:
    @component
    async def Hello() -> Element:
        return Text("hi from async")

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Hello(), fallback=Text("loading")))
    drain()
    assert "hi from async" in _texts(backend)


def test_async_component_suspends_without_boundary_raises() -> None:
    future = create_future()

    @component
    async def Blocked() -> Element:
        return Text(await future)

    rec = Reconciler(FakeBackend())
    with pytest.raises(RuntimeError, match="Suspense"):
        rec.mount(Blocked())


def test_async_component_with_suspense_shows_fallback_then_content() -> None:
    future = create_future()

    @component
    async def Greeting() -> Element:
        text = await future
        return Text(text)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Greeting(), fallback=Text("loading...")))

    assert _texts(backend) == ["loading..."]

    resolve_future(future, "hello async")
    assert _settle(rec, lambda: _texts(backend) == ["hello async"])


def test_sync_component_reading_resource_under_suspense() -> None:
    future = create_future()

    @component
    def Profile() -> Element:
        name = use_resource(lambda: _wait(future), []).read()
        return Text(f"name: {name}")

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Profile(), fallback=Text("spinner")))

    assert _texts(backend) == ["spinner"]

    resolve_future(future, "Ada")
    assert _settle(rec, lambda: _texts(backend) == ["name: Ada"])


async def _wait(future: Any) -> Any:
    return await future


def test_suspense_retry_reuses_cached_resource() -> None:
    """The suspended component's hook state survives the fallback
    round-trip, so its resource is fetched exactly once."""
    fetches: list = []
    future = create_future()

    async def fetch() -> str:
        fetches.append(1)
        return await future

    @component
    def Data() -> Element:
        value = use_resource(fetch, []).read()
        return Text(value)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Data(), fallback=Text("...")))
    drain(timeout=0.01)
    assert len(fetches) == 1

    resolve_future(future, "cached")
    assert _settle(rec, lambda: _texts(backend) == ["cached"])
    assert len(fetches) == 1


def test_suspense_sibling_state_survives_suspension() -> None:
    """Siblings that rendered before the suspender are salvaged: their
    resources aren't refetched on the boundary's retry."""
    sibling_fetches: list = []
    future = create_future()

    @component
    def FastSibling() -> Element:
        value = use_resource(lambda: _fetch_fast(sibling_fetches), []).read()
        return Text(value)

    @component
    def SlowChild() -> Element:
        value = use_resource(lambda: _wait(future), []).read()
        return Text(value)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(
        Suspense(
            View(FastSibling(), SlowChild()),
            fallback=Text("waiting"),
        )
    )
    assert _texts(backend) == ["waiting"]
    drain(timeout=0.01)
    assert len(sibling_fetches) == 1

    resolve_future(future, "slow done")
    assert _settle(rec, lambda: sorted(_texts(backend)) == ["fast done", "slow done"])
    assert len(sibling_fetches) == 1


async def _fetch_fast(log: list) -> str:
    log.append(1)
    return "fast done"


def test_update_suspension_keeps_previous_content() -> None:
    """A mounted component that suspends on a state-driven update keeps
    its old content on screen (no fallback flash) and re-renders when
    the new data arrives."""
    futures = {0: create_future(), 1: create_future()}
    resolve_future(futures[0], "page zero")
    drain()
    setters: list = []

    @component
    def Page() -> Element:
        page, set_page = use_state(0)
        setters.append(set_page)
        value = use_resource(lambda: _wait(futures[page]), [page]).read()
        return Text(value)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Page(), fallback=Text("first load")))
    drain()
    rec.flush_dirty()
    assert _texts(backend) == ["page zero"]

    # Flip to page 1, whose data is pending: old content must stay.
    setters[-1](1)
    rec.flush_dirty()
    drain(timeout=0.1)
    rec.flush_dirty()
    assert _texts(backend) == ["page zero"]

    resolve_future(futures[1], "page one")
    assert _settle(rec, lambda: _texts(backend) == ["page one"])


def test_nested_suspense_inner_boundary_catches() -> None:
    future = create_future()

    @component
    async def Inner() -> Element:
        return Text(await future)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(
        Suspense(
            Text("outer content"),
            Suspense(Inner(), fallback=Text("inner loading")),
            fallback=Text("outer loading"),
        )
    )
    assert sorted(_texts(backend)) == ["inner loading", "outer content"]

    resolve_future(future, "inner ready")
    assert _settle(rec, lambda: sorted(_texts(backend)) == ["inner ready", "outer content"])


def test_async_component_error_reaches_error_boundary() -> None:
    @component
    async def Explodes() -> Element:
        await asyncio.sleep(0)
        raise ValueError("async crash")

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(
        ErrorBoundary(
            Suspense(Explodes(), fallback=Text("loading")),
            fallback=lambda err: Text(f"caught: {err}"),
        )
    )
    assert _texts(backend) == ["loading"]
    assert _settle(rec, lambda: _texts(backend) == ["caught: async crash"])


def test_resource_error_reaches_error_boundary() -> None:
    @component
    def Reads() -> Element:
        return Text(use_resource(_failing_fetch, []).read())

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(
        ErrorBoundary(
            Suspense(Reads(), fallback=Text("loading")),
            fallback=lambda err: Text("recovered"),
        )
    )
    assert _settle(rec, lambda: _texts(backend) == ["recovered"])


async def _failing_fetch() -> None:
    raise RuntimeError("nope")


def test_suspense_without_fallback_is_transparent() -> None:
    """A boundary with no fallback lets the suspension propagate to the
    next boundary up."""
    future = create_future()

    @component
    async def Pending() -> Element:
        return Text(await future)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(
        Suspense(
            Suspense(Pending()),
            fallback=Text("outer catches"),
        )
    )
    assert _texts(backend) == ["outer catches"]

    resolve_future(future, "done")
    assert _settle(rec, lambda: _texts(backend) == ["done"])


def test_suspense_fallback_can_be_a_callable() -> None:
    future = create_future()

    @component
    async def Pending() -> Element:
        return Text(await future)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Pending(), fallback=lambda: Text("lazy fallback")))
    assert _texts(backend) == ["lazy fallback"]


def test_unmount_while_suspended_cancels_cleanly() -> None:
    future = create_future()

    @component
    async def Pending() -> Element:
        return Text(await future)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Pending(), fallback=Text("loading")))
    rec.unmount()
    assert backend.live_view_count() == 0

    # Late resolution must not blow up or resurrect the tree.
    resolve_future(future, "too late")
    drain()
    rec.flush_dirty()
    assert backend.live_view_count() == 0


# ======================================================================
# lazy
# ======================================================================


def test_lazy_sync_loader_renders_without_suspending() -> None:
    @component
    def Real(label: str = "") -> Element:
        return Text(f"real: {label}")

    Lazy = lazy(lambda: Real)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Lazy(label="x"), fallback=Text("loading")))
    assert _texts(backend) == ["real: x"]


def test_lazy_async_loader_suspends_then_renders() -> None:
    future = create_future()

    @component
    def Real() -> Element:
        return Text("loaded component")

    async def load() -> Any:
        await future
        return Real

    Lazy = lazy(load)

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Lazy(), fallback=Text("code loading")))
    assert _texts(backend) == ["code loading"]

    resolve_future(future, None)
    assert _settle(rec, lambda: _texts(backend) == ["loaded component"])


# ======================================================================
# use_resource dependency semantics
# ======================================================================


def test_use_resource_refetches_on_deps_change() -> None:
    fetched_for: list = []

    @component
    def Item(item_id: int = 0) -> Element:
        resource = use_resource(lambda: _fetch_item(item_id, fetched_for), [item_id])
        return Text(str(resource.read()))

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(Suspense(Item(item_id=1), fallback=Text("...")))
    drain()
    rec.flush_dirty()
    assert fetched_for == [1]

    rec.reconcile(Suspense(Item(item_id=2), fallback=Text("...")))
    drain()
    rec.flush_dirty()
    assert fetched_for == [1, 2]

    rec.reconcile(Suspense(Item(item_id=2), fallback=Text("...")))
    drain()
    assert fetched_for == [1, 2]


async def _fetch_item(item_id: int, log: list) -> int:
    log.append(item_id)
    return item_id * 10


# Keep a reference so linters don't flag the FakeView import (used in
# type comments / debugging helpers).
_ = FakeView
