"""Suspense primitives: suspension signals, resources, and lazy loading.

This module implements the machinery behind PythonNative's async
rendering model:

- ``async def`` components: a component body may be a coroutine. The
  reconciler drives it synchronously as far as possible (awaits on
  already-resolved futures complete inline); if it blocks on pending
  work, the render **suspends** and the nearest
  [`Suspense`][pythonnative.Suspense] boundary shows its fallback
  until the coroutine finishes.
- [`use_resource`][pythonnative.use_resource]: a hook that starts an
  async fetch and caches it across renders. Reading an unresolved
  [`Resource`][pythonnative.Resource] suspends the render; awaiting it
  inside an ``async def`` component does the same thing without the
  boundary having to re-run anything by hand.
- [`lazy`][pythonnative.lazy]: code-splitting for components. The
  loader runs once, and renders suspend until it resolves.

The core building block is [`CoroDriver`][pythonnative.suspense.CoroDriver],
a miniature task that steps a coroutine **synchronously** until it
either finishes or blocks on a pending :class:`asyncio.Future`. This is
what lets an ``async def`` component whose awaits are all cached
(resolved resources, completed tasks) render in a single synchronous
pass with zero event-loop round trips, while genuinely pending awaits
suspend cleanly.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from typing import Any, Callable, Generic, List, Optional, Tuple, TypeVar

T = TypeVar("T")

_UNSET = object()


class Suspend(BaseException):
    """Signal that a render is blocked on pending async work.

    Raised while a component renders, either by
    [`Resource.read`][pythonnative.suspense.Resource.read] or by an
    ``async def`` component body blocking on a pending await. The
    reconciler catches it: the nearest
    [`Suspense`][pythonnative.Suspense] boundary shows its fallback
    (initial mounts), or the component keeps its previous content and
    re-renders when the work finishes (updates).

    Derives from :class:`BaseException` so
    [`ErrorBoundary`][pythonnative.ErrorBoundary] (which catches
    :class:`Exception`) never mistakes a suspension for a crash.

    Attributes:
        waitable: The pending work; exposes ``done()`` and
            ``add_done_callback(cb)``.
        hook_state: The suspended component's hook state, carried so
            a Suspense boundary can preserve it across retries (its
            cached resources survive, so the retry doesn't refetch).
        key: ``(component identity, element key)`` used to re-match
            ``hook_state`` on retry.
        label: Component name for diagnostics.
    """

    def __init__(self, waitable: Any, hook_state: Any = None, label: str = "") -> None:
        super().__init__(label or "render suspended")
        self.waitable = waitable
        self.hook_state = hook_state
        self.key: Optional[Tuple[int, Any]] = None
        self.label = label


class CoroDriver:
    """Drive a coroutine synchronously until it blocks on pending work.

    A miniature :class:`asyncio.Task`: it steps the coroutine with
    ``send()``, resolving awaits on already-done futures inline. When
    the coroutine blocks on a *pending* future, the driver parks and
    resumes from that future's done callback (on the framework loop's
    thread). Each step runs inside the :mod:`contextvars` context
    captured at creation, so hooks called after an ``await`` still see
    the owning component's hook state.

    Attributes:
        done: Whether the coroutine finished (returned, raised, or was
            cancelled).
    """

    __slots__ = (
        "_coro",
        "_context",
        "done",
        "_cancelled",
        "_result",
        "_error",
        "_callbacks",
        "_waiting_on",
        "_stepping",
    )

    def __init__(self, coro: Any, context: Optional[contextvars.Context] = None) -> None:
        self._coro = coro
        self._context = context if context is not None else contextvars.copy_context()
        self.done = False
        self._cancelled = False
        self._result: Any = _UNSET
        self._error: Optional[BaseException] = None
        self._callbacks: List[Callable[["CoroDriver"], None]] = []
        self._waiting_on: Optional[Any] = None
        self._stepping = False

    # -- inspection ------------------------------------------------------

    def cancelled(self) -> bool:
        """Whether the driver was cancelled before finishing normally."""
        return self._cancelled

    def result(self) -> Any:
        """Return the coroutine's return value (raises if not done or failed)."""
        if not self.done:
            raise RuntimeError("CoroDriver is not done")
        if self._error is not None:
            raise self._error
        return self._result

    def exception(self) -> Optional[BaseException]:
        """Return the coroutine's exception, or ``None``."""
        if not self.done:
            raise RuntimeError("CoroDriver is not done")
        return self._error

    def add_done_callback(self, callback: Callable[["CoroDriver"], None]) -> None:
        """Invoke ``callback(self)`` when the coroutine finishes.

        Fires immediately when already done. Callbacks run on whatever
        thread finished the coroutine (the framework loop's thread for
        suspended coroutines).
        """
        if self.done:
            callback(self)
            return
        self._callbacks.append(callback)

    # -- driving ---------------------------------------------------------

    def start(self) -> None:
        """Run the coroutine as far as it can go without blocking."""
        self._step(("send", None))

    def cancel(self) -> bool:
        """Throw :class:`asyncio.CancelledError` into the coroutine.

        Returns:
            ``False`` when the coroutine had already finished,
            ``True`` otherwise.
        """
        if self.done:
            return False
        waiting = self._waiting_on
        self._waiting_on = None
        if waiting is not None:
            try:
                waiting.remove_done_callback(self._resume)
            except Exception:
                pass
        self._cancelled = True
        self._step(("throw", asyncio.CancelledError()))
        return True

    def _resume(self, _fut: Any) -> None:
        self._waiting_on = None
        self._step(("send", None))

    def _step(self, action: Tuple[str, Any]) -> None:
        if self.done or self._stepping:
            return
        self._stepping = True
        # When a step runs outside a loop iteration (a synchronous
        # render), mark the framework loop as the running loop for the
        # duration, exactly as asyncio.Task steps do. Without this,
        # anything the coroutine calls that uses
        # ``asyncio.get_running_loop()`` internally (``asyncio.sleep``,
        # ``asyncio.create_task``, ...) raises "no running event loop".
        from . import runtime

        events = asyncio.events
        installed_loop = None
        if events._get_running_loop() is None:
            installed_loop = runtime.get_loop()
            events._set_running_loop(installed_loop)
        try:
            self._context.run(self._advance, action)
        finally:
            if installed_loop is not None:
                events._set_running_loop(None)
            self._stepping = False

    def _advance(self, action: Tuple[str, Any]) -> None:
        kind, value = action
        while True:
            try:
                if kind == "throw":
                    yielded = self._coro.throw(value)
                else:
                    yielded = self._coro.send(value)
            except StopIteration as stop:
                self._finish(stop.value, None)
                return
            except asyncio.CancelledError as exc:
                self._cancelled = True
                self._finish(None, exc)
                return
            except BaseException as exc:
                self._finish(None, exc)
                return

            kind, value = "send", None
            if yielded is None:
                # ``await asyncio.sleep(0)`` and bare yields: resume on
                # the next loop tick to preserve cooperative yielding.
                from . import runtime

                runtime.get_loop().call_soon(self._resume, None)
                return
            if isinstance(yielded, asyncio.Future):
                # Mirror asyncio.Task's handshake with Future.__await__.
                try:
                    yielded._asyncio_future_blocking = False
                except AttributeError:
                    pass
                if yielded.done():
                    continue
                self._waiting_on = yielded
                yielded.add_done_callback(self._resume)
                return
            self._finish(
                None,
                RuntimeError(
                    f"async component awaited an unsupported object: {yielded!r}. "
                    "Await asyncio futures, tasks, or PythonNative awaitables."
                ),
            )
            return

    def _finish(self, result: Any, error: Optional[BaseException]) -> None:
        self.done = True
        self._result = result
        self._error = error
        self._waiting_on = None
        callbacks = self._callbacks
        self._callbacks = []
        for callback in callbacks:
            try:
                callback(self)
            except Exception as exc:
                print(f"[pn.suspense] done callback raised: {exc!r}")


