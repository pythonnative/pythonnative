"""Hooks for reading navigation state from inside a screen."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence, overload

from ..hooks import use_context, use_effect
from .handle import FocusContext, Navigation, NavigationContext
from .state import Route, RouteParams

__all__ = ["use_focus_effect", "use_is_focused", "use_navigation", "use_route"]


def use_navigation() -> Navigation:
    """Return the [`Navigation`][pythonnative.Navigation] handle for the current screen.

    Raises:
        RuntimeError: When no navigator encloses the calling component.

    Example:
        ```python
        @pn.component
        def HomeScreen():
            nav = pn.use_navigation()
            return pn.Button("Open", on_press=lambda: nav.navigate("Detail", id=42))
        ```
    """
    nav = use_context(NavigationContext)
    if nav is None:
        raise RuntimeError(
            "use_navigation() was called outside a navigator. Render the component inside "
            "Stack.Navigator / Tab.Navigator / Drawer.Navigator (see pn.NavigationContainer)."
        )
    return nav


@overload
def use_route() -> Route[Dict[str, Any]]: ...


@overload
def use_route[P: RouteParams](params_type: type[P], /) -> Route[P]: ...


def use_route(params_type: Optional[type] = None, /) -> Route[Any]:
    """Return the current screen's [`Route`][pythonnative.navigation.Route].

    Pass a ``TypedDict`` class as ``params_type`` to get a
    ``Route[MyParams]`` whose ``params`` attribute is typed for editors
    and type checkers. At runtime the hook also verifies that every
    *required* key of the ``TypedDict`` is present on the active route,
    so a screen opened with the wrong params fails at its first render
    with a message naming the missing keys, instead of a ``KeyError``
    deep inside the render.

    Outside any navigator a placeholder route named ``"__root__"`` with
    empty params is returned (and no validation is performed), so
    components can be rendered standalone (previews, tests) without
    special-casing.

    Args:
        params_type: Optional ``TypedDict`` describing this screen's
            params.

    Raises:
        TypeError: If the active route is missing a required param
            declared by ``params_type``.

    Example:
        ```python
        class DetailParams(TypedDict):
            id: int
            title: NotRequired[str]

        @pn.component
        def DetailScreen():
            route = pn.use_route(DetailParams)
            return pn.Text(f"Item {route.params['id']}")
        ```
    """
    nav = use_context(NavigationContext)
    if nav is None:
        return Route("__root__", {}, key="__root__")
    route = nav.route
    if params_type is not None:
        required = getattr(params_type, "__required_keys__", None)
        if required:
            missing = sorted(k for k in required if k not in route.params)
            if missing:
                raise TypeError(
                    f"Screen {route.name!r} is missing required params {missing} "
                    f"declared by {params_type.__name__}; got {sorted(route.params)}"
                )
    return route


def use_is_focused() -> bool:
    """Whether the calling component is on the focused screen.

    Combines the native host's lifecycle (a screen covered by a pushed
    native screen is not focused) with the in-tree state of declarative
    navigators (inactive tabs are not focused).
    """
    return bool(use_context(FocusContext))


def use_focus_effect(effect: Callable[[], Any], deps: Optional[Sequence[Any]] = None) -> None:
    """Run ``effect`` while the screen is focused; its cleanup runs on blur.

    Like [`use_effect`][pythonnative.use_effect], but the callback runs
    only when [`use_is_focused`][pythonnative.use_is_focused] is
    ``True`` and re-runs each time the screen regains focus.

    Args:
        effect: Zero-arg callable, optionally returning a cleanup.
        deps: Extra dependencies (``None`` re-runs on every focused render).

    Example:
        ```python
        @pn.component
        def Feed():
            pn.use_focus_effect(lambda: refresh(), [])
            ...
        ```
    """
    focused = use_is_focused()

    def wrapped() -> Any:
        if focused:
            return effect()
        return None

    use_effect(wrapped, None if deps is None else [focused, *deps])
