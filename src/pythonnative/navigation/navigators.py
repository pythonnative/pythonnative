"""Stack, tab, and drawer navigators: immutable values rendered by one shared core.

A navigator is a module-level value listing its screens:

```python
Root = pn.StackNavigator(
    pn.Screen(HomeScreen, title="Home"),
    pn.Screen(ItemScreen, path="items/{id}"),
    pn.Group(pn.Screen(ComposeScreen), presentation="modal"),
)
```

Calling a navigator (``Root()``) returns the element that renders it,
so a navigator is a zero-argument component: pass it to
[`NavigationContainer`][pythonnative.NavigationContainer], list it as a
screen of another navigator to nest it, or render it from a component.
Navigators listed as screens are *statically* nested: deep links and
``navigate`` resolve screens inside them without rendering anything.

Each rendered navigator owns a
[`NavigationState`][pythonnative.navigation.NavigationState] in
``use_state``, wraps it in a
[`NavigatorCore`][pythonnative.navigation.handle.NavigatorCore], and
renders its screens under a [`Navigation`][pythonnative.Navigation]
provider. Only the *rendering* differs:

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
  ``TabBar`` styled by ``tab_bar_style`` and the theme.
- **Drawer**: like tabs, with a Python-drawn, themed slide-in menu
  instead of a tab bar.

Navigator chrome takes its colors from [`use_theme`][pythonnative.use_theme].
Inactive screens read ``False`` from
[`use_is_focused`][pythonnative.use_is_focused]; ``focus`` and ``blur``
listeners fire as the active route changes.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Unpack

from ..component import Component, component
from ..element import Element, Node
from ..hooks import use_back_handler, use_context, use_effect, use_memo, use_ref, use_state
from ..icons import tab_icon_spec
from ..style import Style, StyleProp
from ..theme import Theme, use_theme
from .container import ContainerContext
from .handle import FocusContext, Navigation, NavigationContext, NavigatorCore, provide, split_target
from .host import HostContext
from .screen import (
    PYTHON_ONLY_OPTIONS,
    Screen,
    ScreenLike,
    ScreenOptions,
    ScreenTarget,
    TabBarStyle,
    find_screen,
    flatten_screens,
)
from .state import NavigationState, Route

__all__ = [
    "DrawerNavigator",
    "Navigator",
    "StackNavigator",
    "TabNavigator",
    "navigator_of",
    "use_screen_options",
]

NavigatorKind = Literal["stack", "tab", "drawer"]

_HEADER_HEIGHT = 44.0
_DRAWER_WIDTH = 280.0
_TRANSPARENT = "#00000000"


# ======================================================================
# Navigator values
# ======================================================================


class Navigator:
    """A navigator definition: its screens, initial screen, and shared options.

    Create one with [`StackNavigator`][pythonnative.StackNavigator],
    [`TabNavigator`][pythonnative.TabNavigator], or
    [`DrawerNavigator`][pythonnative.DrawerNavigator]. Navigators are
    immutable values, usually defined at module level. Calling one
    returns the element that renders it.

    Attributes:
        kind: ``"stack"``, ``"tab"``, or ``"drawer"``.
        screens: The flattened [`Screen`][pythonnative.Screen]s, in order.
        name: Route name used when this navigator is a screen of
            another navigator.
        screen_options: Options applied to every screen.
        group_options: Options contributed by ``Group``s, keyed by route name.
        initial_name: Route name of the screen shown first.
        initial_params: Params of the screen shown first.
    """

    kind: NavigatorKind = "stack"

    __slots__ = ("screens", "group_options", "name", "screen_options", "initial_name", "initial_params")

    def __init__(
        self,
        *screens: ScreenLike,
        name: Optional[str] = None,
        initial: Optional[ScreenTarget] = None,
        screen_options: Optional[ScreenOptions] = None,
    ) -> None:
        from .screen import validate_screen_options

        flat, groups = flatten_screens(screens)
        if not flat:
            raise ValueError(f"{type(self).__name__} needs at least one screen")
        options: Dict[str, Any] = dict(screen_options or {})
        validate_screen_options(options)
        self.screens: Tuple[Screen, ...] = flat
        self.group_options: Dict[str, Dict[str, Any]] = groups
        self.name = name
        self.screen_options = options
        self.initial_name, self.initial_params = self._resolve_initial(initial)
        self._check_screens()

    def _resolve_initial(self, initial: Optional[ScreenTarget]) -> Tuple[str, Dict[str, Any]]:
        if initial is None:
            screen, params = self.screens[0], dict[str, Any]()
        else:
            component, params = split_target(initial)
            found = find_screen(self.screens, component)
            if found is None:
                raise ValueError(f"initial={initial!r} isn't one of this navigator's screens")
            screen = found
        missing = [name for name in screen.required_params() if name not in params]
        if missing:
            raise TypeError(
                f"The initial screen {screen.name!r} requires {missing}; "
                f"pass initial={screen.name}(...) with those arguments"
            )
        return screen.name, params

    def _check_screens(self) -> None:
        """Stacks only need their initial screen to be renderable without params."""

    def path_to(self, target: Any) -> Optional[List[Screen]]:
        """The chain of screens from this navigator to the one rendering ``target``, or ``None``.

        Direct screens win over screens of nested navigators; nested
        navigators are searched in order. The identical component
        anywhere in the tree wins over a Fast Refresh name match.
        """
        return self._path_to(target, exact=True) or self._path_to(target, exact=False)

    def _path_to(self, target: Any, *, exact: bool) -> Optional[List[Screen]]:
        for screen in self.screens:
            if screen.matches(target, exact=exact):
                return [screen]
        for screen in self.screens:
            nested = screen.navigator
            if nested is not None:
                chain = nested._path_to(target, exact=exact)
                if chain is not None:
                    return [screen, *chain]
        return None

    def __call__(self) -> Element:
        """Return the element that renders this navigator."""
        return _IMPLEMENTATIONS[self.kind](navigator=self)

    def __repr__(self) -> str:
        label = f" {self.name!r}" if self.name else ""
        return f"<{type(self).__name__}{label} {[screen.name for screen in self.screens]}>"


class _KeepAliveNavigator(Navigator):
    """Tabs and drawers create every route up front, so every screen must be renderable without params."""

    __slots__ = ()

    def _check_screens(self) -> None:
        for screen in self.screens:
            if screen.name == self.initial_name:
                continue  # its params come from ``initial``
            missing = screen.required_params()
            if missing:
                raise TypeError(
                    f"{type(self).__name__} screen {screen.name!r} requires {missing}; tab and drawer screens "
                    "must be callable without arguments (give the parameters defaults)"
                )


class StackNavigator(Navigator):
    """A stack of screens with history, native transitions, and a native navigation bar.

    Stacks use native screen containers at every nesting level on
    mobile: ``UINavigationController`` on iOS and fragments on Android
    draw the navigation bar and run the transitions. Without a native
    host (tests, headless rendering) the stack draws a themed header
    itself.

    Args:
        *screens: [`Screen`][pythonnative.Screen]s, [`Group`][pythonnative.Group]s,
            bare components, or nested navigators.
        name: Route name when this navigator is nested as a screen.
        initial: The screen shown first: a component, or an element
            carrying its params (``initial=ItemScreen(id=1)``). Defaults
            to the first screen.
        screen_options: [`ScreenOptions`][pythonnative.ScreenOptions]
            for every screen; groups and screens layer on top.

    Example:
        ```python
        Root = pn.StackNavigator(
            pn.Screen(HomeScreen, title="Home"),
            pn.Screen(ItemScreen, path="items/{id}"),
            pn.Group(pn.Screen(ComposeScreen), presentation="modal"),
            screen_options=pn.ScreenOptions(header_large_title=True),
        )
        ```
    """

    kind: NavigatorKind = "stack"
    __slots__ = ()


class TabNavigator(_KeepAliveNavigator):
    """Sibling screens behind a native tab bar.

    Tabs stay mounted once visited (hidden while inactive) so switching
    back restores scroll position and state. Use ``lazy=False`` on a
    screen to mount it eagerly, ``unmount_on_blur=True`` to tear it
    down when it loses focus, and ``freeze_on_blur=True`` to stop
    re-rendering it while hidden. ``tab_bar_visible=False`` hides the
    bar while that tab is focused.

    Args:
        *screens: The tabs (see [`StackNavigator`][pythonnative.StackNavigator]).
        name: Route name when this navigator is nested as a screen.
        initial: The tab selected first. Defaults to the first tab.
        screen_options: Options for every tab.
        tab_bar_style: A [`TabBarStyle`][pythonnative.TabBarStyle];
            unset keys fall back to the theme.

    Example:
        ```python
        Tabs = pn.TabNavigator(
            pn.Screen(FeedScreen, title="Feed", tab_bar_icon="house"),
            pn.Screen(SettingsScreen, title="Settings", tab_bar_icon="settings"),
            name="Main",
        )
        ```
    """

    kind: NavigatorKind = "tab"
    __slots__ = ("tab_bar_style",)

    def __init__(
        self,
        *screens: ScreenLike,
        name: Optional[str] = None,
        initial: Optional[ScreenTarget] = None,
        screen_options: Optional[ScreenOptions] = None,
        tab_bar_style: Optional[TabBarStyle] = None,
    ) -> None:
        super().__init__(*screens, name=name, initial=initial, screen_options=screen_options)
        self.tab_bar_style: Optional[TabBarStyle] = tab_bar_style


class DrawerNavigator(_KeepAliveNavigator):
    """Sibling screens behind a slide-in menu.

    The drawer is drawn in Python on every platform and styled by the
    theme. The handle returned by
    [`use_navigation`][pythonnative.use_navigation] inside a drawer
    screen is a [`DrawerNavigation`][pythonnative.navigation.DrawerNavigation]
    with ``open_drawer()``, ``close_drawer()``, and ``toggle_drawer()``.

    Args:
        *screens: The drawer's screens.
        name: Route name when this navigator is nested as a screen.
        initial: The screen shown first. Defaults to the first screen.
        screen_options: Options for every screen.
        drawer_width: Width of the menu panel, in points.
    """

    kind: NavigatorKind = "drawer"
    __slots__ = ("drawer_width",)

    def __init__(
        self,
        *screens: ScreenLike,
        name: Optional[str] = None,
        initial: Optional[ScreenTarget] = None,
        screen_options: Optional[ScreenOptions] = None,
        drawer_width: float = _DRAWER_WIDTH,
    ) -> None:
        super().__init__(*screens, name=name, initial=initial, screen_options=screen_options)
        self.drawer_width = drawer_width


def navigator_of(element: Element) -> Optional[Navigator]:
    """The navigator an element renders, when it was produced by calling a navigator."""
    if element.type in _IMPLEMENTATION_TYPES:
        navigator = element.props.get("navigator")
        if isinstance(navigator, Navigator):
            return navigator
    return None


# ======================================================================
# Shared core hook
# ======================================================================


def _restorable(navigator: Navigator, state: NavigationState) -> bool:
    screens = {screen.name: screen for screen in navigator.screens}
    for route in state.routes:
        screen = screens.get(route.name)
        if screen is None or any(name not in route.params for name in screen.required_params()):
            return False
    return True


def _use_navigator(navigator: Navigator) -> Tuple[NavigatorCore, NavigationState, bool]:
    """Create (once) and refresh the navigator core for the calling component.

    Returns ``(core, state, parent_focused)``.
    """
    parent = use_context(NavigationContext)
    host = use_context(HostContext)
    parent_focused = use_context(FocusContext)
    enclosing_container = use_context(ContainerContext)
    container = enclosing_container if parent is None else None
    is_native_root = navigator.kind == "stack" and parent is None and host is not None

    def default_state() -> NavigationState:
        first = navigator.initial_name
        if navigator.kind == "stack":
            return NavigationState([Route(first, navigator.initial_params)])
        routes = [
            Route(screen.name, navigator.initial_params if screen.name == first else {}) for screen in navigator.screens
        ]
        return NavigationState(routes, [screen.name for screen in navigator.screens].index(first))

    def initial_state() -> NavigationState:
        if is_native_root:
            assert host is not None
            serialized = host.initial_navigation_state()
            if serialized:
                try:
                    restored: Optional[NavigationState] = NavigationState.from_dict(serialized)
                except (AttributeError, KeyError, TypeError, ValueError, IndexError):
                    restored = None
                if restored is not None and _restorable(navigator, restored):
                    return restored
        seed = parent.route.state if parent is not None else (container.initial_state if container else None)
        if seed is not None:
            seeded = _apply_seed(navigator, default_state(), seed)
            if seeded is not None:
                return seeded
        return default_state()

    state, set_state = use_state(initial_state)
    _version, set_version = use_state(0)
    core: NavigatorCore = use_memo(
        lambda: NavigatorCore(
            navigator,
            state,
            set_state,
            parent,
            host,
            request_render=lambda: set_version(lambda v: v + 1),
        ),
        [],  # pn: ignore[PN103] the core is created once; ``update`` refreshes it every render
    )
    core.update(navigator, state, set_state, parent, host)
    _use_focus_events(core, state, parent_focused)
    _use_seed_updates(core, parent)
    _use_container(core, state, container)
    return core, state, parent_focused


def _apply_seed(navigator: Navigator, base: NavigationState, seed: NavigationState) -> Optional[NavigationState]:
    """Merge a seed state (a deep link, or navigating into a nested navigator) into ``base``.

    Stacks keep their initial route underneath so back works; tabs and
    drawers switch to the seeded route and merge its params. Unknown
    route names or missing params make the seed invalid (``None``).
    """
    if not _restorable(navigator, seed):
        return None
    if navigator.kind == "stack":
        routes = list(seed.routes)
        if routes[0].name != base.routes[0].name:
            routes.insert(0, base.routes[0])
        return NavigationState(routes)
    target = seed.current
    return base.jump_to(target.name, target.params, target.state)


def _use_seed_updates(core: NavigatorCore, parent: Optional[Navigation]) -> None:
    """Follow later navigation into this nested navigator made through the parent."""
    seed = parent.route.state if parent is not None else None
    applied: Any = use_ref(seed)

    def run() -> None:
        if seed is None or seed is applied.current:
            return
        applied.current = seed
        target = seed.current
        if target.name in core.screens:
            core.navigate(target.name, target.params, target.state)

    use_effect(run, [core, seed])


def _use_container(core: NavigatorCore, state: NavigationState, container: Any) -> None:
    """Attach a root navigator to its container (deep links, ``on_state_change``, the ``NavigationRef``)."""

    def attach() -> Any:
        return container.attach_root(core) if container is not None else None

    use_effect(attach, [core, container])

    def report() -> None:
        if container is not None and container.on_state_change is not None:
            container.on_state_change(state)

    use_effect(report, [container, state])

    def cache() -> None:
        publish = getattr(core.host, "cache_navigation_state", None)
        if core.is_native_root and publish is not None:
            publish(state.to_dict())

    use_effect(cache, [core, state])


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

    use_effect(run, [core, state.current.key, parent_focused])

    def emit_state() -> None:
        core.emit(state.current, "state", {"state": state})

    use_effect(emit_state, [core, state])


# ======================================================================
# Screen rendering shared by every navigator
# ======================================================================


def _screen_body(core: NavigatorCore, route: Route, theme: Theme) -> Node:
    """The element for ``route``'s screen, or a themed fallback for an unknown route."""
    if route.name not in core.screens:
        from ..components import Text

        return Text(f"Unknown route: {route.name}", style={"color": theme.colors.text})
    return core.body_for(route)


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
def _NativeHeaderSlot(*, value: Element, side: str) -> Element:
    return Element("View", {"_pn_header_slot": side, "height": 44, "justify_content": "center"}, [value])


