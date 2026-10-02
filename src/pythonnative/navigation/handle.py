"""The [`Navigation`][pythonnative.Navigation] handle and the navigator core behind it.

Every screen rendered by a navigator receives a ``Navigation`` object
through [`use_navigation`][pythonnative.use_navigation]. The handle is
scoped to the screen's route (so ``add_listener("focus", ...)`` fires
for *that* screen) and forwards every action to the
[`NavigatorCore`][pythonnative.navigation.handle.NavigatorCore] that
owns the navigator's state.

Destinations are screen components, called with their params:
``nav.push(ItemScreen(id=42))``. The core looks the component up in its
own navigator, then in navigators statically nested in it, then in each
ancestor, so ``nav.navigate(ProfileScreen(user="ada"))`` reaches a
screen inside a sibling tab without naming the tab.

Every route removal (``pop``, ``pop_to``, ``navigate`` back to an
existing route, ``replace``, and ``reset``) first emits
``before_remove`` for each route that would leave the state; a
listener that calls ``prevent_default()`` cancels the whole
operation. On a native host the stack navigator re-synchronizes the
native screen stack after a vetoed back gesture.
"""

from __future__ import annotations

import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Unpack,
)

from .. import diagnostics
from ..component import Component
from ..element import Element, Node
from ..equality import equal
from ..hooks import Context, create_context
from .screen import Screen, ScreenOptions, ScreenTarget, find_screen, validate_screen_options
from .state import NavigationState, Route

if TYPE_CHECKING:
    from .navigators import Navigator

__all__ = [
    "DrawerNavigation",
    "FocusContext",
    "HostNavigator",
    "Navigation",
    "NavigationContext",
    "NavigationEvent",
    "NavigatorCore",
    "TabNavigation",
    "provide",
    "split_target",
]

NavigatorKind = Literal["stack", "tab", "drawer"]
EventName = Literal["focus", "blur", "before_remove", "state"]
Listener = Callable[["NavigationEvent"], None]

CONTAINER_ROUTE_KEY = "__container__"
"""Route key of the navigator-level handle bound to a ``NavigationRef``; it always resolves to the active route."""


def provide(context: Context[Any], value: Any, *children: Node, key: Optional[str] = None) -> Element:
    """Return a provider element for ``context`` carrying ``value`` over ``children``.

    Equivalent to ``context.Provider(...)``; navigation builds the
    element directly so it doesn't depend on the ``Provider`` call
    signature.
    """
    return Element(context, {"value": value}, list(children), key=key)


