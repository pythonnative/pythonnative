"""Declarative navigation for PythonNative.

Provides a component-based navigation system inspired by React
Navigation. Navigators manage screen state in Python and the
[`Stack`][pythonnative.create_stack_navigator] navigator pushes real
native screen containers (``UIViewController`` on iOS,
``Fragment`` on Android) so users get system-grade transitions and
swipe-back gestures for free.

Three navigator factories are provided out of the box:

- [`create_stack_navigator`][pythonnative.create_stack_navigator]: push
  and pop screens with native transitions when the navigator is mounted
  at the root of an app host.
- [`create_tab_navigator`][pythonnative.create_tab_navigator]: switch
  between sibling tabs (with a tab bar).
- [`create_drawer_navigator`][pythonnative.create_drawer_navigator]:
  switch between sibling screens via a side drawer menu.

Navigators may be nested arbitrarily; nested handles forward unknown
routes and root-level ``go_back`` calls to their parent.

Stack navigators rendered as the root of an app host (i.e. the parent
[`use_navigation`][pythonnative.use_navigation] handle is the host's
own handle) talk to the platform via that host's ``_push`` / ``_pop``
methods, so the back stack matches what UIKit / AndroidX maintain.
Nested stacks (e.g. a stack inside a tab) fall back to in-Python
state; there's no second native navigation controller to push
onto in that case.

Example:
    ```python
    import pythonnative as pn

    Stack = pn.create_stack_navigator()

    @pn.component
    def App():
        return pn.NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", component=HomeScreen, options={"title": "Home"}),
                Stack.Screen("Detail", component=DetailScreen, options={"title": "Detail"}),
            )
        )
    ```
"""

from typing import Any, Callable, Dict, List, Optional

from .element import Element
from .hooks import (
    Provider,
    _NavigationContext,
    component,
    create_context,
    use_context,
    use_effect,
    use_memo,
    use_ref,
    use_state,
)

# ======================================================================
# Focus context
# ======================================================================

# Defaults to True: components rendered outside any declarative
# navigator (e.g. the root component of a screen pushed via the host's
# native nav stack) are by definition focused; the host's own
# ``on_resume`` / ``on_pause`` lifecycle drives the focus state for
# those. Declarative navigators override this provider on the active
# subtree (always True today; reserved for future inactive-screen
# rendering).
_FocusContext = create_context(True)

# ======================================================================
# Data structures
# ======================================================================


