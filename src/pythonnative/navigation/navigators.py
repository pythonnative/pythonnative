"""Stack, tab, and drawer navigators built on one shared core.

All three navigators are ordinary components. Each owns a
[`NavigationState`][pythonnative.navigation.NavigationState] in
``use_state``, wraps it in a
[`NavigatorCore`][pythonnative.navigation.handle.NavigatorCore], and
renders its screens under a
[`Navigation`][pythonnative.Navigation] provider. Only the *rendering*
differs:

- **Stack**: keeps every route mounted (hidden below the top one) so
  popping back restores the previous screen's state, and draws a
  header with a back button. When the stack is the root of a native
  host it pushes real native screens instead and lets the host draw
  the navigation bar.
- **Tabs**: keeps visited tabs alive and hidden (``lazy`` mounts them
  on first focus; ``unmount_on_blur`` opts out), and renders the
  native ``TabBar``.
- **Drawer**: like tabs, with a slide-in menu instead of a tab bar.

Inactive screens read ``False`` from
[`use_is_focused`][pythonnative.use_is_focused]; ``focus`` and ``blur``
listeners fire as the active route changes.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from ..component import component
from ..element import Element, Node
from ..hooks import use_back_handler, use_context, use_effect, use_memo, use_ref, use_state
from .container import ContainerContext
from .handle import FocusContext, Navigation, NavigationContext, NavigatorCore
from .host import HostContext
from .screen import ScreenDef, ScreenOptions, Unpack
from .state import NavigationState, Route

__all__ = [
    "DrawerNavigator",
    "StackNavigator",
    "TabNavigator",
    "create_drawer_navigator",
    "create_stack_navigator",
    "create_tab_navigator",
]

NavigatorKind = Literal["stack", "tab", "drawer"]

_HEADER_HEIGHT = 44.0
_DRAWER_WIDTH = 280.0


# ======================================================================
# Shared core hook
# ======================================================================


def _use_navigator(
    kind: NavigatorKind,
    screens: Sequence[ScreenDef],
    initial_route: Optional[str],
) -> Tuple[NavigatorCore, NavigationState, bool]:
    """Create (once) and refresh the navigator core for the calling component.

    Returns ``(core, state, parent_focused)``.
    """
    screen_map: Dict[str, ScreenDef] = {s.name: s for s in screens}
    parent = use_context(NavigationContext)
    host = use_context(HostContext)
    parent_focused = use_context(FocusContext)
    container = use_context(ContainerContext) if parent is None else None
    is_native_root = kind == "stack" and parent is None and host is not None
    first = initial_route if initial_route in screen_map else next(iter(screen_map))

    def default_state() -> NavigationState:
        if kind == "stack":
            return NavigationState([Route(first, screen_map[first].initial_params)])
        routes = [Route(s.name, s.initial_params) for s in screens]
        return NavigationState(routes, [s.name for s in screens].index(first))

    def initial_state() -> NavigationState:
        if is_native_root:
            serialized = host.initial_navigation_state()
            if serialized:
                try:
                    restored = NavigationState.from_dict(serialized)
                except Exception:
                    restored = None
                if restored is not None and all(r.name in screen_map for r in restored.routes):
                    return restored
        seed = parent.route.state if parent is not None else (container.initial_state if container else None)
        if seed is not None:
            seeded = _apply_seed(kind, screen_map, default_state(), seed)
            if seeded is not None:
                return seeded
        return default_state()

    state, set_state = use_state(initial_state)
    _version, set_version = use_state(0)
    core: NavigatorCore = use_memo(
        lambda: NavigatorCore(
            kind,
            screen_map,
            state,
            set_state,
            parent,
            host,
            request_render=lambda: set_version(lambda v: v + 1),
        ),
        [],
    )
    core.update(screen_map, state, set_state, parent, host)
    _use_focus_events(core, state, parent_focused)
    _use_seed_updates(core, parent)
    _use_container(core, state, container)
    return core, state, parent_focused


def _apply_seed(
    kind: NavigatorKind,
    screen_map: Dict[str, ScreenDef],
    base: NavigationState,
    seed: NavigationState,
) -> Optional[NavigationState]:
    """Merge a seed state (deep link, ``navigate(screen=...)``) into ``base``.

    Stacks keep their initial route underneath so back works; tabs and
    drawers switch to the seeded route and merge its params. Unknown
    route names make the seed invalid (``None``).
    """
    if any(r.name not in screen_map for r in seed.routes):
        return None
    if kind == "stack":
        routes = list(seed.routes)
        if routes[0].name != base.routes[0].name:
            routes.insert(0, base.routes[0])
        return NavigationState(routes)
    target = seed.current
    return base.jump_to(target.name, target.params, target.state)


def _use_seed_updates(core: NavigatorCore, parent: Optional[Navigation]) -> None:
    """Follow later ``navigate("Nested", screen=...)`` calls made on the parent."""
    seed = parent.route.state if parent is not None else None
    applied: Any = use_ref(seed)

    def run() -> None:
        if seed is None or seed is applied.current:
            return
        applied.current = seed
        target = seed.current
        if target.name in core.screens:
            core.navigate(target.name, target.params, target.state)

    use_effect(run, [seed])


def _use_container(core: NavigatorCore, state: NavigationState, container: Any) -> None:
    """Attach a root navigator to its container (deep links, ``on_state_change``)."""

    def attach() -> Any:
        return container.attach_root(core) if container is not None else None

    use_effect(attach, [container])

    def report() -> None:
        if container is not None and container.on_state_change is not None:
            container.on_state_change(state)

    use_effect(report, [state])


def _use_focus_events(core: NavigatorCore, state: NavigationState, parent_focused: bool) -> None:
    """Emit ``blur`` / ``focus`` / ``state`` as the active route or focus changes."""
    last: Any = use_ref(None)

    def run() -> None:
        active: Optional[Route] = state.current if parent_focused else None
        prev: Optional[Route] = last.current
        if (prev.key if prev else None) == (active.key if active else None):
            return
        if prev is not None:
            core.emit(prev, "blur")
        if active is not None:
            core.emit(active, "focus")
        last.current = active

    use_effect(run, [state.current.key, parent_focused])

    def emit_state() -> None:
        core.emit(state.current, "state", {"state": state})

    use_effect(emit_state, [state])


def _use_host_options(core: NavigatorCore, state: NavigationState) -> None:
    """Push the active route's header options to the native host (root stacks only)."""
    options = core.options_for(state.current) if core.is_native_root else None
    signature = _options_signature(options)

    def apply() -> None:
        if options is None or core.host is None:
            return
        try:
            core.host.set_screen_options(options)
        except Exception:
            pass

    use_effect(apply, [signature, state.current.key])


