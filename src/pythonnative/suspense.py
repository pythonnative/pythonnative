"""Suspense resources backed by standard asyncio tasks."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Generic, Optional, Tuple, TypeVar

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

    def __init__(self, driver: asyncio.Future[T]) -> None:
        self._driver = driver

    @property
    def ready(self) -> bool:
        """Whether the fetch has finished (successfully or not)."""
        return self._driver.done()

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
        if driver.done():
            return driver.result()
        raise Suspend(driver, label="Resource.read")

    def __await__(self) -> Any:
        # One consumer's cancellation must not cancel a shared resource.
        return asyncio.shield(self._driver).__await__()

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
    from .runtime import get_loop, run_async

    try:
        value = fetcher()
    except Exception as exc:
        future = get_loop().create_future()
        future.set_exception(exc)
        return Resource(future)
    if inspect.isawaitable(value):
        return Resource(run_async(value))
    future = get_loop().create_future()
    future.set_result(value)
    return Resource(future)


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
    "Resource",
    "Suspend",
    "lazy",
    "start_resource",
]