class Resource(Generic[T]):
    """A cached async value with Suspense integration.

    Returned by [`use_resource`][pythonnative.use_resource]. A resource
    starts fetching as soon as the hook runs and remembers its result
    across renders (until its dependencies change), so re-renders never
    refetch.

    Two ways to consume it:

    - ``resource.read()`` in a regular component: returns the value
      when ready, re-raises the fetcher's error if it failed, and
      **suspends the render** while pending.
    - ``await resource`` in an ``async def`` component: same
      semantics, expressed as a plain await.
    """

    __slots__ = ("_driver",)

    def __init__(self, driver: CoroDriver) -> None:
        self._driver = driver

    @property
    def ready(self) -> bool:
        """Whether the fetch has finished (successfully or not)."""
        return self._driver.done

    def read(self) -> T:
        """Return the fetched value, or suspend the render while pending.

        Raises:
            Suspend: While the fetch is still in flight (caught by the
                reconciler, never by user code).
            BaseException: Whatever the fetcher raised, re-raised so an
                enclosing [`ErrorBoundary`][pythonnative.ErrorBoundary]
                can catch it.
        """
        driver = self._driver
        if driver.done:
            return driver.result()
        raise Suspend(driver, label="Resource.read")

    def __await__(self) -> Any:
        driver = self._driver
        if driver.done:

            def _done() -> Any:
                return driver.result()
                yield  # pragma: no cover - marks this as a generator

            return _done()
        from . import runtime

        future = runtime.create_future()

        def _transfer(d: CoroDriver) -> None:
            error = d.exception() if not d.cancelled() else asyncio.CancelledError()
            if error is not None:
                runtime.reject_future(future, error)
            else:
                runtime.resolve_future(future, d.result())

        driver.add_done_callback(_transfer)
        return future.__await__()

    def cancel(self) -> None:
        """Cancel the in-flight fetch (no-op when already done)."""
        self._driver.cancel()