def _options_signature(options: Optional[Dict[str, Any]]) -> Any:
    if options is None:
        return None
    out = []
    for key in sorted(options):
        value = options[key]
        out.append((key, value if isinstance(value, (str, int, float, bool, type(None))) else id(value)))
    return tuple(out)


def _screen_element(
    core: NavigatorCore,
    route: Route,
    *,
    active: bool,
    parent_focused: bool,
) -> Element:
    """Render ``route``'s component under its navigation and focus providers."""
    screen = core.screens.get(route.name)
    if screen is None:
        from ..components import Text

        body: Node = Text(f"Unknown route: {route.name}")
    else:
        body = screen.component()
    handle = core.handle_for(route)
    return NavigationContext.Provider(handle, FocusContext.Provider(parent_focused and active, body), key=route.key)


def _hidden_style(active: bool) -> Dict[str, Any]:
    return {"flex": 1, "display": "flex" if active else "none"}


# ======================================================================
# Stack
# ======================================================================


@component
def _StackHeader(*, core: NavigatorCore, route: Route, options: Dict[str, Any]) -> Optional[Element]:
    from ..components import Pressable, Text, View

    if options.get("header_shown", True) is False:
        return None
    handle = core.handle_for(route)
    style = {
        "height": _HEADER_HEIGHT,
        "flex_direction": "row",
        "align_items": "center",
        "padding_horizontal": 8,
        "background_color": "#F8F8F8",
        "border_bottom_width": 0.5,
        "border_color": "#C7C7CC",
        **(options.get("header_style") or {}),
    }
    tint = options.get("header_tint_color", "#007AFF")
    title_style = {
        "font_size": 17,
        "bold": True,
        "flex": 1,
        "text_align": "center",
        **(options.get("header_title_style") or {}),
    }

    def slot(value: Any) -> Optional[Element]:
        if value is None:
            return None
        return value() if callable(value) and not isinstance(value, Element) else value

    left = slot(options.get("header_left"))
    if left is None and handle.can_go_back() and options.get("header_back_visible", True):
        back_title = options.get("header_back_title") or "Back"
        left = Pressable(
            Text(f"\u2039 {back_title}", style={"color": tint, "font_size": 17}),
            on_press=handle.go_back,
            accessibility_label="Back",
        )
    right = slot(options.get("header_right"))
    return View(
        View(left, style={"min_width": 60, "align_items": "flex_start"}),
        Text(str(options.get("title", route.name)), style=title_style),
        View(right, style={"min_width": 60, "align_items": "flex_end"}),
        style=style,
    )


