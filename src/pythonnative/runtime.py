"""Asyncio runtime for PythonNative.

PythonNative runs a single, framework-wide ``asyncio`` event loop on
a dedicated daemon thread. Every awaitable surface in the framework
— the async hooks
([`use_async_effect`][pythonnative.hooks.use_async_effect],
[`use_query`][pythonnative.hooks.use_query],
[`use_mutation`][pythonnative.hooks.use_mutation]), the
[`fetch`][pythonnative.net.fetch] HTTP client,
[`AsyncStorage`][pythonnative.storage.AsyncStorage], the awaitable
native modules
([`Camera`][pythonnative.native_modules.camera.Camera] /
[`Location`][pythonnative.native_modules.location.Location] /
[`Notifications`][pythonnative.native_modules.notifications.Notifications]),
and awaited animations — schedules its work on this loop via
[`run_async`][pythonnative.runtime.run_async].

The reconciler is **not** asyncio-aware; it still runs synchronously on
the platform main thread. Coroutines that want to mutate component
state simply call the regular ``use_state`` setter, and the existing
deferred-render path inside the screen host marshals the re-render
onto the main thread. The runtime is therefore additive: it gives
coroutines somewhere to live without changing the rendering contract.

Example:
    ```python
    import asyncio

    import pythonnative as pn


    async def hello() -> str:
        await asyncio.sleep(0.1)
        return "hi"


    future = pn.runtime.run_async(hello())
    print(future.result(timeout=1.0))  # "hi"
    ```
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from concurrent.futures import Future as _ThreadFuture
from typing import Any, Awaitable, Callable, Coroutine, Optional, TypeVar, Union

T = TypeVar("T")


# ======================================================================
# Module-level loop singleton
# ======================================================================

_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def _spawn_loop() -> asyncio.AbstractEventLoop:
    """Create a fresh event loop on a daemon thread and block until it's running."""
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def _run() -> None:
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=_run, daemon=True, name="pn-asyncio")
    thread.start()
    ready.wait()

    global _thread
    _thread = thread
    return loop


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the framework-wide event loop, starting it on first use.

    The loop runs on a daemon thread (``"pn-asyncio"``) and lives for
    the duration of the process. It is safe to call this from any
    thread.

    Returns:
        The shared :class:`asyncio.AbstractEventLoop`.
    """
    global _loop
    if _loop is not None and not _loop.is_closed():
        return _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = _spawn_loop()
        return _loop


def _shutdown_for_tests() -> None:
    """Stop the runtime loop, primarily for test isolation.

    Cancels every pending task, stops the loop, joins the thread, and
    clears the module-level state so the next call to
    [`get_loop`][pythonnative.runtime.get_loop] starts a fresh loop.
    Production code should not call this — the loop is a daemon and
    will be torn down with the process.
    """
    global _loop, _thread
    with _lock:
        loop = _loop
        thread = _thread
        _loop = None
        _thread = None
    if loop is None:
        return
    try:
        for task in asyncio.all_tasks(loop):
            loop.call_soon_threadsafe(task.cancel)
        loop.call_soon_threadsafe(loop.stop)
    except RuntimeError:
        pass
    if thread is not None:
        thread.join(timeout=2.0)
    try:
        loop.close()
    except RuntimeError:
        pass


# ======================================================================
# Scheduling helpers
# ======================================================================


Awaitlike = Union[Coroutine[Any, Any, T], Awaitable[T]]


def run_async(awaitable: Awaitlike[T]) -> "_ThreadFuture[T]":
    """Schedule ``awaitable`` on the framework loop and return a thread future.

    Use this when calling async code from synchronous code (e.g. an
    event handler, a hook setup function, or a test). The returned
    :class:`concurrent.futures.Future` is created by
    :func:`asyncio.run_coroutine_threadsafe` so it can be ``result()``-ed
    from the calling thread and ``cancel()``-ed from anywhere.

    Args:
        awaitable: Either a coroutine object (the typical case) or any
            awaitable. Awaitables that are not coroutines are wrapped
            with :func:`asyncio.ensure_future` on the loop.

    Returns:
        A thread-safe future that resolves with the coroutine's return
        value, or raises its exception.

    Example:
        ```python
        import pythonnative as pn

        async def work():
            return 42

        fut = pn.runtime.run_async(work())
        assert fut.result(timeout=1.0) == 42
        ```
    """
    loop = get_loop()
    if inspect.iscoroutine(awaitable):
        return asyncio.run_coroutine_threadsafe(awaitable, loop)

    async def _wrap() -> T:
        return await awaitable

    return asyncio.run_coroutine_threadsafe(_wrap(), loop)


def call_threadsafe(callback: Callable[..., Any], *args: Any) -> None:
    """Schedule ``callback(*args)`` on the loop thread.

    Thin wrapper around
    :meth:`asyncio.AbstractEventLoop.call_soon_threadsafe`. Useful from
    native delegates (which may fire on arbitrary threads) when you
    need to hop onto the runtime thread before touching asyncio
    primitives.
    """
    get_loop().call_soon_threadsafe(callback, *args)


def resolve_future(future: "asyncio.Future[T]", value: T) -> None:
    """Set ``future``'s result from any thread (no-op if already done).

    Convenience used by every native delegate that wraps a callback
    into an awaitable: the delegate doesn't have to know which thread
    it's on, only that it must not race with cancellation.

    Args:
        future: An :class:`asyncio.Future` bound to the runtime loop.
        value: The value to deliver as the future's result.
    """
    loop = future.get_loop()
    loop.call_soon_threadsafe(_set_future_result, future, value)


def reject_future(future: "asyncio.Future[Any]", error: BaseException) -> None:
    """Set ``future``'s exception from any thread (no-op if already done)."""
    loop = future.get_loop()
    loop.call_soon_threadsafe(_set_future_exception, future, error)


def _set_future_result(future: "asyncio.Future[Any]", value: Any) -> None:
    if not future.done():
        future.set_result(value)


def _set_future_exception(future: "asyncio.Future[Any]", error: BaseException) -> None:
    if not future.done():
        future.set_exception(error)


def create_future() -> "asyncio.Future[Any]":
    """Create a future bound to the framework runtime loop.

    Safe to call from any thread. The returned future is **not**
    attached to whatever loop is current on the caller; instead it
    lives on the framework's shared loop so any thread can call
    [`resolve_future`][pythonnative.runtime.resolve_future] /
    [`reject_future`][pythonnative.runtime.reject_future] on it.
    """
    return get_loop().create_future()


__all__ = [
    "get_loop",
    "run_async",
    "call_threadsafe",
    "create_future",
    "resolve_future",
    "reject_future",
]
