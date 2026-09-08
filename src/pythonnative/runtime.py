"""Application execution on a standard asyncio event loop.

Mobile hosts start one application thread with :func:`start`. All Python
rendering, callbacks, and tasks run there. Native hosts own their UI threads
and marshal view operations themselves. Headless programs can instead drive
an ordinary local loop with :func:`run_blocking` and :func:`drain`.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import threading
from typing import Any, Awaitable, Callable, Coroutine, TypeVar

T = TypeVar("T")
Awaitlike = Coroutine[Any, Any, T] | Awaitable[T]
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_owner: threading.Thread | None = None
_lock = threading.RLock()
_scope: contextvars.ContextVar[TaskScope | None] = contextvars.ContextVar("pn_task_scope", default=None)


class TaskScope:
    """Own tasks until an application or component is disposed.

    Closing a scope cancels its tasks and rejects new work. A task removes
    itself when it finishes, including when it fails or is cancelled.
    """

    def __init__(self, name: str = "application") -> None:
        self.name = name
        self.closed = False
        self._tasks: set[Any] = set()

    @property
    def pending(self) -> int:
        """Number of unfinished tasks owned by this scope."""
        return sum(not task.done() for task in self._tasks)

    def create_task(self, awaitable: Awaitlike[T], *, report_errors: bool = False) -> Any:
        """Schedule work with this scope's lifetime and context."""
        if self.closed:
            if inspect.iscoroutine(awaitable):
                awaitable.close()
            raise RuntimeError(f"Task scope {self.name!r} is closed")
        token = _scope.set(self)
        try:
            task = _schedule(awaitable)
        finally:
            _scope.reset(token)
        self._tasks.add(task)

        def finished(done: Any) -> None:
            self._tasks.discard(done)
            if report_errors and not done.cancelled():
                error = done.exception()
                if error is not None:
                    from .diagnostics import report_error

                    if not report_error(error, phase=f"task in {self.name}"):
                        get_loop().call_exception_handler(
                            {"message": f"Task in {self.name} failed", "exception": error}
                        )

        task.add_done_callback(finished)
        return task

    def close(self) -> None:
        """Cancel owned work; calling this more than once is harmless."""
        self.closed = True
        for task in tuple(self._tasks):
            if (
                isinstance(task, asyncio.Future)
                and task.get_loop().is_running()
                and not _on_loop_thread(task.get_loop())
            ):
                task.get_loop().call_soon_threadsafe(task.cancel)
            else:
                task.cancel()
        self._tasks.clear()


_application_scope = TaskScope()


def start() -> asyncio.AbstractEventLoop:
    """Start the application thread once and return its event loop."""
    global _loop, _thread, _owner
    with _lock:
        if _thread is not None and _thread.is_alive():
            assert _loop is not None
            return _loop
        if _loop is not None and not _loop.is_closed():
            raise RuntimeError("Start the application runtime before creating headless tasks")
        ready = threading.Event()
        loop = asyncio.new_event_loop()
        _loop = loop

        def serve() -> None:
            asyncio.set_event_loop(loop)
            ready.set()
            try:
                loop.run_forever()
            finally:
                loop.run_until_complete(_cancel_tasks(loop))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()

        _thread = threading.Thread(target=serve, name="PythonNative", daemon=True)
        _owner = _thread
        _thread.start()
        ready.wait()
        return loop


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the application loop, or the caller's loop in headless mode."""
    global _loop, _owner
    if _thread is not None and _thread.is_alive():
        assert _loop is not None
        return _loop
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        with _lock:
            if _loop is None or _loop.is_closed():
                _loop = asyncio.new_event_loop()
                _owner = threading.current_thread()
            return _loop