@component
def _StackNavigatorImpl(*, screens: Tuple[ScreenDef, ...], initial_route: Optional[str] = None) -> Element:
    from ..components import View

    if not screens:
        return View(style={"flex": 1})
    core, state, parent_focused = _use_navigator("stack", screens, initial_route)
    _use_host_options(core, state)

    def on_back() -> bool:
        if core.is_native_root:
            evt = core.emit(state.current, "before_remove", {"action": "back"})
            return evt.default_prevented
        if len(state) > 1:
            return core.pop(1, source="back")
        return False

    use_back_handler(on_back)

    current = state.current
    if core.is_native_root:
        # Other routes live on other native screens; only ours renders here.
        return View(_screen_element(core, current, active=True, parent_focused=parent_focused), style={"flex": 1})

    layers: List[Element] = []
    for route in state.routes:
        active = route is current
        header = _StackHeader(core=core, route=route, options=core.options_for(route))
        layers.append(
            View(
                header,
                View(_screen_element(core, route, active=active, parent_focused=parent_focused), style={"flex": 1}),
                style=_hidden_style(active),
                key=route.key,
            )
        )
    return View(*layers, style={"flex": 1})


class StackNavigator:
    """Factory returned by [`create_stack_navigator`][pythonnative.create_stack_navigator]."""

    __slots__ = ()

    @staticmethod
    def Screen(
        name: str,
        component: Callable[[], Any],
        *,
        options: Any = None,
        initial_params: Optional[Dict[str, Any]] = None,
        **option_kwargs: Unpack[ScreenOptions],
    ) -> ScreenDef:
        """Define a screen. ``options`` may be a dict or ``(route) -> dict``; keywords merge on top."""
        return ScreenDef(name, component, options=options, initial_params=initial_params, **option_kwargs)

    @staticmethod
    def Navigator(*screens: ScreenDef, initial_route: Optional[str] = None, key: Optional[str] = None) -> Element:
        """Render the stack with the given screens (the first, or ``initial_route``, shows first)."""
        return _StackNavigatorImpl(screens=tuple(screens), initial_route=initial_route).with_key(key)


def create_stack_navigator() -> StackNavigator:
    """Create a stack navigator: push and pop screens with history.

    At the root of a native host the stack pushes real native screens
    (``UINavigationController`` on iOS, fragments on Android), so users
    get system transitions and swipe-back for free. Nested stacks are
    drawn in Python with their own header.

    Example:
        ```python
        import pythonnative as pn

        Stack = pn.create_stack_navigator()

        @pn.component
        def App():
            return pn.NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Home", HomeScreen, title="Home"),
                    Stack.Screen("Detail", DetailScreen, title="Detail"),
                )
            )
        ```
    """
    return StackNavigator()


