"""Unit tests for the pn.runtime main-thread guest loop."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from pythonnative.runtime import (
    call_on_main_thread,
    call_threadsafe,
    create_future,
    drain,
    get_loop,
    reject_future,
    resolve_future,
    run_async,
    run_blocking,
)


def test_loop_is_singleton() -> None:
    loop_a = get_loop()
    loop_b = get_loop()
    assert loop_a is loop_b


def test_loop_lives_on_the_creating_thread() -> None:
    """The framework loop is owned by the thread that created it (the
    platform main thread on device, the test thread here); coroutines
    run on that same thread, never a background one."""
    main_thread = threading.current_thread()
    get_loop()

    async def grab_thread() -> threading.Thread:
        return threading.current_thread()

    assert run_blocking(grab_thread()) is main_thread


def test_get_loop_adopts_running_loop() -> None:
    """Inside asyncio.run / an async test, get_loop returns the
    caller's loop instead of the framework's own."""

    async def check() -> bool:
        return get_loop() is asyncio.get_running_loop()

    assert asyncio.run(check())


def test_run_blocking_returns_result() -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 7

    assert run_blocking(work()) == 7


def test_run_blocking_propagates_exceptions() -> None:
    async def explode() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        run_blocking(explode())


def test_run_blocking_timeout() -> None:
    async def forever() -> None:
        await asyncio.sleep(60)

    with pytest.raises(TimeoutError):
        run_blocking(forever(), timeout=0.05)


def test_run_async_on_loop_thread_returns_task() -> None:
    """On the loop's own thread run_async wraps the coroutine in an
    asyncio.Task, so callers can await or cancel it."""
    get_loop()

    async def work() -> int:
        return 3

    handle = run_async(work())
    assert isinstance(handle, asyncio.Task)
    drain()
    assert handle.result() == 3


def test_run_async_from_other_thread_returns_concurrent_future() -> None:
    """From a foreign thread run_async returns a
    concurrent.futures.Future; the work still executes on the loop's
    owner thread once it pumps."""
    get_loop()
    results: list = []

    async def work() -> threading.Thread:
        return threading.current_thread()

    def submit() -> None:
        results.append(run_async(work()))

    worker = threading.Thread(target=submit)
    worker.start()
    worker.join()

    future = results[0]
    assert not isinstance(future, asyncio.Task)
    drain(until=future.done)
    assert future.result(timeout=0) is threading.current_thread()


def test_run_async_task_propagates_exceptions() -> None:
    async def explode() -> None:
        raise ValueError("bad")

    task = run_async(explode())
    drain()
    with pytest.raises(ValueError, match="bad"):
        task.result()


def test_call_threadsafe_dispatches_callback() -> None:
    get_loop()
    received: list = []

    def deliver() -> None:
        call_threadsafe(received.append, 42)

    worker = threading.Thread(target=deliver)
    worker.start()
    worker.join()

    drain(until=lambda: bool(received))
    assert received == [42]


def test_resolve_future_from_any_thread() -> None:
    future = create_future()

    def deliver() -> None:
        time.sleep(0.02)
        resolve_future(future, "hi")

    threading.Thread(target=deliver, daemon=True).start()

    async def wait() -> str:
        return await future

    assert run_blocking(wait(), timeout=2.0) == "hi"


def test_reject_future_from_any_thread() -> None:
    future = create_future()

    def deliver() -> None:
        time.sleep(0.02)
        reject_future(future, RuntimeError("bad"))

    threading.Thread(target=deliver, daemon=True).start()

    async def wait() -> str:
        await future
        return "unreached"

    with pytest.raises(RuntimeError, match="bad"):
        run_blocking(wait(), timeout=2.0)


def test_resolve_after_done_is_noop() -> None:
    future = create_future()
    resolve_future(future, 1)
    # Second resolve must not raise InvalidStateError.
    resolve_future(future, 2)

    async def wait() -> int:
        return await future

    assert run_blocking(wait(), timeout=2.0) == 1


def test_drain_settles_chained_tasks() -> None:
    """drain() keeps pumping until dependent tasks settle, not just one
    loop iteration."""
    order: list = []

    async def second() -> None:
        await asyncio.sleep(0)
        order.append("second")

    async def first() -> None:
        order.append("first")
        await asyncio.sleep(0.01)
        await second()

    run_async(first())
    assert drain(timeout=2.0)
    assert order == ["first", "second"]


def test_drain_until_predicate() -> None:
    hits: list = []

    async def tick() -> None:
        while True:
            hits.append(1)
            await asyncio.sleep(0.001)

    task = run_async(tick())
    assert drain(timeout=2.0, until=lambda: len(hits) >= 3)
    task.cancel()
    drain()
    assert len(hits) >= 3


def test_run_blocking_rejects_reentrant_use() -> None:
    async def inner() -> None:
        coro = asyncio.sleep(0)
        try:
            run_blocking(coro)
        finally:
            coro.close()

    with pytest.raises(RuntimeError, match="event loop is running"):
        run_blocking(inner())


def test_call_on_main_thread_runs_inline_off_device() -> None:
    """Off-device the helper has no platform main loop to marshal onto;
    it should just invoke ``fn`` synchronously on the caller's thread."""
    received: list = []
    caller_thread = threading.current_thread()

    def fn() -> None:
        received.append(threading.current_thread())

    call_on_main_thread(fn)
    assert received == [caller_thread]


def test_coroutines_share_the_callers_thread() -> None:
    """The async-first model: coroutines and synchronous code interleave
    on one thread, so a coroutine can safely touch state the sync side
    owns without locks."""
    state = {"value": 0}

    async def bump() -> None:
        state["value"] += 1

    run_blocking(bump())
    assert state["value"] == 1