def _on_loop_thread(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return loop is _loop and threading.current_thread() is _owner


async def _ensure_coro(awaitable: Awaitlike[T]) -> T:
    return await awaitable


def _schedule(awaitable: Awaitlike[T]) -> Any:
    loop = get_loop()
    if _on_loop_thread(loop):
        return asyncio.ensure_future(awaitable, loop=loop)
    return asyncio.run_coroutine_threadsafe(_ensure_coro(awaitable), loop)


def run_async(awaitable: Awaitlike[T]) -> Any:
    """Schedule work in the current component scope or the application scope.

    Returns an asyncio task on the application thread and a concurrent
    future on other threads. Both handles support cancellation.
    """
    return (_scope.get() or _application_scope).create_task(awaitable)


def run_application_task(awaitable: Awaitlike[T]) -> Any:
    """Start work that should survive the component that requested it."""
    return _application_scope.create_task(awaitable)


def invoke(callback: Callable[..., Any], *args: Any, scope: TaskScope | None = None) -> Any:
    """Invoke a callback and schedule an awaitable result in its owner's scope."""
    owner = scope or _scope.get() or _application_scope
    if owner.closed:
        return None
    token = _scope.set(owner)
    try:
        result = callback(*args)
        if inspect.isawaitable(result):
            return owner.create_task(result, report_errors=True)
        return result
    finally:
        _scope.reset(token)


def run_blocking(awaitable: Awaitlike[T], timeout: float | None = None) -> T:
    """Wait for work from synchronous code; never block the application loop."""
    loop = get_loop()
    if loop.is_running() and _on_loop_thread(loop):
        if inspect.iscoroutine(awaitable):
            awaitable.close()
        raise RuntimeError("run_blocking() cannot run inside the event loop; await the result")

    async def bounded() -> T:
        async with asyncio.timeout(timeout):
            return await awaitable

    if loop.is_running():
        return asyncio.run_coroutine_threadsafe(bounded(), loop).result()
    return loop.run_until_complete(bounded())


def drain(timeout: float = 1.0, *, until: Callable[[], bool] | None = None) -> bool:
    """Settle headless work or wait for application tasks from a test thread.

    Long-lived application tasks require an explicit ``until`` predicate.
    This uses public asyncio APIs and never inspects selector internals.
    """

    async def settle() -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        idle_turns = 0
        while loop.time() < deadline:
            await asyncio.sleep(0)
            if until is not None and until():
                return True
            pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task() and not task.done()]
            if until is None and not pending:
                idle_turns += 1
                if idle_turns >= 3:
                    return True
            else:
                idle_turns = 0
            await asyncio.sleep(0.001)
        return False

    return run_blocking(settle())


def call_threadsafe(callback: Callable[..., Any], *args: Any) -> None:
    """Enqueue a callback on the application event loop from any thread."""
    get_loop().call_soon_threadsafe(callback, *args)


def call_on_application_thread(fn: Callable[[], None]) -> None:
    """Execute Python work on its owner thread, inline when already there."""
    loop = get_loop()
    if _on_loop_thread(loop):
        fn()
    else:
        loop.call_soon_threadsafe(fn)


def resolve_future(future: asyncio.Future[T], value: T) -> None:
    """Complete a future from any thread unless it was cancelled."""

    def complete() -> None:
        if not future.done():
            future.set_result(value)

    future.get_loop().call_soon_threadsafe(complete)


def reject_future(future: asyncio.Future[Any], error: BaseException) -> None:
    """Fail a future from any thread unless it was cancelled."""

    def complete() -> None:
        if not future.done():
            future.set_exception(error)

    future.get_loop().call_soon_threadsafe(complete)


def create_future() -> asyncio.Future[Any]:
    """Create a future for completion by a native request."""
    return get_loop().create_future()


async def _cancel_tasks(loop: asyncio.AbstractEventLoop) -> None:
    tasks = [task for task in asyncio.all_tasks(loop) if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _shutdown_for_tests() -> None:
    global _loop, _thread, _owner, _application_scope
    with _lock:
        loop, thread = _loop, _thread
        _application_scope.close()
        if loop is not None and not loop.is_closed():
            if thread is not None:
                loop.call_soon_threadsafe(loop.stop)
                thread.join(timeout=5)
                if thread.is_alive():
                    raise RuntimeError("Application thread did not stop")
            elif not loop.is_running():
                loop.run_until_complete(_cancel_tasks(loop))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
        _loop = _thread = _owner = None
        _application_scope = TaskScope()


__all__ = [
    "TaskScope",
    "call_on_application_thread",
    "call_threadsafe",
    "create_future",
    "drain",
    "get_loop",
    "reject_future",
    "resolve_future",
    "run_application_task",
    "run_async",
    "run_blocking",
    "start",
]