# ======================================================================
# Keep-alive helpers shared by tabs and drawers
# ======================================================================


def _use_visited(state: NavigationState) -> Any:
    """Track which route keys have been active at least once (for ``lazy``)."""
    visited: Any = use_ref(None)
    if visited.current is None:
        visited.current = set()
    visited.current.add(state.current.key)
    live = {r.key for r in state.routes}
    visited.current.intersection_update(live)
    return visited.current


def _render_keep_alive(
    core: NavigatorCore, state: NavigationState, parent_focused: bool, visited: Any
) -> List[Element]:
    from ..components import View

    out: List[Element] = []
    for route in state.routes:
        active = route is state.current
        options = core.options_for(route)
        if not active:
            if options.get("unmount_on_blur", False):
                continue
            if options.get("lazy", True) and route.key not in visited:
                continue
        out.append(
            View(
                _screen_element(core, route, active=active, parent_focused=parent_focused),
                style=_hidden_style(active),
                key=route.key,
            )
        )
    return out


# ======================================================================
# Tabs
# ======================================================================


@component
def _TabNavigatorImpl(*, screens: Tuple[ScreenDef, ...], initial_route: Optional[str] = None) -> Element:
    from ..components import View

    if not screens:
        return View(style={"flex": 1})
    core, state, parent_focused = _use_navigator("tab", screens, initial_route)
    visited = _use_visited(state)

    items: List[Dict[str, Any]] = []
    for route in state.routes:
        options = core.options_for(route)
        item: Dict[str, Any] = {
            "name": route.name,
            "title": options.get("tab_bar_label") or options.get("title", route.name),
        }
        icon = options.get("tab_bar_icon")
        if icon is not None:
            item["icon"] = icon
        badge = options.get("tab_bar_badge")
        if badge is not None:
            item["badge"] = str(badge)
        items.append(item)

    def on_tab_select(name: str) -> None:
        core.navigate(name, {})

    tab_bar = Element(
        "TabBar",
        {"items": items, "active_tab": state.current.name, "on_tab_select": on_tab_select},
        [],
        key="__tab_bar__",
    )
    return View(
        View(*_render_keep_alive(core, state, parent_focused, visited), style={"flex": 1}),
        tab_bar,
        style={"flex": 1, "flex_direction": "column"},
    )


class TabNavigator:
    """Factory returned by [`create_tab_navigator`][pythonnative.create_tab_navigator]."""

    __slots__ = ()

    @staticmethod
    def Screen(
        name: str,
        component: Callable[[], Any],
        *,
        options: Any = None,
        initial_params: Optional[Dict[str, Any]] = None,
        **option_kwargs: Unpack[ScreenOptions],
    ) -> ScreenDef:
        """Define a tab. ``options`` may be a dict or ``(route) -> dict``; keywords merge on top."""
        return ScreenDef(name, component, options=options, initial_params=initial_params, **option_kwargs)

    @staticmethod
    def Navigator(*screens: ScreenDef, initial_route: Optional[str] = None, key: Optional[str] = None) -> Element:
        """Render the tab bar with the given screens (the first, or ``initial_route``, is selected first)."""
        return _TabNavigatorImpl(screens=tuple(screens), initial_route=initial_route).with_key(key)


def create_tab_navigator() -> TabNavigator:
    """Create a tab navigator with a native tab bar.

    Tabs stay mounted once visited (hidden while inactive) so switching
    back restores scroll position and state. Use ``lazy=False`` on a
    screen to mount it eagerly, or ``unmount_on_blur=True`` to tear it
    down when it loses focus.

    Example:
        ```python
        Tab = pn.create_tab_navigator()

        Tab.Navigator(
            Tab.Screen("Home", HomeScreen, title="Home", tab_bar_icon="house.fill"),
            Tab.Screen("Settings", SettingsScreen, title="Settings"),
        )
        ```
    """
    return TabNavigator()