class HostNavigator(Protocol):
    """What a root stack needs from the native screen host.

    Hosts and FakeHost publish application focus and cached navigation state.
    Screen presentation belongs to the logical tree and its native containers.
    """

    is_focused: bool

    def initial_navigation_state(self) -> Optional[Dict[str, Any]]:
        """The serialized state this screen was pushed with, if any."""
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
    every render with the latest navigator value, state, and setter
    (see ``update``). Internally routes are addressed by name, which is
    what serialized state and native screens carry; the public API
    addresses screens by component.
    """

    def __init__(
        self,
        navigator: "Navigator",
        state: NavigationState,
        set_state: Callable[[Any], None],
        parent: Optional["Navigation"] = None,
        host: Optional[HostNavigator] = None,
        request_render: Optional[Callable[[], None]] = None,
    ) -> None:
        self.navigator = navigator
        self.kind: NavigatorKind = navigator.kind
        self.screens: Dict[str, Screen] = {screen.name: screen for screen in navigator.screens}
        self.state = state
        self._set_state = set_state
        self.parent = parent
        self.host = host
        self._request_render = request_render
        self._listeners: Dict[Tuple[str, str], List[Listener]] = {}
        # Options set at runtime (``set_options`` / ``use_screen_options``), keyed by route key.
        self.runtime_options: Dict[str, Dict[str, Any]] = {}
        self._handles: Dict[str, Navigation] = {}
        self._bodies: Dict[str, Tuple[Any, Any, Element]] = {}
        self._container_handle: Optional[Navigation] = None
        self.drawer_open = False
        self._set_drawer_open: Optional[Callable[[bool], None]] = None
        self.on_state_change: Optional[Callable[[NavigationState], None]] = None

    # ------------------------------------------------------------------
    # Wiring from the owning component
    # ------------------------------------------------------------------

    def update(
        self,
        navigator: "Navigator",
        state: NavigationState,
        set_state: Callable[[Any], None],
        parent: Optional["Navigation"],
        host: Optional[HostNavigator],
    ) -> None:
        """Sync the core with the owning component's latest render.

        Handles, cached screen bodies, and runtime options for routes no
        longer in ``state`` are dropped.
        """
        self.navigator = navigator
        self.screens = {screen.name: screen for screen in navigator.screens}
        self.state = state
        self._set_state = set_state
        self.parent = parent
        self.host = host
        live = {r.key for r in state.routes}
        for cache in (self._handles, self.runtime_options, self._bodies):
            for key in [key for key in cache if key not in live]:
                del cache[key]

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

    def container_handle(self) -> "Navigation":
        """The navigator-level handle bound to a ``NavigationRef``; its ``route`` is always the active route."""
        if self._container_handle is None:
            self._container_handle = Navigation(self, CONTAINER_ROUTE_KEY)
        return self._container_handle

    def body_for(self, route: Route) -> Element:
        """The screen element for ``route``, reused while its params and component are unchanged.

        Returning the identical element lets the reconciler skip the
        screen when only the navigator re-renders (an option change, a
        focus change, another route's update).
        """
        screen = self.screens[route.name]
        cached = self._bodies.get(route.key)
        if cached is not None and cached[0] is route.params and cached[1] is screen.component:
            return cached[2]
        body = screen.render(route.params)
        self._bodies[route.key] = (route.params, screen.component, body)
        return body

    def options_for(self, route: Route) -> Dict[str, Any]:
        """Effective options: navigator, then groups, then the screen, then runtime options."""
        options: Dict[str, Any] = dict(self.navigator.screen_options)
        options.update(self.navigator.group_options.get(route.name, {}))
        screen = self.screens.get(route.name)
        if screen is not None:
            options.update(screen.options)
        options.update(self.runtime_options.get(route.key, {}))
        return options

    # ------------------------------------------------------------------
    # Targets
    # ------------------------------------------------------------------

    def resolve(self, target: Any) -> Tuple[List[Screen], Dict[str, Any]]:
        """Locate ``target`` from this navigator and split off its params.

        Returns the chain of screens from this navigator down to the
        target (one entry when the target is a direct screen), and the
        params for the target screen.

        Raises:
            LookupError: If neither this navigator nor any navigator
                nested in it statically renders the target.
            TypeError: If ``target`` isn't a screen element, component,
                or navigator.
        """
        component, params = split_target(target)
        chain = self.navigator.path_to(component)
        if chain is None:
            raise LookupError(component)
        return chain, params

    def _route_through(
        self, chain: List[Screen], params: Mapping[str, Any]
    ) -> Tuple[str, Dict[str, Any], Optional[NavigationState]]:
        """``(name, params, nested_seed)`` for acting on ``chain[0]`` so the last screen gets ``params``."""
        if len(chain) == 1:
            return chain[0].name, dict(params), None
        seed = NavigationState([Route(chain[-1].name, params)])
        for screen in reversed(chain[1:-1]):
            seed = NavigationState([Route(screen.name, state=seed)])
        return chain[0].name, {}, seed

    def act(self, action: str, target: Any) -> None:
        """Run ``action`` (``navigate``, ``push``, ``replace``, ``pop_to``, ``jump_to``) toward ``target``.

        A target this navigator can't reach is handed to the parent
        navigator; at the root an unknown target raises ``ValueError``.
        """
        try:
            chain, params = self.resolve(target)
        except LookupError:
            if self.parent is not None:
                self.parent._core.act(action, target)
                return
            raise ValueError(
                f"{_describe(target)} isn't a screen of this navigator tree. Known routes: {list(self.screens)}"
            ) from None
        name, own_params, nested = self._route_through(chain, params)
        if action == "push" and nested is None:
            self.push(name, own_params)
        elif action == "replace":
            self.replace(name, own_params, nested)
        elif action == "pop_to":
            self.pop_to(name, own_params, nested)
        else:
            self.navigate(name, own_params, nested)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def add_listener(self, route_key: str, event: str, listener: Listener) -> Callable[[], None]:
        """Subscribe ``listener`` to ``event`` for the route with ``route_key``; returns an unsubscribe callable."""
        bucket = self._listeners.setdefault((route_key, event), [])
        bucket.append(listener)
        if event == "before_remove" and len(bucket) == 1:
            self._guard_changed()

        def remove() -> None:
            try:
                bucket.remove(listener)
            except ValueError:
                return
            if event == "before_remove" and not bucket:
                self._guard_changed()

        return remove

    def has_listeners(self, route_key: str, event: str) -> bool:
        """Whether any listener is registered for ``event`` on the route with ``route_key``."""
        return bool(self._listeners.get((route_key, event)))

    def _guard_changed(self) -> None:
        """A route gained or lost its last ``before_remove`` listener: re-render so ``Screen.guarded`` follows."""
        if self._request_render is not None:
            self._request_render()

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

    def _removal_allowed(self, routes: Sequence[Route], action: str) -> bool:
        """Emit ``before_remove`` for ``routes`` (topmost first); ``False`` if any listener vetoed."""
        for route in reversed(list(routes)):
            evt = self.emit(route, "before_remove", {"action": action})
            if evt.default_prevented:
                return False
        return True

    # ------------------------------------------------------------------
    # State transitions (by route name)
    # ------------------------------------------------------------------

    def _commit(self, new_state: NavigationState) -> None:
        if new_state == self.state:
            return
        # Reflect the commit at once so handles (and the native back path)
        # see the new state before the owning component re-renders.
        self.state = new_state
        self._set_state(new_state)
        if self.on_state_change is not None:
            self.on_state_change(new_state)

    def _require(self, name: str) -> None:
        if name not in self.screens:
            raise ValueError(f"Unknown route {name!r}. Known routes: {list(self.screens)}")

    def navigate(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Go to the route ``name``: stacks pop back to it or push it; tabs and drawers jump to it."""
        self._require(name)
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
            if not self._removal_allowed(self.state.routes[existing + 1 :], "navigate"):
                return
            self._commit(self.state.pop_to(name, params, nested))
            return
        self._commit(self.state.jump_to(name, params, nested))

    def push(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Push a new route ``name`` (stacks); tabs and drawers fall back to ``navigate``."""
        self._require(name)
        if self.kind != "stack":
            self.navigate(name, params, nested)
            return
        self._commit(self.state.push(name, params, nested))

    def replace(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Swap the active route for a fresh ``name`` (stacks); tabs and drawers fall back to ``navigate``."""
        self._require(name)
        if self.kind != "stack":
            self.navigate(name, params, nested)
            return
        if not self._removal_allowed([self.state.current], "replace"):
            return
        self._commit(self.state.replace(name, params, nested))

    def pop(self, count: int = 1, *, source: str = "pop") -> bool:
        """Pop ``count`` screens. Returns whether anything was popped here or by a parent.

        A ``before_remove`` veto counts as handled (``True``) while leaving the state unchanged.
        """
        if self.kind != "stack" or len(self.state) <= 1:
            if self.parent is not None:
                return self.parent.pop(count)
            return False
        count = max(1, min(count, len(self.state) - 1))
        if not self._removal_allowed(self.state.routes[len(self.state) - count :], source):
            return True
        self._commit(self.state.pop(count))
        return True

    def pop_to_top(self) -> None:
        """Pop every screen above the first one (no-op when only one screen is present)."""
        if len(self.state) > 1:
            self.pop(len(self.state) - 1, source="pop_to_top")

    def pop_to(self, name: str, params: Mapping[str, Any], nested: Optional[NavigationState] = None) -> None:
        """Pop back to the most recent ``name``, merging ``params`` into it.

        When ``name`` isn't in the history the active screen is replaced
        by a fresh ``name`` instead (React Navigation's ``popTo``
        semantics). Non-stack navigators fall back to ``navigate``.
        """
        self._require(name)
        if self.kind != "stack":
            self.navigate(name, params, nested)
            return
        existing = self.state.find(name)
        if existing is None:
            self.replace(name, params, nested)
            return
        if existing == self.state.index:
            self.navigate(name, params, nested)
            return
        if not self._removal_allowed(self.state.routes[existing + 1 :], "pop_to"):
            return
        self._commit(self.state.pop_to(name, params, nested))

    def reset(self, routes: Sequence[Route], index: Optional[int] = None) -> None:
        """Replace the whole history with ``routes``, activating ``index`` (the last route by default).

        ``before_remove`` fires for every current route whose key isn't in
        ``routes``; a veto leaves the state untouched.
        """
        for route in routes:
            self._require(route.name)
        kept = {route.key for route in routes}
        removed = [route for route in self.state.routes if route.key not in kept]
        if not self._removal_allowed(removed, "reset"):
            return
        self._commit(NavigationState(routes, index))

    def set_params(self, route_key: str, params: Mapping[str, Any]) -> None:
        """Merge ``params`` into the route with ``route_key``; its screen re-renders with the new arguments."""
        routes = list(self.state.routes)
        for i, route in enumerate(routes):
            if route.key == route_key:
                screen = self.screens.get(route.name)
                if screen is not None and isinstance(screen.component, Component):
                    screen.component(**{**route.params, **params})  # validate against the signature
                routes[i] = route.with_params(params)
                self._commit(NavigationState(routes, self.state.index))
                return

    def set_options(self, route_key: str, options: Mapping[str, Any]) -> None:
        """Merge runtime ``options`` for the route with ``route_key``; re-render only if something changed.

        Raises:
            TypeError: For an unknown option key.
            ValueError: For an unknown ``presentation`` or ``animation`` value.
        """
        validate_screen_options(options)
        current = self.runtime_options.setdefault(route_key, {})
        if all(key in current and equal(current[key], value) for key, value in options.items()):
            return
        current.update(options)
        if self._request_render is not None:
            self._request_render()

    def set_drawer_open(self, open_: bool) -> None:
        """Open or close the drawer (no-op unless a drawer navigator owns this core)."""
        if self._set_drawer_open is not None:
            self._set_drawer_open(bool(open_))


def split_target(target: Any) -> Tuple[Any, Dict[str, Any]]:
    """Split a navigation target into ``(component_or_navigator, params)``.

    An element built by calling a screen component carries the params
    as its props; a navigator's element carries none. A bare component
    or navigator means "no params".

    Raises:
        TypeError: If ``target`` isn't a screen element, component, or navigator.
    """
    from .navigators import Navigator, navigator_of

    if isinstance(target, Element):
        navigator = navigator_of(target)
        if navigator is not None:
            return navigator, {}
        if isinstance(target.type, Component):
            if target.children:
                raise TypeError(f"A screen target can't carry children: {target!r}")
            return target.type, _explicit_params(target.type, target.props)
    if isinstance(target, (Component, Navigator)):
        return target, {}
    raise TypeError(
        f"Navigation targets are screen elements like ItemScreen(id=1), components, or navigators; got {target!r}"
    )


def _explicit_params(component: Component[Any], props: Mapping[str, Any]) -> Dict[str, Any]:
    """The props a caller passed, leaving out parameter defaults the call filled in.

    ``ItemScreen(id=1)`` binds ``tab="details"`` from the signature; as a
    navigation target it carries only ``id``, so navigating back to an
    existing ``ItemScreen`` route merges ``id`` without resetting ``tab``,
    and the screen still receives its defaults when it renders.
    """
    parameters = inspect.signature(component.fn).parameters
    explicit: Dict[str, Any] = {}
    for name, value in props.items():
        parameter = parameters.get(name)
        if parameter is not None and parameter.default is not inspect.Parameter.empty and value is parameter.default:
            continue
        explicit[name] = value
    return explicit


def _describe(target: Any) -> str:
    try:
        component, _ = split_target(target)
    except TypeError:
        return repr(target)
    return getattr(component, "display_name", None) or getattr(component, "name", None) or repr(component)


class Navigation:
    """Imperative navigation API for one screen.

    Obtained with [`use_navigation`][pythonnative.use_navigation].
    Destinations are screen components called with their params, so the
    type checker verifies them:

    ```python
    nav.push(ItemScreen(id=42))
    nav.navigate(SettingsScreen())
    nav.replace(LoginScreen())
    nav.pop()
    nav.pop_to(HomeScreen)
    nav.pop_to_top()
    nav.set_params(id=44)
    nav.set_options(title="Edited")
    unsubscribe = nav.add_listener("focus", lambda e: print("focused", e.route.name))
    ```

    A destination this navigator doesn't know is looked up in the
    navigators nested in it and then in each enclosing navigator, so
    screens can navigate anywhere in the tree without knowing its
    shape.
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

    def get_state(self) -> NavigationState:
        """The owning navigator's current state."""
        return self._core.state

    def get_parent(self) -> Optional["Navigation"]:
        """The handle of the enclosing navigator, or ``None`` at the top."""
        return self._core.parent

    def get_options(self) -> Dict[str, Any]:
        """Effective options for this handle's route (static merged with runtime options)."""
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

    def navigate(self, target: Element, /) -> None:
        """Go to ``target``: pop back to it if it's in the stack (merging params), otherwise push it.

        Tab and drawer navigators switch to it. A target inside a
        nested navigator opens that navigator on the target.
        """
        self._core.act("navigate", target)

    def push(self, target: Element, /) -> None:
        """Push a new instance of ``target`` (stacks; tabs and drawers switch to it)."""
        self._core.act("push", target)

    def replace(self, target: Element, /) -> None:
        """Replace the current screen with ``target``."""
        self._core.act("replace", target)

    def pop(self, count: int = 1) -> bool:
        """Pop ``count`` screens off the nearest stack; returns whether anything happened."""
        return self._core.pop(count)

    def go_back(self) -> bool:
        """Pop one screen off the nearest stack; returns whether anything happened."""
        return self._core.pop(1, source="go_back")

    def pop_to_top(self) -> None:
        """Pop every screen above the first one."""
        self._core.pop_to_top()

    def pop_to(self, target: ScreenTarget, /) -> None:
        """Pop back to the most recent ``target`` (a component, or an element whose params are merged in).

        If ``target`` isn't in the history, the active screen is replaced
        by it. ``before_remove`` fires for every screen popped.
        """
        self._core.act("pop_to", target)

    def reset(self, *targets: Element, index: Optional[int] = None) -> None:
        """Replace the whole history of this navigator with ``targets`` (``index`` active, the last by default).

        ```python
        nav.reset(HomeScreen(), ItemScreen(id=1))
        ```
        """
        if not targets:
            raise TypeError("reset() needs at least one screen")
        routes: List[Route] = []
        for target in targets:
            component, params = split_target(target)
            screen = find_screen(self._core.screens.values(), component)
            if screen is None:
                raise ValueError(f"{_describe(target)} isn't a screen of this navigator")
            routes.append(Route(screen.name, params))
        self._core.reset(routes, index)

    def set_params(self, **params: Any) -> None:
        """Merge ``params`` into this screen's arguments; the screen re-renders with them."""
        self._core.set_params(self._route_key, params)

    def set_options(self, **options: Unpack[ScreenOptions]) -> None:
        """Set [`ScreenOptions`][pythonnative.ScreenOptions] for this screen at runtime.

        Prefer [`use_screen_options`][pythonnative.use_screen_options]
        from the screen's own render; call this to change another
        screen's options (``nav.get_parent().set_options(...)``).
        """
        self._core.set_options(self._route_key, options)

    def add_listener(self, event: EventName, listener: Listener) -> Callable[[], None]:
        """Subscribe to ``"focus"``, ``"blur"``, ``"before_remove"``, or ``"state"`` for this route.

        Returns an unsubscribe callable. ``before_remove`` fires for
        every removal (``pop``, ``pop_to``, ``navigate`` back to an
        existing route, ``replace``, ``reset``, and the system back
        gesture) and its ``data["action"]`` names the cause. Listeners
        may call ``event.prevent_default()`` to keep the screen (useful
        for unsaved-changes prompts); after a vetoed native back the
        stack restores the native screens to match. Set
        ``gesture_enabled=False`` (iOS only) to disable the swipe
        gesture outright instead of animating it out and back.
        """
        return self._core.add_listener(self._route_key, event, listener)

    def __repr__(self) -> str:
        return f"<Navigation {self._core.kind} route={self.route.name!r}>"


class TabNavigation(Navigation):
    """Handle for screens inside a tab navigator (adds ``jump_to``)."""

    __slots__ = ()

    def jump_to(self, target: ScreenTarget, /) -> None:
        """Switch to the tab rendering ``target`` (an element's params are merged into the tab's)."""
        self._core.act("jump_to", target)


class DrawerNavigation(Navigation):
    """Handle for screens inside a drawer navigator (adds drawer controls)."""

    __slots__ = ()

    def jump_to(self, target: ScreenTarget, /) -> None:
        """Switch to the drawer screen rendering ``target`` and close the drawer."""
        self._core.act("jump_to", target)
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
