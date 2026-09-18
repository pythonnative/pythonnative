"""Stack, tab, and drawer navigators built on one shared core.

All three navigators are ordinary components. Each owns a
[`NavigationState`][pythonnative.navigation.NavigationState] in
``use_state``, wraps it in a
[`NavigatorCore`][pythonnative.navigation.handle.NavigatorCore], and
renders its screens under a
[`Navigation`][pythonnative.Navigation] provider. Only the *rendering*
differs:

- **Stack**: keeps every route mounted (hidden below the top one) so
  popping back restores the previous screen's state. When a native host
  is present, every stack, nested or not, renders a native
  ``ScreenStack`` (``UINavigationController`` on iOS, fragments on
  Android) that draws the navigation bar and runs the platform
  transitions and back gesture. Without a host (tests, the browser
  preview's headless mode) the stack draws a themed header with a back
  button itself.
- **Tabs**: keeps visited tabs alive and hidden (``lazy`` mounts them
  on first focus; ``unmount_on_blur`` opts out; ``freeze_on_blur``
  stops re-rendering them while hidden), and renders the native
  ``TabBar`` styled by ``tab_bar_style`` and the navigation theme.
- **Drawer**: like tabs, with a Python-drawn, themed slide-in menu
  instead of a tab bar.

Every navigator accepts ``screen_options`` (a dict or ``(route) ->
dict``) applied to all of its screens, and ``Group(...)`` adds a layer
for a subset of them. Inactive screens read ``False`` from
[`use_is_focused`][pythonnative.use_is_focused]; ``focus`` and ``blur``
listeners fire as the active route changes.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

from ..component import component, memo
from ..element import Element, Node
from ..hooks import use_back_handler, use_context, use_effect, use_memo, use_ref, use_state
from ..icons import tab_icon_spec
from ..style import Style, StyleProp
from .container import ContainerContext
from .handle import FocusContext, Navigation, NavigationContext, NavigatorCore, provide
from .host import HostContext
from .screen import (
    PYTHON_ONLY_OPTIONS,
    OptionsLike,
    ScreenDef,
    ScreenGroup,
    ScreenOptions,
    TabBarStyle,
    Unpack,
    flatten_screens,
)
from .state import NavigationState, Route
from .theme import NavigationTheme, use_navigation_theme

__all__ = [
    "DrawerNavigator",
    "StackNavigator",
    "TabNavigator",
    "create_drawer_navigator",
    "create_stack_navigator",
    "create_tab_navigator",
]

NavigatorKind = Literal["stack", "tab", "drawer"]
NavigatorItem = Union[ScreenDef, ScreenGroup]

_HEADER_HEIGHT = 44.0
_DRAWER_WIDTH = 280.0
_TRANSPARENT = "#00000000"


# ======================================================================
# Shared core hook
# ======================================================================


def _use_navigator(
    kind: NavigatorKind,
    screens: Sequence[ScreenDef],
    initial_route: Optional[str],
    screen_options: OptionsLike = None,
    group_options: Optional[Dict[str, OptionsLike]] = None,
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
            screen_options=screen_options,
            group_options=group_options,
        ),
        [],
    )
    core.update(screen_map, state, set_state, parent, host, screen_options=screen_options, group_options=group_options)
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
    """Attach a root navigator to its container (deep links, ``on_state_change``, the ``NavigationRef``)."""

    def attach() -> Any:
        return container.attach_root(core) if container is not None else None

    use_effect(attach, [container])

    def report() -> None:
        if container is not None and container.on_state_change is not None:
            container.on_state_change(state)

    use_effect(report, [state])

    def cache() -> None:
        publish = getattr(core.host, "cache_navigation_state", None)
        if core.is_native_root and publish is not None:
            publish(state.to_dict())

    use_effect(cache, [state])


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


# ======================================================================
# Screen rendering shared by every navigator
# ======================================================================


def _screen_body(core: NavigatorCore, route: Route, theme: NavigationTheme) -> Node:
    """The element for ``route``'s component, or a themed fallback for an unknown route."""
    screen = core.screens.get(route.name)
    if screen is None:
        from ..components import Text

        return Text(f"Unknown route: {route.name}", style={"color": theme.colors.text})
    return screen.component()