# ======================================================================
# Drawer
# ======================================================================


@component
def _DrawerNavigatorImpl(
    *,
    screens: Tuple[ScreenDef, ...],
    initial_route: Optional[str] = None,
    drawer_width: float = _DRAWER_WIDTH,
) -> Element:
    from ..components import Pressable, Text, View

    if not screens:
        return View(style={"flex": 1})
    core, state, parent_focused = _use_navigator("drawer", screens, initial_route)
    visited = _use_visited(state)
    drawer_open, set_drawer_open = use_state(False)
    core.drawer_open = drawer_open
    core._set_drawer_open = set_drawer_open

    def on_back() -> bool:
        if drawer_open:
            set_drawer_open(False)
            return True
        return False

    use_back_handler(on_back)

    content = View(*_render_keep_alive(core, state, parent_focused, visited), style={"flex": 1})
    if not drawer_open:
        return View(content, style={"flex": 1})

    def select(name: str) -> Callable[[], None]:
        def _select() -> None:
            core.navigate(name, {})
            set_drawer_open(False)

        return _select

    rows: List[Element] = []
    for route in state.routes:
        options = core.options_for(route)
        active = route is state.current
        rows.append(
            Pressable(
                Text(
                    str(options.get("title", route.name)),
                    style={"font_size": 16, "color": "#007AFF" if active else "#1C1C1E", "bold": active},
                ),
                on_press=select(route.name),
                style={
                    "padding_vertical": 14,
                    "padding_horizontal": 20,
                    "background_color": "#EEF3FF" if active else "#00000000",
                },
                key=f"__drawer_{route.key}",
            )
        )
    panel = View(
        *rows,
        style={
            "width": drawer_width,
            "background_color": "#FFFFFF",
            "padding_top": 24,
            "border_right_width": 0.5,
            "border_color": "#C7C7CC",
        },
    )
    scrim = Pressable(on_press=lambda: set_drawer_open(False), style={"flex": 1, "background_color": "#00000040"})
    return View(
        content,
        View(
            panel,
            scrim,
            style={"position": "absolute", "top": 0, "left": 0, "right": 0, "bottom": 0, "flex_direction": "row"},
        ),
        style={"flex": 1},
    )


class DrawerNavigator:
    """Factory returned by [`create_drawer_navigator`][pythonnative.create_drawer_navigator]."""

    __slots__ = ()

    @staticmethod
    def Screen(
        name: str,
        component: Callable[[], Any],
        *,
        options: Any = None,
        initial_params: Optional[Dict[str, Any]] = None,
        **option_kwargs: Unpack[ScreenOptions],
    ) -> ScreenDef:
        """Define a drawer screen. ``options`` may be a dict or ``(route) -> dict``; keywords merge on top."""
        return ScreenDef(name, component, options=options, initial_params=initial_params, **option_kwargs)

    @staticmethod
    def Navigator(
        *screens: ScreenDef,
        initial_route: Optional[str] = None,
        drawer_width: float = _DRAWER_WIDTH,
        key: Optional[str] = None,
    ) -> Element:
        """Render the drawer with the given screens (the first, or ``initial_route``, shows first)."""
        return _DrawerNavigatorImpl(
            screens=tuple(screens), initial_route=initial_route, drawer_width=drawer_width
        ).with_key(key)


def create_drawer_navigator() -> DrawerNavigator:
    """Create a drawer navigator: sibling screens behind a slide-in menu.

    The handle returned by [`use_navigation`][pythonnative.use_navigation]
    inside a drawer screen is a
    [`DrawerNavigation`][pythonnative.navigation.DrawerNavigation] with
    ``open_drawer()``, ``close_drawer()``, and ``toggle_drawer()``.
    """
    return DrawerNavigator()
