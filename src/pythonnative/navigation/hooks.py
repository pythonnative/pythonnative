"""Hooks for reading navigation state from inside a screen."""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from ..hooks import use_context, use_effect
from .handle import FocusContext, Navigation, NavigationContext
from .state import Route

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


def use_route() -> Route:
    """Return the current screen's [`Route`][pythonnative.navigation.Route].

    Outside any navigator a placeholder route named ``"__root__"`` with
    empty params is returned, so components can be rendered standalone
    (previews, tests) without special-casing.

    Example:
        ```python
        @pn.component
        def DetailScreen():
            route = pn.use_route()
            return pn.Text(f"Item {route.params['id']}")
        ```
    """
    nav = use_context(NavigationContext)
    if nav is None:
        return Route("__root__", {}, key="__root__")
    return nav.route


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