@memo(equal=lambda old, new: old.get("body") is new.get("body"))
@component
def _FrozenScreen(*, body: Any) -> Any:
    """Memo wrapper: re-renders only when handed a new ``body`` element object (see ``freeze_on_blur``)."""
    return body


def _screen_element(
    core: NavigatorCore,
    route: Route,
    body: Node,
    *,
    active: bool,
    parent_focused: bool,
    header_options: Optional[Dict[str, Any]] = None,
) -> Element:
    """Render ``body`` under ``route``'s navigation and focus providers."""
    handle = core.handle_for(route)
    children: List[Node] = [body]
    if header_options is not None:
        for side in ("left", "right"):
            value = header_options.get(f"header_{side}")
            if value is not None:
                children.append(_NativeHeaderSlot(value=value, side=side).with_key(f"header-{side}"))
    return provide(
        NavigationContext, handle, provide(FocusContext, parent_focused and active, *children), key=route.key
    )


@component
def _NativeHeaderSlot(*, value: Any, side: str) -> Element:
    body = value() if callable(value) and not isinstance(value, Element) else value
    return Element("View", {"_pn_header_slot": side, "height": 44, "justify_content": "center"}, [body])


def _native_screen_props(options: Dict[str, Any], theme: NavigationTheme) -> Dict[str, Any]:
    """Wire props for a native ``Screen``: the options native reads, with theme colors filled in as defaults."""
    props = {key: value for key, value in options.items() if key not in PYTHON_ONLY_OPTIONS}
    props.setdefault("header_tint_color", theme.colors.primary)
    header_style = dict(options.get("header_style") or {})
    header_style.setdefault("background_color", theme.colors.card)
    props["header_style"] = header_style
    title_style = dict(options.get("header_title_style") or {})
    title_style.setdefault("color", theme.colors.text)
    props["header_title_style"] = title_style
    return props


def _native_screen(
    core: NavigatorCore, route: Route, active: bool, parent_focused: bool, theme: NavigationTheme
) -> Element:
    options = core.options_for(route)
    # ``guarded`` is an internal wire prop, recomputed every render: while
    # the route has a ``before_remove`` listener, iOS refuses the pop or
    # dismiss synchronously and reports ``on_native_back`` for Python to
    # decide, instead of animating the screen out and back in.
    guarded = core.has_listeners(route.key, "before_remove")
    return Element(
        "Screen",
        {
            "flex": 1,
            "active": active,
            "route_key": route.key,
            "guarded": guarded,
            **_native_screen_props(options, theme),
        },
        [
            _screen_element(
                core,
                route,
                _screen_body(core, route, theme),
                active=active,
                parent_focused=parent_focused,
                header_options=options,
            )
        ],
        key=route.key,
    )


def _hidden_style(active: bool) -> Style:
    return {"flex": 1, "display": "flex" if active else "none"}


# ======================================================================
# Stack
# ======================================================================


