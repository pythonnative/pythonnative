"""Structural factories: ``Fragment``, ``ErrorBoundary``, and ``Suspense``.

These produce elements whose ``type`` is one of the reconciler-owned
singletons from [`pythonnative.element`][pythonnative.element]
(``FRAGMENT``, ``ERROR_BOUNDARY``, ``SUSPENSE``) rather than a native
view name, so they never create a platform view of their own.
"""

from typing import Any, Callable, Dict, Optional

from ..element import ERROR_BOUNDARY, FRAGMENT, SUSPENSE, Element


def Fragment(*children: Optional[Element], key: Optional[str] = None) -> Element:
    """Group children without adding a wrapping native view.

    Like React's ``<></>``: groups elements without introducing an
    extra container. Each child mounts as a direct sibling of the
    Fragment's position in the parent's child list. Components may
    also simply return a plain ``list`` of elements; ``Fragment``
    exists for when the group needs a ``key`` (e.g. rendering a list
    of pairs) or when a single expression reads better.

    ```python
    pn.Column(
        pn.Text("Top"),
        pn.Fragment(
            pn.Text("Middle A"),
            pn.Text("Middle B"),
        ),
        pn.Text("Bottom"),
    )
    ```

    Args:
        *children: Child elements to expose at the parent level.
            ``None`` and ``False`` children are dropped, which makes
            conditional rendering with ``cond and pn.Text(...)``
            ergonomic.
        key: Stable identity for keyed reconciliation. A keyed
            Fragment moves all of its children as one unit and
            preserves their state across reorders.

    Returns:
        An [`Element`][pythonnative.Element] whose type is
        [`FRAGMENT`][pythonnative.element.FRAGMENT].
    """
    kept = [c for c in children if c is not None and c is not False]
    return Element(FRAGMENT, {}, kept, key=key)


def ErrorBoundary(
    *children: Element,
    fallback: Optional[Any] = None,
    on_error: Optional[Callable[[BaseException], Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Catch render errors in the wrapped subtree and display ``fallback`` instead.

    When any descendant raises during render (initial mount, a parent
    re-render, or a local state-driven update), the failed subtree is
    torn down and ``fallback`` is mounted in its place. Without a
    boundary the error propagates to the screen host (which shows the
    dev error overlay in dev mode).

    ``fallback`` may be:

    - An [`Element`][pythonnative.Element], shown as-is.
    - ``fallback(error) -> Element``.
    - ``fallback(error, reset) -> Element``, where ``reset`` is a
      zero-arg callable that clears the error and remounts the
      original children (fresh state), for retry buttons.

    Args:
        *children: Subtree to wrap.
        fallback: Fallback content (see above). Required for the
            boundary to actually catch; without it errors propagate
            to the next boundary up.
        on_error: Callback invoked with the exception when the
            boundary catches, before the fallback mounts. Use it for
            error reporting.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] whose type is
        [`ERROR_BOUNDARY`][pythonnative.element.ERROR_BOUNDARY], with
        ``fallback`` and ``on_error`` in its props (omitted when
        ``None``).

    Example:
        ```python
        import pythonnative as pn

        pn.ErrorBoundary(
            MyRiskyComponent(),
            fallback=lambda err, reset: pn.Column(
                pn.Text(f"Error: {err}"),
                pn.Button("Retry", on_press=reset),
            ),
            on_error=lambda err: log.exception(err),
        )
        ```
    """
    props: Dict[str, Any] = {}
    if fallback is not None:
        props["fallback"] = fallback
    if on_error is not None:
        props["on_error"] = on_error
    return Element(ERROR_BOUNDARY, props, list(children), key=key)


def Suspense(
    *children: Element,
    fallback: Optional[Any] = None,
    key: Optional[str] = None,
) -> Element:
    """Show ``fallback`` while descendants wait on async work, then swap in the content.

    A Suspense boundary catches **suspensions** from the subtree it
    wraps: an ``async def`` component body blocking on a pending
    await, or a regular component calling
    [`Resource.read`][pythonnative.suspense.Resource.read] on data that hasn't
    arrived (see [`use_resource`][pythonnative.use_resource] and
    [`lazy`][pythonnative.lazy]). While anything is pending the
    boundary renders ``fallback``; when the awaited work completes it
    retries the content and swaps it in. Suspended components keep
    their hook state across retries, so cached resources aren't
    refetched.

    Two timing behaviors, matching React:

    - **Initial mount**: the fallback shows until the content is ready.
    - **Updates**: a component that's already on screen and suspends
      again (its dependencies changed) keeps its previous content
      visible and re-renders when ready; there's no fallback flash.

    Args:
        *children: Subtree to wrap (the async content).
        fallback: Content shown while suspended: an
            [`Element`][pythonnative.Element] or a zero-arg callable
            returning one. Without it, suspensions propagate to the
            next Suspense boundary up.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] whose type is
        [`SUSPENSE`][pythonnative.element.SUSPENSE], with ``fallback``
        in its props.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        async def Profile(user_id: str):
            user = await api.fetch_user(user_id)
            return pn.Text(user.name)

        @pn.component
        def Screen():
            return pn.Suspense(
                Profile(user_id="42"),
                fallback=pn.ActivityIndicator(),
            )
        ```
    """
    return Element(SUSPENSE, {"fallback": fallback}, list(children), key=key)
