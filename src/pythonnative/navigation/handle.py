"""The [`Navigation`][pythonnative.Navigation] handle and the navigator core behind it.

Every screen rendered by a navigator receives a ``Navigation`` object
through [`use_navigation`][pythonnative.use_navigation]. The handle is
scoped to the screen's route (so ``add_listener("focus", ...)`` fires
for *that* screen) and forwards every action to the
[`NavigatorCore`][pythonnative.navigation.handle.NavigatorCore] that
owns the navigator's state.

Actions the core can't satisfy (an unknown route, popping past the
first screen) bubble to the parent navigator, so a stack nested in a
tab still pops correctly and ``navigate("Settings")`` from deep inside
one tab can switch to another.

When the core belongs to the **root stack of a native host** it never
mutates its own state for pushes and pops: it asks the host to push or
pop a real native screen carrying the serialized next state, and the
new screen's navigator boots from that state.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Protocol, Sequence, Tuple, Union

from .. import diagnostics
from ..hooks import Context, create_context
from .screen import ScreenDef
from .state import NavigationState, Route

__all__ = [
    "DrawerNavigation",
    "FocusContext",
    "HostNavigator",
    "Navigation",
    "NavigationContext",
    "NavigationEvent",
    "NavigatorCore",
    "TabNavigation",
]

NavigatorKind = Literal["stack", "tab", "drawer"]
EventName = Literal["focus", "blur", "before_remove", "state"]
Listener = Callable[["NavigationEvent"], None]


class HostNavigator(Protocol):
    """What a root stack needs from the native screen host.

    Hosts (iOS view controller, Android fragment, browser preview) and
    [`FakeHost`][pythonnative.testing.FakeHost] implement these. Each
    method receives the *serialized* next navigation state so the
    screen it creates can boot with the full history.
    """

    is_focused: bool

    def initial_navigation_state(self) -> Optional[Dict[str, Any]]:
        """The serialized state this screen was pushed with, if any."""
        ...

    def push_screen(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Push a native screen that boots from ``state``."""
        ...

    def pop_screens(self, count: int) -> None:
        """Pop ``count`` native screens."""
        ...

    def replace_screen(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Replace the current native screen with one booting from ``state``."""
        ...

    def reset_screens(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Replace the whole native stack with one booting from ``state``."""
        ...

    def set_screen_options(self, options: Dict[str, Any]) -> None:
        """Apply header options (``title`` and friends) to the native bar."""
        ...

    def add_focus_listener(self, callback: Callable[[bool], None]) -> Callable[[], None]:
        """Subscribe to the host covering / revealing this screen; returns an unsubscribe."""
        ...


class NavigationEvent:
    """Payload delivered to ``add_listener`` callbacks.

    Attributes:
        type: ``"focus"``, ``"blur"``, ``"before_remove"``, or ``"state"``.
        route: The route the event concerns.
        data: Extra event data (``before_remove`` carries the
            ``action`` that caused it).
    """

    __slots__ = ("type", "route", "data", "default_prevented")

    def __init__(self, type_: str, route: Route, data: Optional[Mapping[str, Any]] = None) -> None:
        self.type = type_
        self.route = route
        self.data: Dict[str, Any] = dict(data or {})
        self.default_prevented = False

    def prevent_default(self) -> None:
        """Cancel the action (only meaningful for ``before_remove``)."""
        self.default_prevented = True

    def __repr__(self) -> str:
        return f"NavigationEvent({self.type!r}, {self.route.name!r})"


class NavigatorCore:
    """State machine shared by every ``Navigation`` handle a navigator hands out.

    Owned by the navigator component: created once per mount, updated
    every render with the latest state and setter (see ``update``).
    """

    def __init__(
        self,
        kind: NavigatorKind,
        screens: Mapping[str, ScreenDef],
        state: NavigationState,
        set_state: Callable[[Any], None],
        parent: Optional["Navigation"] = None,
        host: Optional[HostNavigator] = None,
        request_render: Optional[Callable[[], None]] = None,
    ) -> None:
        self.kind = kind
        self.screens: Dict[str, ScreenDef] = dict(screens)
        self.state = state
        self._set_state = set_state
        self.parent = parent
        self.host = host
        self._request_render = request_render
        self._listeners: Dict[Tuple[str, str], List[Listener]] = {}
        # ``set_options`` results, keyed by route key.
        self.runtime_options: Dict[str, Dict[str, Any]] = {}
        self._handles: Dict[str, Navigation] = {}
        self.drawer_open = False
        self._set_drawer_open: Optional[Callable[[bool], None]] = None
        self.on_state_change: Optional[Callable[[NavigationState], None]] = None

    # ------------------------------------------------------------------
    # Wiring from the owning component
    # ------------------------------------------------------------------

    def update(
        self,
        screens: Mapping[str, ScreenDef],
        state: NavigationState,
        set_state: Callable[[Any], None],
        parent: Optional["Navigation"],
        host: Optional[HostNavigator],
    ) -> None:
        """Sync the core with the owning component's latest render.

        Handles and ``set_options`` overrides for routes no longer in ``state`` are dropped.
        """
        self.screens = dict(screens)
        self.state = state
        self._set_state = set_state
        self.parent = parent
        self.host = host
        live = {r.key for r in state.routes}
        for key in list(self._handles):
            if key not in live:
                del self._handles[key]
        for key in list(self.runtime_options):
            if key not in live:
                del self.runtime_options[key]

    @property
    def is_native_root(self) -> bool:
        """Whether this core drives a native screen stack through the host."""
        return self.kind == "stack" and self.host is not None and self.parent is None

    def handle_for(self, route: Route) -> "Navigation":
        """The (cached) handle scoped to ``route``."""
        handle = self._handles.get(route.key)
        if handle is None:
            cls = {"tab": TabNavigation, "drawer": DrawerNavigation}.get(self.kind, Navigation)
            handle = cls(self, route.key)
            self._handles[route.key] = handle
        return handle

    def route_by_key(self, key: str) -> Route:
        """Return the route with ``key``, falling back to the active route once it has left the state."""
        for route in self.state.routes:
            if route.key == key:
                return route
        return self.state.current

    def options_for(self, route: Route) -> Dict[str, Any]:
        """Static screen options merged with any ``set_options`` overrides."""
        screen = self.screens.get(route.name)
        options = screen.resolve_options(route) if screen is not None else {}
        options.update(self.runtime_options.get(route.key, {}))
        return options

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def add_listener(self, route_key: str, event: str, listener: Listener) -> Callable[[], None]:
        """Subscribe ``listener`` to ``event`` for the route with ``route_key``; returns an unsubscribe callable."""
        bucket = self._listeners.setdefault((route_key, event), [])
        bucket.append(listener)

        def remove() -> None:
            try:
                bucket.remove(listener)
            except ValueError:
                pass

        return remove

    def emit(self, route: Route, event: str, data: Optional[Mapping[str, Any]] = None) -> NavigationEvent:
        """Deliver ``event`` to the listeners registered for ``route`` and return the event.

        Check ``default_prevented`` on the result to see whether a ``before_remove`` listener cancelled the action.
        """
        evt = NavigationEvent(event, route, data)
        for listener in list(self._listeners.get((route.key, event), ())):
            try:
                listener(evt)
            except Exception as exc:
                if not diagnostics.report_error(exc, phase=f"navigation {event} listener"):
                    raise
        return evt

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _commit(self, new_state: NavigationState) -> None:
        if new_state == self.state:
            return
        self._set_state(new_state)
        if self.on_state_change is not None:
            self.on_state_change(new_state)

    def _validate(self, name: str) -> bool:
        return name in self.screens

    def _with_initial_params(self, name: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        screen = self.screens.get(name)
        base = dict(screen.initial_params) if screen is not None else {}
        base.update(params)
        return base

    def navigate(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Go to the screen ``name``: stacks pop back to it or push it; tabs and drawers jump to it.

        Unknown routes bubble to the parent navigator. On a native root stack, popping back is delegated to the host.
        """
        if not self._validate(name):
            if self.parent is not None:
                self.parent._core.navigate(name, params, nested)
                return
            raise ValueError(f"Unknown route {name!r}. Known routes: {list(self.screens)}")
        if self.kind == "stack":
            existing = self.state.find(name)
            if existing is None:
                self.push(name, params, nested)
                return
            if existing == self.state.index:
                new_state = self.state.set_params(params) if params else self.state
                if nested is not None:
                    routes = list(new_state.routes)
                    routes[new_state.index] = routes[new_state.index].with_state(nested)
                    new_state = NavigationState(routes, new_state.index)
                if new_state is not self.state:
                    self._commit(new_state)
                return
            new_state = self.state.pop_to(name, params, nested)
            if self.is_native_root:
                self.host.pop_screens(len(self.state) - len(new_state))
                return
            self._commit(new_state)
            return
        self._commit(self.state.jump_to(name, params, nested))

    def push(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Push a new instance of ``name`` with its ``initial_params`` merged under ``params``.

        Non-stack navigators fall back to ``navigate``; unknown routes bubble to the parent navigator.
        """
        if self.kind != "stack":
            self.navigate(name, params, nested)
            return
        if not self._validate(name):
            if self.parent is not None:
                self.parent._core.push(name, params, nested)
                return
            raise ValueError(f"Unknown route {name!r}. Known routes: {list(self.screens)}")
        new_state = self.state.push(name, self._with_initial_params(name, params), nested)
        if self.is_native_root:
            self.host.push_screen(new_state.to_dict(), self.options_for(new_state.current))
            return
        self._commit(new_state)

    def replace(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Swap the active screen for a fresh ``name`` (stacks); tabs and drawers fall back to ``navigate``."""
        if not self._validate(name):
            if self.parent is not None:
                self.parent._core.replace(name, params, nested)
                return
            raise ValueError(f"Unknown route {name!r}. Known routes: {list(self.screens)}")
        if self.kind != "stack":
            self.navigate(name, params, nested)
            return
        new_state = self.state.replace(name, self._with_initial_params(name, params), nested)
        if self.is_native_root:
            self.host.replace_screen(new_state.to_dict(), self.options_for(new_state.current))
            return
        self._commit(new_state)

    def pop(self, count: int = 1, *, source: str = "pop") -> bool:
        """Pop ``count`` screens. Returns whether anything was popped here or by a parent."""
        if self.kind != "stack" or len(self.state) <= 1:
            if self.parent is not None:
                return self.parent.pop(count)
            return False
        count = max(1, min(count, len(self.state) - 1))
        for route in reversed(self.state.routes[len(self.state) - count :]):
            evt = self.emit(route, "before_remove", {"action": source})
            if evt.default_prevented:
                return True
        if self.is_native_root:
            self.host.pop_screens(count)
            return True
        self._commit(self.state.pop(count))
        return True

    def pop_to_top(self) -> None:
        """Pop every screen above the first one (no-op when only one screen is present)."""
        if len(self.state) > 1:
            self.pop(len(self.state) - 1, source="pop_to_top")

    def reset(self, routes: Sequence[Route], index: Optional[int] = None) -> None:
        """Replace the whole history with ``routes``, activating ``index`` (the last route by default).

        Raises ``ValueError`` if any route name is unknown to this navigator.
        """
        for route in routes:
            if not self._validate(route.name):
                raise ValueError(f"Unknown route {route.name!r}. Known routes: {list(self.screens)}")
        new_state = NavigationState(routes, index)
        if self.is_native_root:
            self.host.reset_screens(new_state.to_dict(), self.options_for(new_state.current))
            return
        self._commit(new_state)

    def set_params(self, route_key: str, params: Mapping[str, Any]) -> None:
        """Merge ``params`` into the route with ``route_key`` and commit the new state."""
        routes = list(self.state.routes)
        for i, route in enumerate(routes):
            if route.key == route_key:
                routes[i] = route.with_params(params)
                self._commit(NavigationState(routes, self.state.index))
                return

    def set_options(self, route_key: str, options: Mapping[str, Any]) -> None:
        """Merge runtime ``options`` for the route with ``route_key`` and request a render if anything changed."""
        current = self.runtime_options.setdefault(route_key, {})
        if all(current.get(k) == v for k, v in options.items()) and all(k in current for k in options):
            return
        current.update(options)
        if self._request_render is not None:
            self._request_render()

    def set_drawer_open(self, open_: bool) -> None:
        """Open or close the drawer (no-op unless a drawer navigator owns this core)."""
        if self._set_drawer_open is not None:
            self._set_drawer_open(bool(open_))


class Navigation:
    """Imperative navigation API for one screen.

    Obtained with [`use_navigation`][pythonnative.use_navigation]. Every
    method that changes screens accepts the destination route name
    followed by params as keyword arguments:

    ```python
    nav.navigate("Detail", id=42)
    nav.push("Detail", id=43)
    nav.replace("Login")
    nav.pop()
    nav.pop_to_top()
    nav.set_params(id=44)
    nav.set_options(title="Edited")
    unsubscribe = nav.add_listener("focus", lambda e: print("focused", e.route.name))
    ```

    Unknown routes bubble to the parent navigator, so screens can
    navigate across nested navigators without knowing the tree shape.
    """

    __slots__ = ("_core", "_route_key")

    def __init__(self, core: NavigatorCore, route_key: str) -> None:
        self._core = core
        self._route_key = route_key

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def route(self) -> Route:
        """The route this handle belongs to."""
        return self._core.route_by_key(self._route_key)

    @property
    def kind(self) -> NavigatorKind:
        """``"stack"``, ``"tab"``, or ``"drawer"``."""
        return self._core.kind

    def get_params(self) -> Dict[str, Any]:
        """Params of this handle's route."""
        return dict(self.route.params)

    def get_state(self) -> NavigationState:
        """The owning navigator's current state."""
        return self._core.state

    def get_parent(self) -> Optional["Navigation"]:
        """The handle of the enclosing navigator, or ``None`` at the top."""
        return self._core.parent

    def get_options(self) -> Dict[str, Any]:
        """Effective options for this handle's route (static merged with ``set_options``)."""
        return self._core.options_for(self.route)

    def can_go_back(self) -> bool:
        """Whether ``pop()`` would do anything (here or in a parent)."""
        if self._core.kind == "stack" and len(self._core.state) > 1:
            return True
        parent = self._core.parent
        return parent.can_go_back() if parent is not None else False

    def is_focused(self) -> bool:
        """Whether this handle's route is the navigator's active route."""
        return self._core.state.current.key == self._route_key

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def navigate(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Go to ``route``: switch to it if already present, otherwise push it.

        When ``route`` renders a nested navigator, ``screen`` names the
        screen to show inside it and ``params`` go to that screen:

        ```python
        nav.navigate("Tabs", screen="Profile", user="ada")
        ```
        """
        self._core.navigate(route, *_split_nested(screen, params))

    def push(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Push a new instance of ``route`` (stacks; tabs fall back to ``navigate``)."""
        self._core.push(route, *_split_nested(screen, params))

    def replace(self, route: str, /, *, screen: Optional[str] = None, **params: Any) -> None:
        """Replace the current screen with ``route``."""
        self._core.replace(route, *_split_nested(screen, params))

    def pop(self, count: int = 1) -> bool:
        """Pop ``count`` screens off the nearest stack; returns whether anything happened."""
        return self._core.pop(count)

    def go_back(self) -> bool:
        """Alias for ``pop()``."""
        return self._core.pop(1, source="go_back")

    def pop_to_top(self) -> None:
        """Pop every screen above the first one."""
        self._core.pop_to_top()

    def reset(self, *routes: Union[str, Route], index: Optional[int] = None, **params: Any) -> None:
        """Replace the whole history.

        ``nav.reset("Home")`` installs a single route (``params`` apply
        to it); ``nav.reset(Route("A"), Route("B", {...}))`` installs
        several, with ``index`` selecting the active one (last by
        default).
        """
        if not routes:
            raise TypeError("reset() needs at least one route")
        if len(routes) == 1 and isinstance(routes[0], str):
            self._core.reset([Route(routes[0], params)], index)
            return
        if params:
            raise TypeError("params keywords are only allowed when resetting to a single route name")
        resolved = [Route(r) if isinstance(r, str) else r for r in routes]
        self._core.reset(resolved, index)

    def set_params(self, **params: Any) -> None:
        """Merge ``params`` into this handle's route."""
        self._core.set_params(self._route_key, params)

    def set_options(self, **options: Any) -> None:
        """Override [`ScreenOptions`][pythonnative.ScreenOptions] for this route at runtime."""
        self._core.set_options(self._route_key, options)

    def add_listener(self, event: EventName, listener: Listener) -> Callable[[], None]:
        """Subscribe to ``"focus"``, ``"blur"``, ``"before_remove"``, or ``"state"`` for this route.

        Returns an unsubscribe callable. ``before_remove`` listeners may
        call ``event.prevent_default()`` to keep the screen (useful for
        unsaved-changes prompts). Native back gestures on iOS can't be
        intercepted this way; use ``gesture_enabled=False`` to disable
        them for such screens.
        """
        return self._core.add_listener(self._route_key, event, listener)

    def __repr__(self) -> str:
        return f"<Navigation {self._core.kind} route={self.route.name!r}>"


def _split_nested(screen: Optional[str], params: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[NavigationState]]:
    """Turn ``screen=...`` into a nested seed state (params then belong to the nested screen)."""
    if screen is None:
        return params, None
    return {}, NavigationState([Route(screen, params)])


class TabNavigation(Navigation):
    """Handle for screens inside a tab navigator (adds ``jump_to``)."""

    __slots__ = ()

    def jump_to(self, route: str, /, **params: Any) -> None:
        """Switch to the tab named ``route``."""
        self._core.navigate(route, params)


class DrawerNavigation(Navigation):
    """Handle for screens inside a drawer navigator (adds drawer controls)."""

    __slots__ = ()

    def jump_to(self, route: str, /, **params: Any) -> None:
        """Switch to the drawer screen named ``route`` and close the drawer."""
        self._core.navigate(route, params)
        self._core.set_drawer_open(False)

    def open_drawer(self) -> None:
        """Slide the drawer menu open."""
        self._core.set_drawer_open(True)

    def close_drawer(self) -> None:
        """Close the drawer menu."""
        self._core.set_drawer_open(False)

    def toggle_drawer(self) -> None:
        """Open the drawer menu if it's closed, otherwise close it."""
        self._core.set_drawer_open(not self._core.drawer_open)

    def is_drawer_open(self) -> bool:
        """Return whether the drawer menu is currently open."""
        return self._core.drawer_open


NavigationContext: Context[Optional[Navigation]] = create_context(None, name="Navigation")
"""Provides the [`Navigation`][pythonnative.Navigation] handle for the current screen."""

FocusContext: Context[bool] = create_context(True, name="Focus")
"""Whether the current subtree is the focused screen (see [`use_is_focused`][pythonnative.use_is_focused])."""
