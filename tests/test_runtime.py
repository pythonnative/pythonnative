"""Unit tests for the pn.runtime asyncio runtime."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from pythonnative.runtime import (
    call_threadsafe,
    create_future,
    get_loop,
    reject_future,
    resolve_future,
    run_async,
)


def test_loop_is_singleton_and_running() -> None:
    loop_a = get_loop()
    loop_b = get_loop()
    assert loop_a is loop_b
    assert loop_a.is_running()


def test_loop_runs_on_dedicated_thread() -> None:
    loop = get_loop()
    main_thread = threading.current_thread()

    async def grab_thread() -> str:
        return threading.current_thread().name

    name = asyncio.run_coroutine_threadsafe(grab_thread(), loop).result(timeout=2.0)
    assert name == "pn-asyncio"
    assert threading.current_thread() is main_thread  # we never crossed onto the loop thread


def test_run_async_returns_thread_future_with_result() -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 7

    future = run_async(work())
    assert future.result(timeout=2.0) == 7


def test_run_async_propagates_exceptions() -> None:
    async def explode() -> None:
        raise ValueError("nope")

    future = run_async(explode())
    with pytest.raises(ValueError, match="nope"):
        future.result(timeout=2.0)


def test_call_threadsafe_dispatches_callback() -> None:
    received: list = []
    done = threading.Event()

    def callback(x: int) -> None:
        received.append(x)
        done.set()

    call_threadsafe(callback, 42)
    assert done.wait(2.0)
    assert received == [42]


def test_resolve_future_from_any_thread() -> None:
    future = create_future()

    def deliver() -> None:
        time.sleep(0.05)
        resolve_future(future, "hi")

    threading.Thread(target=deliver, daemon=True).start()

    async def wait() -> str:
        return await future

    assert run_async(wait()).result(timeout=2.0) == "hi"


def test_reject_future_from_any_thread() -> None:
    future = create_future()

    def deliver() -> None:
        time.sleep(0.05)
        reject_future(future, RuntimeError("bad"))

    threading.Thread(target=deliver, daemon=True).start()

    async def wait() -> str:
        await future
        return "unreached"

    with pytest.raises(RuntimeError, match="bad"):
        run_async(wait()).result(timeout=2.0)


def test_resolve_after_done_is_noop() -> None:
    future = create_future()
    resolve_future(future, 1)
    # Second resolve must not raise InvalidStateError.
    resolve_future(future, 2)

    async def wait() -> int:
        return await future

    # Race-free wait for the first resolution to land via call_soon_threadsafe.
    assert run_async(wait()).result(timeout=2.0) == 1