@component
def _StackHeader(
    *, core: NavigatorCore, route: Route, options: Dict[str, Any], theme: NavigationTheme
) -> Optional[Element]:
    from ..components import Pressable, Text, View

    if options.get("header_shown", True) is False:
        return None
    handle = core.handle_for(route)
    style: StyleProp = [
        {
            "height": _HEADER_HEIGHT,
            "flex_direction": "row",
            "align_items": "center",
            "padding_horizontal": 8,
            "background_color": theme.colors.card,
            "border_bottom_width": 0.5,
            "border_color": theme.colors.border,
        },
        options.get("header_style"),
    ]
    tint = options.get("header_tint_color", theme.colors.primary)
    title_style: StyleProp = [
        {
            "font_size": 17,
            "bold": True,
            "flex": 1,
            "text_align": "center",
            "color": theme.colors.text,
        },
        options.get("header_title_style"),
    ]

    def slot(value: Any) -> Optional[Element]:
        if value is None:
            return None
        return value() if callable(value) and not isinstance(value, Element) else value

    left = slot(options.get("header_left"))
    if left is None and handle.can_go_back() and options.get("header_back_visible", True):
        back_title = options.get("header_back_title") or "Back"
        left = Pressable(
            Text(f"‹ {back_title}", style={"color": tint, "font_size": 17}),
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
def _StackNavigatorImpl(
    *,
    screens: Tuple[ScreenDef, ...],
    initial_route: Optional[str] = None,
    screen_options: OptionsLike = None,
    group_options: Optional[Dict[str, OptionsLike]] = None,
) -> Element:
    from ..components import View

    theme = use_navigation_theme()
    if not screens:
        return View(style={"flex": 1})
    core, state, parent_focused = _use_navigator("stack", screens, initial_route, screen_options, group_options)

    def on_back() -> bool:
        if parent_focused and len(state) > 1:
            return core.pop(1, source="back")
        return False

    use_back_handler(on_back)

    current = state.current
    stack_ref = use_ref(None)
    if core.host is not None:

        def native_back(count: int = 1) -> None:
            # Guarded screens reach here before UIKit pops, so a veto costs
            # nothing. For the unguarded race (a listener added after the
            # gesture started) the native container already popped; if
            # Python's state didn't follow (a veto, or nothing to pop), tell
            # it to restore the stack to match Python.
            before = core.state
            core.pop(count, source="back")
            handle = stack_ref.current
            if core.state is before and handle is not None:
                handle.command("restore_stack")

        return Element(
            "ScreenStack",
            {"flex": 1, "on_native_back": native_back, "ref": stack_ref},
            [_native_screen(core, route, route is current, parent_focused, theme) for route in state.routes],
        )

    layers: List[Element] = []
    for route in state.routes:
        active = route is current
        header = _StackHeader(core=core, route=route, options=core.options_for(route), theme=theme)
        body = _screen_element(
            core, route, _screen_body(core, route, theme), active=active, parent_focused=parent_focused
        )
        layers.append(View(header, View(body, style={"flex": 1}), style=_hidden_style(active), key=route.key))
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
    def Group(*screens: ScreenDef, screen_options: OptionsLike = None) -> ScreenGroup:
        """Group screens that share ``screen_options`` (layered between the navigator's and each screen's own)."""
        return ScreenGroup(screens, screen_options)

    @staticmethod
    def Navigator(
        *screens: NavigatorItem,
        screen_options: OptionsLike = None,
        initial_route: Optional[str] = None,
        key: Optional[str] = None,
    ) -> Element:
        """Render the stack with the given screens and groups (the first screen, or ``initial_route``, shows first).

        ``screen_options`` (a dict or ``(route) -> dict``) applies to every
        screen; group and screen options layer on top, then ``set_options``.
        """
        flat, groups = flatten_screens(screens)
        return _StackNavigatorImpl(
            screens=flat, initial_route=initial_route, screen_options=screen_options, group_options=groups
        ).with_key(key)


def create_stack_navigator() -> StackNavigator:
    """Create a stack navigator: push and pop screens with history.

    Stacks use native screen containers at every nesting level on mobile:
    ``UINavigationController`` on iOS and fragments on Android draw the
    navigation bar and run the transitions. Without a native host (tests,
    headless rendering) the stack draws a themed header itself.

    Example:
        ```python
        import pythonnative as pn

        Stack = pn.create_stack_navigator()

        @pn.component
        def App():
            return pn.NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Home", HomeScreen, title="Home"),
                    Stack.Group(
                        Stack.Screen("Compose", ComposeScreen),
                        screen_options={"presentation": "modal"},
                    ),
                    screen_options=lambda route: {"title": route.name.title()},
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


def _use_frozen(state: NavigationState) -> Dict[str, Node]:
    """Per-navigator cache of the last body element of each blurred ``freeze_on_blur`` screen."""
    frozen: Any = use_ref(None)
    if frozen.current is None:
        frozen.current = {}
    live = {r.key for r in state.routes}
    for key in list(frozen.current):
        if key not in live:
            del frozen.current[key]
    return frozen.current


def _render_keep_alive(
    core: NavigatorCore,
    state: NavigationState,
    parent_focused: bool,
    visited: Any,
    frozen: Dict[str, Node],
    theme: NavigationTheme,
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
        body: Node
        if options.get("freeze_on_blur", False):
            if active:
                frozen.pop(route.key, None)
                inner: Node = _screen_body(core, route, theme)
            else:
                inner = frozen.get(route.key)
                if inner is None:
                    inner = _screen_body(core, route, theme)
                    frozen[route.key] = inner
            body = _FrozenScreen(body=inner)
        else:
            body = _screen_body(core, route, theme)
        out.append(
            View(
                _screen_element(core, route, body, active=active, parent_focused=parent_focused),
                style=_hidden_style(active),
                key=route.key,
            )
        )
    return out


# ======================================================================
# Tabs
# ======================================================================


def _tab_bar_props(style: Optional[TabBarStyle], theme: NavigationTheme) -> Dict[str, Any]:
    """Translate ``TabBarStyle`` plus theme defaults into the native ``TabBar`` props."""
    resolved: Dict[str, Any] = dict(style or {})
    props: Dict[str, Any] = {
        "tint_color": resolved.get("active_tint_color", theme.colors.primary),
        "background_color": resolved.get("background_color", theme.colors.card),
    }
    if "inactive_tint_color" in resolved:
        props["inactive_tint_color"] = resolved["inactive_tint_color"]
    if "translucent" in resolved:
        props["translucent"] = bool(resolved["translucent"])
    if "show_labels" in resolved:
        props["shows_labels"] = bool(resolved["show_labels"])
    return props


@component
def _TabNavigatorImpl(
    *,
    screens: Tuple[ScreenDef, ...],
    initial_route: Optional[str] = None,
    screen_options: OptionsLike = None,
    group_options: Optional[Dict[str, OptionsLike]] = None,
    tab_bar_style: Optional[TabBarStyle] = None,
) -> Element:
    from ..components import View

    theme = use_navigation_theme()
    if not screens:
        return View(style={"flex": 1})
    core, state, parent_focused = _use_navigator("tab", screens, initial_route, screen_options, group_options)
    visited = _use_visited(state)
    frozen = _use_frozen(state)

    items: List[Dict[str, Any]] = []
    for route in state.routes:
        options = core.options_for(route)
        item: Dict[str, Any] = {
            "name": route.name,
            "title": options.get("tab_bar_label") or options.get("title", route.name),
        }
        icon = options.get("tab_bar_icon")
        if icon is not None:
            item["icon"] = tab_icon_spec(icon)
        badge = options.get("tab_bar_badge")
        if badge is not None:
            item["badge"] = str(badge)
        items.append(item)

    def on_tab_select(name: str) -> None:
        core.navigate(name, {})

    children: List[Element] = [
        View(*_render_keep_alive(core, state, parent_focused, visited, frozen, theme), style={"flex": 1})
    ]
    if core.options_for(state.current).get("tab_bar_visible", True) is not False:
        children.append(
            Element(
                "TabBar",
                {
                    "items": items,
                    "active_tab": state.current.name,
                    "on_tab_select": on_tab_select,
                    **_tab_bar_props(tab_bar_style, theme),
                },
                [],
                key="__tab_bar__",
            )
        )
    return View(*children, style={"flex": 1, "flex_direction": "column"})


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
    def Group(*screens: ScreenDef, screen_options: OptionsLike = None) -> ScreenGroup:
        """Group tabs that share ``screen_options`` (layered between the navigator's and each tab's own)."""
        return ScreenGroup(screens, screen_options)

    @staticmethod
    def Navigator(
        *screens: NavigatorItem,
        screen_options: OptionsLike = None,
        initial_route: Optional[str] = None,
        tab_bar_style: Optional[TabBarStyle] = None,
        key: Optional[str] = None,
    ) -> Element:
        """Render the tab bar with the given tabs and groups (the first, or ``initial_route``, is selected first).

        ``tab_bar_style`` is a [`TabBarStyle`][pythonnative.TabBarStyle];
        unset keys fall back to the navigation theme.
        """
        flat, groups = flatten_screens(screens)
        return _TabNavigatorImpl(
            screens=flat,
            initial_route=initial_route,
            screen_options=screen_options,
            group_options=groups,
            tab_bar_style=tab_bar_style,
        ).with_key(key)


def create_tab_navigator() -> TabNavigator:
    """Create a tab navigator with a native tab bar.

    Tabs stay mounted once visited (hidden while inactive) so switching
    back restores scroll position and state. Use ``lazy=False`` on a
    screen to mount it eagerly, ``unmount_on_blur=True`` to tear it
    down when it loses focus, and ``freeze_on_blur=True`` to stop
    re-rendering it while hidden. ``tab_bar_visible=False`` hides the
    bar while that tab is focused.

    Example:
        ```python
        Tab = pn.create_tab_navigator()

        Tab.Navigator(
            Tab.Screen("Home", HomeScreen, title="Home", tab_bar_icon="house"),
            Tab.Screen("Settings", SettingsScreen, title="Settings"),
            tab_bar_style={"active_tint_color": "#FF2D55", "show_labels": False},
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
    screen_options: OptionsLike = None,
    group_options: Optional[Dict[str, OptionsLike]] = None,
    drawer_width: float = _DRAWER_WIDTH,
) -> Element:
    from ..components import Pressable, Text, View

    theme = use_navigation_theme()
    if not screens:
        return View(style={"flex": 1})
    core, state, parent_focused = _use_navigator("drawer", screens, initial_route, screen_options, group_options)
    visited = _use_visited(state)
    frozen = _use_frozen(state)
    drawer_open, set_drawer_open = use_state(False)
    core.drawer_open = drawer_open
    core._set_drawer_open = set_drawer_open

    def on_back() -> bool:
        if drawer_open:
            set_drawer_open(False)
            return True
        return False

    use_back_handler(on_back)

    content = View(*_render_keep_alive(core, state, parent_focused, visited, frozen, theme), style={"flex": 1})
    if not drawer_open:
        return View(content, style={"flex": 1})

    def select(name: str) -> Callable[[], None]:
        def _select() -> None:
            core.navigate(name, {})
            set_drawer_open(False)

        return _select

    colors = theme.colors
    rows: List[Element] = []
    for route in state.routes:
        options = core.options_for(route)
        active = route is state.current
        rows.append(
            Pressable(
                Text(
                    str(options.get("title", route.name)),
                    style={"font_size": 16, "color": colors.primary if active else colors.text, "bold": active},
                ),
                on_press=select(route.name),
                style={
                    "padding_vertical": 14,
                    "padding_horizontal": 20,
                    "background_color": colors.background if active else _TRANSPARENT,
                },
                key=f"__drawer_{route.key}",
            )
        )
    panel = View(
        *rows,
        style={
            "width": drawer_width,
            "background_color": colors.card,
            "padding_top": 24,
            "border_right_width": 0.5,
            "border_color": colors.border,
        },
    )
    scrim = Pressable(
        on_press=lambda: set_drawer_open(False),
        style={"flex": 1, "background_color": "#00000080" if theme.dark else "#00000040"},
    )
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
    def Group(*screens: ScreenDef, screen_options: OptionsLike = None) -> ScreenGroup:
        """Group drawer screens that share ``screen_options``."""
        return ScreenGroup(screens, screen_options)

    @staticmethod
    def Navigator(
        *screens: NavigatorItem,
        screen_options: OptionsLike = None,
        initial_route: Optional[str] = None,
        drawer_width: float = _DRAWER_WIDTH,
        key: Optional[str] = None,
    ) -> Element:
        """Render the drawer with the given screens and groups (the first, or ``initial_route``, shows first)."""
        flat, groups = flatten_screens(screens)
        return _DrawerNavigatorImpl(
            screens=flat,
            initial_route=initial_route,
            screen_options=screen_options,
            group_options=groups,
            drawer_width=drawer_width,
        ).with_key(key)


def create_drawer_navigator() -> DrawerNavigator:
    """Create a drawer navigator: sibling screens behind a slide-in menu.

    The drawer is drawn in Python on every platform and styled by the
    navigation theme. The handle returned by
    [`use_navigation`][pythonnative.use_navigation] inside a drawer
    screen is a [`DrawerNavigation`][pythonnative.navigation.DrawerNavigation]
    with ``open_drawer()``, ``close_drawer()``, and ``toggle_drawer()``.
    """
    return DrawerNavigator()