def _native_screen_props(options: Dict[str, Any], theme: Theme) -> Dict[str, Any]:
    """Wire props for a native ``Screen``: the options native reads, with theme colors filled in as defaults."""
    props = {key: value for key, value in options.items() if key not in PYTHON_ONLY_OPTIONS}
    props.setdefault("header_tint_color", theme.colors.primary)
    header_style = dict(options.get("header_style") or {})
    header_style.setdefault("background_color", theme.colors.surface)
    props["header_style"] = header_style
    title_style = dict(options.get("header_title_style") or {})
    title_style.setdefault("color", theme.colors.text)
    props["header_title_style"] = title_style
    props.setdefault("title", "")
    return props


def _native_screen(core: NavigatorCore, route: Route, active: bool, parent_focused: bool, theme: Theme) -> Element:
    options = core.options_for(route)
    options.setdefault("title", route.name)
    # ``guarded`` is an internal wire prop, recomputed every render: while
    # the route has a ``before_remove`` listener, iOS refuses the pop or
    # dismiss synchronously and reports ``on_native_back`` for Python to
    # decide, instead of animating the screen out and back in.
    guarded = core.has_listeners(route.key, "before_remove")
    return Element(
        "Screen",
        {
            "flex": 1,
            # A transparent modal shows the screen below it through its own background.
            "background_color": (
                _TRANSPARENT if options.get("presentation") == "transparent_modal" else theme.colors.background
            ),
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


def _hidden_style(active: bool, theme: Theme) -> Style:
    return {"flex": 1, "display": "flex" if active else "none", "background_color": theme.colors.background}


# ======================================================================
# Stack
# ======================================================================


@component
def _StackHeader(*, core: NavigatorCore, route: Route, options: Dict[str, Any], theme: Theme) -> Optional[Element]:
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
            "background_color": theme.colors.surface,
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
    left: Optional[Element] = options.get("header_left")
    if left is None and handle.can_go_back() and options.get("header_back_visible", True):
        back_title = options.get("header_back_title") or "Back"
        left = Pressable(
            Text(f"‹ {back_title}", style={"color": tint, "font_size": 17}),
            on_press=handle.go_back,
            accessibility_label="Back",
        )
    right: Optional[Element] = options.get("header_right")
    return View(
        View(left, style={"min_width": 60, "align_items": "flex_start"}),
        Text(str(options.get("title", route.name)), style=title_style),
        View(right, style={"min_width": 60, "align_items": "flex_end"}),
        style=style,
    )


@component
def _StackNavigatorImpl(*, navigator: StackNavigator) -> Element:
    from ..components import View

    theme = use_theme()
    core, state, parent_focused = _use_navigator(navigator)

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
        layers.append(View(header, View(body, style={"flex": 1}), style=_hidden_style(active, theme), key=route.key))
    return View(*layers, style={"flex": 1})


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
    theme: Theme,
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
        if options.get("freeze_on_blur", False) and not active and route.key in frozen:
            # The identical element makes the reconciler skip the screen.
            body = frozen[route.key]
        else:
            body = _screen_body(core, route, theme)
            frozen[route.key] = body
        out.append(
            View(
                _screen_element(core, route, body, active=active, parent_focused=parent_focused),
                style=_hidden_style(active, theme),
                key=route.key,
            )
        )
    return out


# ======================================================================
# Tabs
# ======================================================================


def _tab_bar_props(style: Optional[TabBarStyle], theme: Theme) -> Dict[str, Any]:
    """Translate ``TabBarStyle`` plus theme defaults into the native ``TabBar`` props."""
    resolved: Dict[str, Any] = dict(style or {})
    props: Dict[str, Any] = {
        "tint_color": resolved.get("active_tint_color", theme.colors.primary),
        "background_color": resolved.get("background_color", theme.colors.surface),
    }
    if "inactive_tint_color" in resolved:
        props["inactive_tint_color"] = resolved["inactive_tint_color"]
    if "translucent" in resolved:
        props["translucent"] = bool(resolved["translucent"])
    if "show_labels" in resolved:
        props["shows_labels"] = bool(resolved["show_labels"])
    return props


@component
def _TabNavigatorImpl(*, navigator: TabNavigator) -> Element:
    from ..components import View

    theme = use_theme()
    core, state, parent_focused = _use_navigator(navigator)
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
                    **_tab_bar_props(navigator.tab_bar_style, theme),
                },
                [],
                key="__tab_bar__",
            )
        )
    return View(*children, style={"flex": 1, "flex_direction": "column"})