class _ScreenDef:
    """Configuration for a single screen within a navigator.

    Attributes:
        name: Route name used by `navigate(name, ...)`.
        component: A `@component` function rendered when this screen is
            active.
        options: Free-form per-screen options (e.g., `title` for the
            tab bar, `headerShown`, etc.). Interpretation is up to the
            specific navigator implementation.
    """

    __slots__ = ("name", "component", "options")

    def __init__(self, name: str, component_fn: Any, options: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.component = component_fn
        self.options = options or {}

    def __repr__(self) -> str:
        return f"Screen({self.name!r})"


class _RouteEntry:
    """One entry on a stack-style navigation stack.

    Attributes:
        name: Route name (matches a `_ScreenDef.name`).
        params: Params dict passed via `navigate(..., params=...)`.
    """

    __slots__ = ("name", "params")

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.params = params or {}

    def __repr__(self) -> str:
        return f"Route({self.name!r})"


# ======================================================================
# Navigation handle for declarative navigators
# ======================================================================


_INITIAL_ROUTE_KEY = "__pn_initial_route__"
_INITIAL_PARAMS_KEY = "__pn_initial_params__"


def _parent_is_app_host(parent: Any) -> bool:
    """Return True when ``parent`` is the host's own NavigationHandle.

    The host's
    [`NavigationHandle`][pythonnative.hooks.NavigationHandle] sets a
    ``_host`` attribute pointing at the owning app host. Declarative
    navigators check for that marker to decide whether they should
    push real native screens (root navigator) or fall back to
    in-Python state (nested navigator).
    """
    return parent is not None and hasattr(parent, "_host") and getattr(parent, "_host", None) is not None


class _DeclarativeNavHandle:
    """Navigation handle provided by declarative navigators.

    Implements the same interface as
    [`NavigationHandle`][pythonnative.hooks.NavigationHandle] so
    [`use_navigation`][pythonnative.use_navigation] returns a
    compatible object regardless of whether the app drives navigation
    imperatively or through declarative navigators.

    When ``parent`` is the host's own ``NavigationHandle`` (root
    Stack), ``navigate`` / ``go_back`` / ``reset`` drive the native
    navigation controller and the in-Python stack is bypassed; the
    OS owns the back-stack source of truth.

    When ``parent`` is another declarative handle (nested navigator),
    unknown routes and root-level ``go_back`` calls are forwarded to
    the parent so a stack inside a tab still pops correctly.
    """

    def __init__(
        self,
        screen_map: Dict[str, "_ScreenDef"],
        get_stack: Callable[[], List["_RouteEntry"]],
        set_stack: Callable,
        parent: Any = None,
    ) -> None:
        self._screen_map = screen_map
        self._get_stack = get_stack
        self._set_stack = set_stack
        self._parent = parent
        self._host_component_path: Optional[str] = None

    def _push_via_host(self, route_name: str, params: Optional[Dict[str, Any]]) -> bool:
        """Try to push via the underlying app host. Returns True if it ran."""
        if not _parent_is_app_host(self._parent):
            return False
        host = self._parent._host
        component_path = self._host_component_path or getattr(host, "_component_path", None)
        if not component_path:
            return False
        push_args = {
            _INITIAL_ROUTE_KEY: route_name,
            _INITIAL_PARAMS_KEY: params or {},
        }
        try:
            host._push(component_path, push_args)
            return True
        except Exception:
            return False

    def _pop_via_host(self) -> bool:
        """Try to pop via the underlying app host. Returns True if it ran."""
        if not _parent_is_app_host(self._parent):
            return False
        try:
            self._parent._host._pop()
            return True
        except Exception:
            return False

    def navigate(self, route_name: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Navigate to a named route.

        Behaviour depends on the kind of navigator:

        - **Root stack** (parent is the host's NavigationHandle): the
          host's native ``_push`` is invoked so the user sees a real
          UIKit / AndroidX transition; the in-Python stack is left
          untouched because the native controller is the source of
          truth.
        - **Nested stack / tab / drawer**: ``set_stack`` is called with
          the new route; the parent reconciler re-renders the active
          screen subtree in place.
        - **Unknown route**: forwarded to ``parent`` if one exists,
          otherwise raises ``ValueError``.

        Args:
            route_name: A route registered on this navigator.
            params: Optional dict made available to the destination
                screen via [`use_route`][pythonnative.use_route] or
                ``nav.get_params()``.

        Raises:
            ValueError: If ``route_name`` is unknown and no parent
                handle exists.
        """
        if route_name in self._screen_map:
            if self._push_via_host(route_name, params):
                return
            entry = _RouteEntry(route_name, params)
            self._set_stack(lambda s: list(s) + [entry])
        elif self._parent is not None:
            self._parent.navigate(route_name, params=params)
        else:
            raise ValueError(f"Unknown route: {route_name!r}. Known routes: {list(self._screen_map)}")

    def go_back(self) -> None:
        """Pop the current screen from the stack.

        Resolution order:

        1. If the current stack has more than one entry (a real
           in-Python push), pop the top.
        2. If the parent is the host's NavigationHandle, pop the
           native navigation controller.
        3. If the parent is another declarative handle, forward.
        4. Otherwise no-op.
        """
        stack = self._get_stack()
        if len(stack) > 1:
            self._set_stack(lambda s: list(s[:-1]))
            return
        if self._pop_via_host():
            return
        if self._parent is not None:
            self._parent.go_back()

    def get_params(self) -> Dict[str, Any]:
        """Return the params dict for the current route.

        Returns:
            The dict supplied to the most recent matching ``navigate(...)``
            call, or an empty dict if none was supplied.
        """
        stack = self._get_stack()
        return stack[-1].params if stack else {}

    def reset(self, route_name: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Reset the stack to a single route.

        For a root stack this pops every screen above the original
        root (the screen the user landed on when the app launched)
        and then pushes ``route_name`` on top. For nested navigators
        the in-Python stack is replaced wholesale.

        Args:
            route_name: Route to install as the new root.
            params: Optional params for that route.

        Raises:
            ValueError: If ``route_name`` is unknown.
        """
        if route_name not in self._screen_map:
            raise ValueError(f"Unknown route: {route_name!r}. Known routes: {list(self._screen_map)}")
        if _parent_is_app_host(self._parent):
            host = self._parent._host
            reset_fn = getattr(host, "_reset_to_root", None)
            if callable(reset_fn):
                try:
                    reset_fn()
                except Exception:
                    pass
            if self._push_via_host(route_name, params):
                return
        self._set_stack([_RouteEntry(route_name, params)])


class _TabNavHandle(_DeclarativeNavHandle):
    """Navigation handle for tab navigators.

    `navigate(name)` switches the active tab instead of pushing a new
    entry onto a stack. Unknown routes are forwarded to the parent
    handle if one exists.
    """

    def __init__(
        self,
        screen_map: Dict[str, "_ScreenDef"],
        get_stack: Callable[[], List["_RouteEntry"]],
        set_stack: Callable,
        switch_tab: Callable[[str, Optional[Dict[str, Any]]], None],
        parent: Any = None,
    ) -> None:
        super().__init__(screen_map, get_stack, set_stack, parent=parent)
        self._switch_tab = switch_tab

    def navigate(self, route_name: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Switch to a tab by name, or forward to parent for unknown routes."""
        if route_name in self._screen_map:
            self._switch_tab(route_name, params)
        elif self._parent is not None:
            self._parent.navigate(route_name, params=params)
        else:
            raise ValueError(f"Unknown route: {route_name!r}. Known routes: {list(self._screen_map)}")


class _DrawerNavHandle(_DeclarativeNavHandle):
    """Navigation handle for drawer navigators.

    Adds drawer-specific methods
    ([`open_drawer`][pythonnative.navigation._DrawerNavHandle.open_drawer],
    [`close_drawer`][pythonnative.navigation._DrawerNavHandle.close_drawer],
    [`toggle_drawer`][pythonnative.navigation._DrawerNavHandle.toggle_drawer])
    on top of the standard `_DeclarativeNavHandle` interface.
    """

    def __init__(
        self,
        screen_map: Dict[str, "_ScreenDef"],
        get_stack: Callable[[], List["_RouteEntry"]],
        set_stack: Callable,
        switch_screen: Callable[[str, Optional[Dict[str, Any]]], None],
        set_drawer_open: Callable[[bool], None],
        get_drawer_open: Callable[[], bool],
        parent: Any = None,
    ) -> None:
        super().__init__(screen_map, get_stack, set_stack, parent=parent)
        self._switch_screen = switch_screen
        self._set_drawer_open = set_drawer_open
        self._get_drawer_open = get_drawer_open

    def navigate(self, route_name: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Switch to a screen and close the drawer, or forward to parent."""
        if route_name in self._screen_map:
            self._switch_screen(route_name, params)
            self._set_drawer_open(False)
        elif self._parent is not None:
            self._parent.navigate(route_name, params=params)
        else:
            raise ValueError(f"Unknown route: {route_name!r}. Known routes: {list(self._screen_map)}")

    def open_drawer(self) -> None:
        """Open the drawer."""
        self._set_drawer_open(True)

    def close_drawer(self) -> None:
        """Close the drawer."""
        self._set_drawer_open(False)

    def toggle_drawer(self) -> None:
        """Toggle the drawer open/closed."""
        self._set_drawer_open(not self._get_drawer_open())


# ======================================================================
# Stack navigator
# ======================================================================


def _build_screen_map(screens: Any) -> Dict[str, "_ScreenDef"]:
    """Build an ordered dict of name -> _ScreenDef from a list."""
    result: Dict[str, _ScreenDef] = {}
    for s in screens or []:
        if isinstance(s, _ScreenDef):
            result[s.name] = s
    return result


def _read_host_initial_route(parent_nav: Any) -> "tuple[Optional[str], Dict[str, Any]]":
    """Extract a host-provided initial route from a parent NavigationHandle.

    When a pushed VC/Fragment boots, the host's ``_args`` carry the
    requested route name and params (set by
    [`_DeclarativeNavHandle._push_via_host`][pythonnative.navigation._DeclarativeNavHandle._push_via_host]).
    The root Stack navigator reads them so the new screen renders on
    the right entry rather than the navigator's first registered
    screen.

    Returns:
        ``(route_name, params)``. Both are ``None`` / ``{}`` when no
        host args are present.
    """
    if not _parent_is_app_host(parent_nav):
        return None, {}
    args = parent_nav.get_params() if parent_nav is not None else {}
    if not isinstance(args, dict):
        return None, {}
    route = args.get(_INITIAL_ROUTE_KEY)
    params = args.get(_INITIAL_PARAMS_KEY) or {}
    if not isinstance(route, str) or not route:
        return None, {}
    if not isinstance(params, dict):
        params = {}
    return route, params


def _apply_screen_options(parent_nav: Any, screen_def: "_ScreenDef") -> None:
    """Push the active screen's options into the host (title, etc.)."""
    if not _parent_is_app_host(parent_nav):
        return
    host = parent_nav._host
    title = screen_def.options.get("title") if screen_def is not None else None
    setter = getattr(host, "_set_screen_options", None)
    if callable(setter):
        try:
            setter({"title": title} if title is not None else {})
        except Exception:
            pass


@component
def _stack_navigator_impl(screens: Any = None, initial_route: Optional[str] = None) -> Element:
    screen_map = _build_screen_map(screens)
    if not screen_map:
        return Element("View", {}, [])

    parent_nav = use_context(_NavigationContext)

    requested_route, requested_params = _read_host_initial_route(parent_nav)
    if requested_route is not None and requested_route in screen_map:
        first_route = requested_route
        first_params: Dict[str, Any] = dict(requested_params)
    else:
        first_route = initial_route or next(iter(screen_map))
        first_params = {}

    stack, set_stack = use_state(lambda: [_RouteEntry(first_route, first_params)])

    stack_ref = use_ref(None)
    stack_ref["current"] = stack

    handle = use_memo(
        lambda: _DeclarativeNavHandle(screen_map, lambda: stack_ref["current"], set_stack, parent=parent_nav), []
    )
    handle._screen_map = screen_map
    handle._parent = parent_nav

    current = stack[-1]
    screen_def = screen_map.get(current.name)
    if screen_def is None:
        return Element("Text", {"text": f"Unknown route: {current.name}"}, [])

    _apply_screen_options(parent_nav, screen_def)

    screen_el = screen_def.component()
    return Provider(_NavigationContext, handle, Provider(_FocusContext, True, screen_el))


def create_stack_navigator() -> Any:
    """Create a stack-based navigator.

    Stacks support push (`navigate(name, params=...)`) and pop
    (`go_back()`). The active screen is the top of the stack.

    Returns:
        An object exposing two static factories:

        - `Screen(name, *, component, options=None)`: define a screen.
        - `Navigator(*screens, initial_route=None, key=None)`: render
            the navigator with the given screens.

    Example:
        ```python
        import pythonnative as pn
        from pythonnative.navigation import (
            NavigationContainer, create_stack_navigator
        )

        Stack = create_stack_navigator()

        @pn.component
        def App():
            return NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Home", component=HomeScreen),
                    Stack.Screen("Detail", component=DetailScreen),
                    initial_route="Home",
                )
            )
        ```
    """

    class _StackNavigator:
        @staticmethod
        def Screen(name: str, *, component: Any, options: Optional[Dict[str, Any]] = None) -> "_ScreenDef":
            """Define a screen within this stack navigator.

            Args:
                name: Route name used by `navigate(name)`.
                component: A `@component` function rendered when this
                    screen is active.
                options: Optional per-screen settings.

            Returns:
                A `_ScreenDef` consumed by `Navigator(...)`.
            """
            return _ScreenDef(name, component, options)

        @staticmethod
        def Navigator(*screens: Any, initial_route: Optional[str] = None, key: Optional[str] = None) -> Element:
            """Render the stack navigator with the given screens.

            Args:
                *screens: One or more `Screen(...)` definitions.
                initial_route: Optional name of the route to mount
                    first. Defaults to the first screen passed.
                key: Stable identity for keyed reconciliation.

            Returns:
                An [`Element`][pythonnative.Element] that mounts the
                stack navigator.
            """
            return _stack_navigator_impl(screens=list(screens), initial_route=initial_route, key=key)

    return _StackNavigator()


# ======================================================================
# Tab navigator
# ======================================================================


@component
def _tab_navigator_impl(screens: Any = None, initial_route: Optional[str] = None) -> Element:
    screen_list = list(screens or [])
    screen_map = _build_screen_map(screen_list)
    if not screen_map:
        return Element("View", {}, [])

    parent_nav = use_context(_NavigationContext)

    first_route = initial_route or screen_list[0].name
    active_tab, set_active_tab = use_state(first_route)
    tab_params, set_tab_params = use_state(lambda: {first_route: {}})

    params_ref = use_ref(None)
    params_ref["current"] = tab_params

    def switch_tab(name: str, params: Optional[Dict[str, Any]] = None) -> None:
        set_active_tab(name)
        if params:
            set_tab_params(lambda p: {**p, name: params})

    def get_stack() -> List[_RouteEntry]:
        p = params_ref["current"] or {}
        return [_RouteEntry(active_tab, p.get(active_tab, {}))]

    handle = use_memo(lambda: _TabNavHandle(screen_map, get_stack, lambda _: None, switch_tab, parent=parent_nav), [])
    handle._screen_map = screen_map
    handle._switch_tab = switch_tab
    handle._parent = parent_nav

    screen_def = screen_map.get(active_tab)
    if screen_def is None:
        screen_def = screen_map[screen_list[0].name]

    tab_items: List[Dict[str, Any]] = []
    for s in screen_list:
        if isinstance(s, _ScreenDef):
            item: Dict[str, Any] = {"name": s.name, "title": s.options.get("title", s.name)}
            icon = s.options.get("tab_bar_icon")
            if icon is not None:
                item["icon"] = icon
            tab_items.append(item)

    def on_tab_select(name: str) -> None:
        switch_tab(name)

    tab_bar = Element(
        "TabBar",
        {"items": tab_items, "active_tab": active_tab, "on_tab_select": on_tab_select},
        [],
        key="__tab_bar__",
    )

    screen_el = screen_def.component()
    content = Provider(
        _NavigationContext,
        handle,
        Provider(_FocusContext, True, screen_el),
    )

    return Element(
        "View",
        {"flex_direction": "column", "flex": 1},
        [Element("View", {"flex": 1}, [content]), tab_bar],
    )


def create_tab_navigator() -> Any:
    """Create a tab-based navigator.

    Tab navigators render a tab bar and switch between sibling screens.
    Use `options={"title": "..."}` on a `Screen` to label the tab.

    Returns:
        An object exposing static `Screen(...)` and `Navigator(...)`
        factories analogous to
        [`create_stack_navigator`][pythonnative.create_stack_navigator].

    Example:
        ```python
        import pythonnative as pn
        from pythonnative.navigation import (
            NavigationContainer, create_tab_navigator
        )

        Tab = create_tab_navigator()

        @pn.component
        def App():
            return NavigationContainer(
                Tab.Navigator(
                    Tab.Screen("Home", component=HomeScreen, options={"title": "Home"}),
                    Tab.Screen("Settings", component=SettingsScreen),
                )
            )
        ```
    """

    class _TabNavigator:
        @staticmethod
        def Screen(name: str, *, component: Any, options: Optional[Dict[str, Any]] = None) -> "_ScreenDef":
            """Define a screen within this tab navigator.

            Args:
                name: Route name and default tab title.
                component: A `@component` function rendered when this
                    tab is active.
                options: Optional per-screen settings. Recognized keys:

                    - `title` (str): Tab label.
                    - `tab_bar_icon` (str | dict): Native system icon
                      identifier. A string is used on every platform; a
                      dict like `{"ios": "house.fill", "android":
                      "ic_menu_home"}` selects per platform. iOS values
                      are resolved via SF Symbols
                      (`UIImage.systemImageNamed_`); Android values are
                      resolved against `android.R.drawable.<name>`.
                      Names that don't resolve fall back to text-only.

            Returns:
                A `_ScreenDef` consumed by `Navigator(...)`.
            """
            return _ScreenDef(name, component, options)

        @staticmethod
        def Navigator(*screens: Any, initial_route: Optional[str] = None, key: Optional[str] = None) -> Element:
            """Render the tab navigator with the given screens.

            Args:
                *screens: One or more `Screen(...)` definitions.
                initial_route: Optional name of the tab to start on.
                key: Stable identity for keyed reconciliation.

            Returns:
                An [`Element`][pythonnative.Element] that mounts the
                tab navigator.
            """
            return _tab_navigator_impl(screens=list(screens), initial_route=initial_route, key=key)

    return _TabNavigator()


# ======================================================================
# Drawer navigator
# ======================================================================


@component
def _drawer_navigator_impl(screens: Any = None, initial_route: Optional[str] = None) -> Element:
    screen_list = list(screens or [])
    screen_map = _build_screen_map(screen_list)
    if not screen_map:
        return Element("View", {}, [])

    parent_nav = use_context(_NavigationContext)

    first_route = initial_route or screen_list[0].name
    active_screen, set_active_screen = use_state(first_route)
    drawer_open, set_drawer_open = use_state(False)
    screen_params, set_screen_params = use_state(lambda: {first_route: {}})

    params_ref = use_ref(None)
    params_ref["current"] = screen_params

    def switch_screen(name: str, params: Optional[Dict[str, Any]] = None) -> None:
        set_active_screen(name)
        if params:
            set_screen_params(lambda p: {**p, name: params})

    def get_stack() -> List[_RouteEntry]:
        p = params_ref["current"] or {}
        return [_RouteEntry(active_screen, p.get(active_screen, {}))]

    handle = use_memo(
        lambda: _DrawerNavHandle(
            screen_map,
            get_stack,
            lambda _: None,
            switch_screen,
            set_drawer_open,
            lambda: drawer_open,
            parent=parent_nav,
        ),
        [],
    )
    handle._screen_map = screen_map
    handle._switch_screen = switch_screen
    handle._set_drawer_open = set_drawer_open
    handle._get_drawer_open = lambda: drawer_open
    handle._parent = parent_nav

    screen_def = screen_map.get(active_screen)
    if screen_def is None:
        screen_def = screen_map[screen_list[0].name]

    screen_el = screen_def.component()
    content = Provider(
        _NavigationContext,
        handle,
        Provider(_FocusContext, True, screen_el),
    )

    children: List[Element] = [Element("View", {"flex": 1}, [content])]

    if drawer_open:
        menu_items: List[Element] = []
        for s in screen_list:
            if not isinstance(s, _ScreenDef):
                continue
            label = s.options.get("title", s.name)
            item_name = s.name

            def make_select(n: str) -> Callable[[], None]:
                def _select() -> None:
                    switch_screen(n)
                    set_drawer_open(False)

                return _select

            menu_items.append(
                Element("Button", {"title": label, "on_click": make_select(item_name)}, [], key=f"__drawer_{item_name}")
            )

        drawer_panel = Element(
            "View",
            {"background_color": "#FFFFFF", "width": 250},
            menu_items,
        )
        children.insert(0, drawer_panel)

    return Element("View", {"flex_direction": "row", "flex": 1}, children)


def create_drawer_navigator() -> Any:
    """Create a drawer-based navigator.

    Drawer navigators render a side panel for switching between sibling
    screens. The navigation handle returned by
    [`use_navigation`][pythonnative.use_navigation] inside a drawer
    navigator includes `open_drawer()`, `close_drawer()`, and
    `toggle_drawer()` methods in addition to the standard
    `navigate`/`go_back`/`reset` interface.

    Returns:
        An object exposing static `Screen(...)` and `Navigator(...)`
        factories analogous to
        [`create_stack_navigator`][pythonnative.create_stack_navigator].

    Example:
        ```python
        import pythonnative as pn
        from pythonnative.navigation import (
            NavigationContainer, create_drawer_navigator
        )

        Drawer = create_drawer_navigator()

        @pn.component
        def App():
            return NavigationContainer(
                Drawer.Navigator(
                    Drawer.Screen("Home", component=HomeScreen, options={"title": "Home"}),
                    Drawer.Screen("Settings", component=SettingsScreen),
                )
            )
        ```
    """

    class _DrawerNavigator:
        @staticmethod
        def Screen(name: str, *, component: Any, options: Optional[Dict[str, Any]] = None) -> "_ScreenDef":
            """Define a screen within this drawer navigator.

            Args:
                name: Route name and default drawer-menu label.
                component: A `@component` function rendered when this
                    screen is active.
                options: Optional per-screen settings (e.g.,
                    `{"title": "..."}`).

            Returns:
                A `_ScreenDef` consumed by `Navigator(...)`.
            """
            return _ScreenDef(name, component, options)

        @staticmethod
        def Navigator(*screens: Any, initial_route: Optional[str] = None, key: Optional[str] = None) -> Element:
            """Render the drawer navigator with the given screens.

            Args:
                *screens: One or more `Screen(...)` definitions.
                initial_route: Optional name of the screen to mount
                    first.
                key: Stable identity for keyed reconciliation.

            Returns:
                An [`Element`][pythonnative.Element] that mounts the
                drawer navigator.
            """
            return _drawer_navigator_impl(screens=list(screens), initial_route=initial_route, key=key)

    return _DrawerNavigator()


# ======================================================================
# NavigationContainer
# ======================================================================


def NavigationContainer(child: Element, *, key: Optional[str] = None) -> Element:
    """Root container for the navigation tree.

    Wraps the child navigator in a full-size view. All declarative
    navigators (stack, tab, drawer) should be nested inside a
    `NavigationContainer`.

    Args:
        child: The root navigator element (typically a `Stack.Navigator`,
            `Tab.Navigator`, or `Drawer.Navigator`).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"View"`.

    Example:
        ```python
        import pythonnative as pn
        from pythonnative.navigation import (
            NavigationContainer, create_stack_navigator
        )

        Stack = create_stack_navigator()

        @pn.component
        def App():
            return NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Home", component=HomeScreen),
                )
            )
        ```
    """
    return Element("View", {"flex": 1}, [child], key=key)


# ======================================================================
# Hooks
# ======================================================================


def use_route() -> Dict[str, Any]:
    """Return the current route's params dict.

    Convenience hook that reads from the navigation context. Equivalent
    to `use_navigation().get_params()` but tolerates the no-navigation
    case (returns `{}` instead of raising).

    Returns:
        The current route's `params` dict, or `{}` if no navigator is
        in scope.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def DetailScreen():
            params = pn.use_route()
            item_id = params.get("id")
            return pn.Text(f"Item {item_id}")
        ```
    """
    nav = use_context(_NavigationContext)
    if nav is None:
        return {}
    get_params = getattr(nav, "get_params", None)
    if get_params:
        return get_params()
    return {}


def use_focus_effect(effect: Callable, deps: Optional[list] = None) -> None:
    """Run `effect` only while the screen is focused.

    Like [`use_effect`][pythonnative.use_effect], but the callback runs
    only when the enclosing navigator marks this screen as the active
    one. Useful for starting subscriptions, refreshing data, or
    pausing animations on the inactive screen.

    The focus state combines two sources of truth:

    - The screen host's lifecycle (``on_resume`` / ``on_pause``), so
      pushing a sibling onto the navigation stack blurs this screen and
      popping back to it refocuses it.
    - The in-tree ``_FocusContext`` value, which lets declarative
      navigators (e.g. tabs, drawers) mark only the active subtree as
      focused even when both screens are part of the same host.

    Args:
        effect: A zero-arg callable invoked when focused. Optionally
            returns a cleanup callable.
        deps: Dependency list, or `None` to run on every render while
            focused.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def HomeScreen():
            pn.use_focus_effect(lambda: print("screen focused"), [])
            return pn.Text("Home")
        ```
    """
    context_focused = use_context(_FocusContext)

    nav = use_context(_NavigationContext)
    # Walk the navigator parent chain to find the screen host. Declarative
    # navigators (Stack/Tab/Drawer) wrap the host's ``NavigationHandle``
    # as ``_parent``; only the host-level handle has ``_host``.
    host = None
    cursor = nav
    while cursor is not None:
        candidate = getattr(cursor, "_host", None)
        if candidate is not None:
            host = candidate
            break
        cursor = getattr(cursor, "_parent", None)
    initial_host_focus = bool(getattr(host, "_is_focused", True)) if host is not None else True
    host_focused, set_host_focused = use_state(initial_host_focus)

    def subscribe_to_host_focus() -> Any:
        if host is None:
            return None
        subscribers = getattr(host, "_focus_subscribers", None)
        if subscribers is None:
            return None
        subscribers.append(set_host_focused)
        # The host may have changed focus state between the initial
        # ``use_state`` call and this effect running (e.g. mid-render
        # lifecycle event); resync once to avoid stale state.
        set_host_focused(bool(host._is_focused))

        def cleanup() -> None:
            try:
                subscribers.remove(set_host_focused)
            except ValueError:
                pass

        return cleanup

    use_effect(subscribe_to_host_focus, [])

    is_focused = context_focused and host_focused
    all_deps = [is_focused] + (list(deps) if deps is not None else [])

    def wrapped_effect() -> Any:
        if is_focused:
            return effect()
        return None

    use_effect(wrapped_effect, all_deps)