def start_resource(fetcher: Callable[[], Any]) -> Resource[Any]:
    """Start ``fetcher`` immediately and wrap it in a [`Resource`][pythonnative.Resource].

    The fetcher may be an ``async def`` (typical) or a plain function;
    synchronous results resolve the resource immediately, so reading
    it never suspends.

    This is the non-hook constructor used for module-level resources
    (preloading data before a screen mounts) and by
    [`lazy`][pythonnative.lazy]. Inside components, prefer
    [`use_resource`][pythonnative.use_resource], which caches per
    component instance and re-fetches when dependencies change.
    """

    async def _run() -> Any:
        value = fetcher()
        if inspect.isawaitable(value):
            return await value
        return value

    driver = CoroDriver(_run())
    driver.start()
    return Resource(driver)


def lazy(loader: Callable[[], Any]) -> Callable[..., Any]:
    """Define a component that loads its implementation on first render.

    ``loader`` runs once, the first time the returned component
    renders; until it resolves, renders suspend (so wrap usages in a
    [`Suspense`][pythonnative.Suspense] boundary to show a loading
    state). The loaded value must be a component (a ``@component``
    function or any element factory).

    Args:
        loader: A zero-arg callable returning the component, or an
            ``async def`` resolving to it. Synchronous loaders (a
            deferred ``import``) resolve immediately and never
            suspend.

    Returns:
        A component. Props (and children) pass through to the loaded
        component unchanged.

    Example:
        ```python
        import pythonnative as pn

        Chart = pn.lazy(lambda: __import__("app.chart", fromlist=["Chart"]).Chart)

        @pn.component
        def Dashboard():
            return pn.Suspense(
                Chart(points=[1, 2, 3]),
                fallback=pn.ActivityIndicator(),
            )
        ```
    """
    from .component import Component

    state: dict = {}

    def Lazy(*children: Any, **props: Any) -> Any:
        resource = state.get("resource")
        if resource is None:
            resource = start_resource(loader)
            state["resource"] = resource
        loaded = resource.read()
        return loaded(*children, **props)

    name = getattr(loader, "__name__", "Lazy")
    if name == "<lambda>":
        name = "Lazy"
    return Component(Lazy, display_name=name)


__all__ = [
    "CoroDriver",
    "Resource",
    "Suspend",
    "lazy",
    "start_resource",
]