# ======================================================================
# Drawer
# ======================================================================


@component
def _DrawerNavigatorImpl(*, navigator: DrawerNavigator) -> Element:
    from ..components import Pressable, Text, View

    theme = use_theme()
    core, state, parent_focused = _use_navigator(navigator)
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
            "width": navigator.drawer_width,
            "background_color": colors.surface,
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


_IMPLEMENTATIONS: Dict[str, Component[...]] = {
    "stack": _StackNavigatorImpl,
    "tab": _TabNavigatorImpl,
    "drawer": _DrawerNavigatorImpl,
}
_IMPLEMENTATION_TYPES = frozenset(_IMPLEMENTATIONS.values())


def use_screen_options(**options: Unpack[ScreenOptions]) -> None:
    """Set the calling screen's options from its render.

    Options set here layer over the screen's static options and follow
    the screen's props and state, so dynamic titles and header buttons
    live next to the code that computes them:

    ```python
    @pn.component
    def ItemScreen(id: int) -> pn.Node:
        item = use_item(id)
        pn.use_screen_options(
            title=item.title,
            header_right=pn.Button("Share", on_press=lambda: share(item)),
        )
        return ItemDetails(item)
    ```

    The navigator re-renders only when the options actually change, and
    it doesn't re-render the screen in response.

    Raises:
        RuntimeError: If the calling component isn't inside a navigator.
        TypeError: For an unknown option key.
    """
    from ..hooks import use_layout_effect
    from .hooks import use_navigation

    navigation = use_navigation()

    def apply() -> None:
        navigation.set_options(**options)

    use_layout_effect(apply)
