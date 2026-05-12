"""Comprehensive tests for the declarative navigation system."""

from typing import Any, Dict, List

import pytest

from pythonnative.element import Element
from pythonnative.hooks import HookState, _NavigationContext, _set_hook_state, component, use_navigation
from pythonnative.navigation import (
    NavigationContainer,
    _build_screen_map,
    _DeclarativeNavHandle,
    _DrawerNavHandle,
    _FocusContext,
    _RouteEntry,
    _ScreenDef,
    _TabNavHandle,
    create_drawer_navigator,
    create_stack_navigator,
    create_tab_navigator,
    use_focus_effect,
    use_route,
)
from pythonnative.reconciler import Reconciler

# ======================================================================
# Mock backend (same as test_reconciler / test_hooks)
# ======================================================================


class MockView:
    _next_id = 0

    def __init__(self, type_name: str, props: Dict[str, Any]) -> None:
        MockView._next_id += 1
        self.id = MockView._next_id
        self.type_name = type_name
        self.props = dict(props)
        self.children: List["MockView"] = []


class MockBackend:
    def __init__(self) -> None:
        self.ops: List[Any] = []

    def create_view(self, type_name: str, props: Dict[str, Any]) -> MockView:
        view = MockView(type_name, props)
        self.ops.append(("create", type_name, view.id))
        return view

    def update_view(self, view: MockView, type_name: str, changed: Dict[str, Any]) -> None:
        view.props.update(changed)
        self.ops.append(("update", type_name, view.id, tuple(sorted(changed.keys()))))

    def add_child(self, parent: MockView, child: MockView, parent_type: str) -> None:
        parent.children.append(child)
        self.ops.append(("add_child", parent.id, child.id))

    def remove_child(self, parent: MockView, child: MockView, parent_type: str) -> None:
        parent.children = [c for c in parent.children if c.id != child.id]
        self.ops.append(("remove_child", parent.id, child.id))

    def insert_child(self, parent: MockView, child: MockView, parent_type: str, index: int) -> None:
        parent.children.insert(index, child)
        self.ops.append(("insert_child", parent.id, child.id, index))


# ======================================================================
# Data structures
# ======================================================================


def test_screen_def_creation() -> None:
    s = _ScreenDef("Home", lambda: None, {"title": "Home"})
    assert s.name == "Home"
    assert s.options == {"title": "Home"}
    assert "Home" in repr(s)


def test_screen_def_defaults() -> None:
    s = _ScreenDef("Detail", lambda: None)
    assert s.options == {}


def test_route_entry() -> None:
    r = _RouteEntry("Home", {"id": 42})
    assert r.name == "Home"
    assert r.params == {"id": 42}
    assert "Home" in repr(r)


def test_route_entry_defaults() -> None:
    r = _RouteEntry("Home")
    assert r.params == {}


def test_build_screen_map() -> None:
    screens = [
        _ScreenDef("A", lambda: None),
        _ScreenDef("B", lambda: None),
        "not a screen",
    ]
    result = _build_screen_map(screens)
    assert set(result.keys()) == {"A", "B"}


def test_build_screen_map_empty() -> None:
    assert _build_screen_map(None) == {}
    assert _build_screen_map([]) == {}


# ======================================================================
# _DeclarativeNavHandle
# ======================================================================


def test_declarative_handle_navigate() -> None:
    stack: List[_RouteEntry] = [_RouteEntry("Home")]
    screens = {"Home": _ScreenDef("Home", lambda: None), "Detail": _ScreenDef("Detail", lambda: None)}

    captured: list = []

    def set_stack(val: Any) -> None:
        nonlocal stack
        if callable(val):
            stack = val(stack)
        else:
            stack = val
        captured.append(list(stack))

    handle = _DeclarativeNavHandle(screens, lambda: stack, set_stack)
    handle.navigate("Detail", {"id": 5})

    assert len(captured) == 1
    assert captured[0][-1].name == "Detail"
    assert captured[0][-1].params == {"id": 5}


def test_declarative_handle_go_back() -> None:
    stack: List[_RouteEntry] = [_RouteEntry("Home"), _RouteEntry("Detail")]
    captured: list = []

    def set_stack(val: Any) -> None:
        nonlocal stack
        if callable(val):
            stack = val(stack)
        else:
            stack = val
        captured.append(list(stack))

    handle = _DeclarativeNavHandle({}, lambda: stack, set_stack)
    handle.go_back()

    assert len(captured[-1]) == 1
    assert captured[-1][0].name == "Home"


def test_declarative_handle_go_back_stops_at_root() -> None:
    stack: List[_RouteEntry] = [_RouteEntry("Home")]
    captured: list = []

    def set_stack(val: Any) -> None:
        nonlocal stack
        if callable(val):
            stack = val(stack)
        else:
            stack = val
        captured.append(list(stack))

    handle = _DeclarativeNavHandle({}, lambda: stack, set_stack)
    handle.go_back()

    assert captured == []
    assert len(stack) == 1
    assert stack[0].name == "Home"


def test_declarative_handle_get_params() -> None:
    stack = [_RouteEntry("Home"), _RouteEntry("Detail", {"id": 42})]
    handle = _DeclarativeNavHandle({}, lambda: stack, lambda _: None)

    assert handle.get_params() == {"id": 42}


def test_declarative_handle_get_params_empty_stack() -> None:
    handle = _DeclarativeNavHandle({}, lambda: [], lambda _: None)
    assert handle.get_params() == {}


def test_declarative_handle_reset() -> None:
    stack: List[_RouteEntry] = [_RouteEntry("A"), _RouteEntry("B"), _RouteEntry("C")]
    screens = {"Home": _ScreenDef("Home", lambda: None)}
    captured: list = []

    def set_stack(val: Any) -> None:
        captured.append(val)

    handle = _DeclarativeNavHandle(screens, lambda: stack, set_stack)
    handle.reset("Home", {"fresh": True})

    assert len(captured) == 1
    assert len(captured[0]) == 1
    assert captured[0][0].name == "Home"


def test_declarative_handle_navigate_unknown_raises() -> None:
    handle = _DeclarativeNavHandle({"Home": _ScreenDef("Home", lambda: None)}, lambda: [], lambda _: None)
    with pytest.raises(ValueError, match="Unknown route"):
        handle.navigate("Missing")


# ======================================================================
# Native-backed delegation via host._push / host._pop
# ======================================================================


class _FakeHost:
    """Stub `_ScreenHost` used to assert native-push delegation."""

    def __init__(self, component_path: str = "app.demo.App") -> None:
        self._component_path = component_path
        self.pushed: list = []
        self.popped = 0
        self.reset_count = 0

    def _push(self, page: Any, args: Any) -> None:
        self.pushed.append((page, args))

    def _pop(self) -> None:
        self.popped += 1

    def _reset_to_root(self) -> None:
        self.reset_count += 1


class _FakeHostHandle:
    """Mimics `NavigationHandle`: declarative navigators look for `_host`."""

    def __init__(self, host: Any) -> None:
        self._host = host

    def navigate(self, route_name: str, params: Any = None) -> None:
        # Forwarding fallback (should not be called for host-routed pushes).
        raise AssertionError("host handle navigate() invoked unexpectedly")

    def go_back(self) -> None:
        raise AssertionError("host handle go_back() invoked unexpectedly")


def test_declarative_handle_native_push_when_parent_is_host() -> None:
    """A root Stack whose parent has `_host` should push via the host."""
    host = _FakeHost("app.demo.App")
    parent = _FakeHostHandle(host)
    screens = {"Detail": _ScreenDef("Detail", lambda: None)}

    set_stack_calls: list = []

    def set_stack(val: Any) -> None:
        set_stack_calls.append(val)

    handle = _DeclarativeNavHandle(screens, lambda: [_RouteEntry("Home")], set_stack, parent=parent)
    handle.navigate("Detail", {"id": 7})

    assert len(host.pushed) == 1
    screen_path, push_args = host.pushed[0]
    assert screen_path == "app.demo.App"
    assert push_args["__pn_initial_route__"] == "Detail"
    assert push_args["__pn_initial_params__"] == {"id": 7}
    assert set_stack_calls == []  # in-Python stack is NOT touched


def test_declarative_handle_native_pop_at_root_when_parent_is_host() -> None:
    """`go_back` on a single-entry root stack pops the host nav controller."""
    host = _FakeHost()
    parent = _FakeHostHandle(host)
    handle = _DeclarativeNavHandle(
        {"A": _ScreenDef("A", lambda: None)},
        lambda: [_RouteEntry("A")],
        lambda _: None,
        parent=parent,
    )

    handle.go_back()
    assert host.popped == 1


def test_declarative_handle_native_pop_falls_through_to_in_python_first() -> None:
    """In-Python pop wins when the stack has multiple entries, even on native."""
    host = _FakeHost()
    parent = _FakeHostHandle(host)
    stack: list = [_RouteEntry("A"), _RouteEntry("B")]
    set_stack_calls: list = []

    def set_stack(val: Any) -> None:
        if callable(val):
            new = val(stack)
            stack.clear()
            stack.extend(new)
        else:
            stack.clear()
            stack.extend(val)
        set_stack_calls.append(list(stack))

    handle = _DeclarativeNavHandle({}, lambda: stack, set_stack, parent=parent)
    handle.go_back()
    assert host.popped == 0  # didn't escalate to native pop
    assert set_stack_calls[-1] == [_RouteEntry("A")] or set_stack_calls[-1][0].name == "A"


def test_declarative_handle_native_reset_calls_host_helpers() -> None:
    """`reset` on a root stack invokes both pop-to-root and push."""
    host = _FakeHost("app.demo.App")
    parent = _FakeHostHandle(host)
    handle = _DeclarativeNavHandle(
        {"Home": _ScreenDef("Home", lambda: None)},
        lambda: [_RouteEntry("Home")],
        lambda _: None,
        parent=parent,
    )

    handle.reset("Home", {"fresh": True})
    assert host.reset_count == 1
    assert host.pushed[0][0] == "app.demo.App"
    assert host.pushed[0][1]["__pn_initial_route__"] == "Home"


def test_declarative_handle_reset_unknown_raises() -> None:
    handle = _DeclarativeNavHandle({"Home": _ScreenDef("Home", lambda: None)}, lambda: [], lambda _: None)
    with pytest.raises(ValueError, match="Unknown route"):
        handle.reset("Missing")


# ======================================================================
# Tab nav handle
# ======================================================================


def test_tab_handle_navigate_switches_tab() -> None:
    switched: list = []
    screens = {"A": _ScreenDef("A", lambda: None), "B": _ScreenDef("B", lambda: None)}

    def switch_tab(name: str, params: Any = None) -> None:
        switched.append((name, params))

    handle = _TabNavHandle(screens, lambda: [], lambda _: None, switch_tab)
    handle.navigate("B", {"x": 1})

    assert switched == [("B", {"x": 1})]


# ======================================================================
# Drawer nav handle
# ======================================================================


def test_drawer_handle_open_close_toggle() -> None:
    drawer_state = [False]

    def set_open(val: bool) -> None:
        drawer_state[0] = val

    screens = {"A": _ScreenDef("A", lambda: None)}

    def noop_switch(n: str, p: Any = None) -> None:
        pass

    handle = _DrawerNavHandle(screens, lambda: [], lambda _: None, noop_switch, set_open, lambda: drawer_state[0])

    handle.open_drawer()
    assert drawer_state[0] is True

    handle.close_drawer()
    assert drawer_state[0] is False

    handle.toggle_drawer()
    assert drawer_state[0] is True

    handle.toggle_drawer()
    assert drawer_state[0] is False


def test_drawer_handle_navigate_closes_drawer() -> None:
    drawer_state = [True]
    switched: list = []

    def set_open(val: bool) -> None:
        drawer_state[0] = val

    def switch_screen(name: str, params: Any = None) -> None:
        switched.append(name)

    screens = {"A": _ScreenDef("A", lambda: None), "B": _ScreenDef("B", lambda: None)}
    handle = _DrawerNavHandle(screens, lambda: [], lambda _: None, switch_screen, set_open, lambda: drawer_state[0])

    handle.navigate("B")
    assert switched == ["B"]
    assert drawer_state[0] is False


# ======================================================================
# NavigationContainer
# ======================================================================


def test_navigation_container_wraps_child() -> None:
    child = Element("Text", {"text": "hi"}, [])
    el = NavigationContainer(child)
    assert el.type == "View"
    assert el.props.get("flex") == 1
    assert len(el.children) == 1
    assert el.children[0] is child


def test_navigation_container_with_key() -> None:
    child = Element("Text", {"text": "hi"}, [])
    el = NavigationContainer(child, key="nav")
    assert el.key == "nav"


# ======================================================================
# create_stack_navigator
# ======================================================================


def test_stack_screen_creates_screen_def() -> None:
    Stack = create_stack_navigator()
    s = Stack.Screen("Home", component=lambda: None, options={"title": "Home"})
    assert isinstance(s, _ScreenDef)
    assert s.name == "Home"


def test_stack_navigator_element() -> None:
    Stack = create_stack_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    el = Stack.Navigator(Stack.Screen("Home", component=HomeScreen))
    assert isinstance(el, Element)
    assert callable(el.type)


def test_stack_navigator_renders_initial_screen() -> None:
    Stack = create_stack_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    @component
    def DetailScreen() -> Element:
        return Element("Text", {"text": "detail"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator(
        Stack.Screen("Home", component=HomeScreen),
        Stack.Screen("Detail", component=DetailScreen),
    )
    root = rec.mount(el)

    assert any(op[0] == "create" and op[1] == "Text" for op in backend.ops)

    def find_text(view: MockView) -> Any:
        if view.type_name == "Text":
            return view.props.get("text")
        for c in view.children:
            r = find_text(c)
            if r:
                return r
        return None

    assert find_text(root) == "home"


def test_stack_navigator_respects_initial_route() -> None:
    Stack = create_stack_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    @component
    def DetailScreen() -> Element:
        return Element("Text", {"text": "detail"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator(
        Stack.Screen("Home", component=HomeScreen),
        Stack.Screen("Detail", component=DetailScreen),
        initial_route="Detail",
    )
    root = rec.mount(el)

    def find_text(view: MockView) -> Any:
        if view.type_name == "Text":
            return view.props.get("text")
        for c in view.children:
            r = find_text(c)
            if r:
                return r
        return None

    assert find_text(root) == "detail"


def test_stack_navigator_provides_navigation_context() -> None:
    Stack = create_stack_navigator()
    captured_nav: list = [None]

    @component
    def HomeScreen() -> Element:
        nav = use_navigation()
        captured_nav[0] = nav
        return Element("Text", {"text": "home"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator(Stack.Screen("Home", component=HomeScreen))
    rec.mount(el)

    assert captured_nav[0] is not None
    assert hasattr(captured_nav[0], "navigate")
    assert hasattr(captured_nav[0], "go_back")
    assert hasattr(captured_nav[0], "get_params")


def test_stack_navigator_empty_screens() -> None:
    Stack = create_stack_navigator()

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator()
    root = rec.mount(el)
    assert root.type_name == "View"


# ======================================================================
# create_tab_navigator
# ======================================================================


def test_tab_screen_creates_screen_def() -> None:
    Tab = create_tab_navigator()
    s = Tab.Screen("Home", component=lambda: None, options={"title": "Home"})
    assert isinstance(s, _ScreenDef)


def test_tab_navigator_renders_initial_screen() -> None:
    Tab = create_tab_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    @component
    def SettingsScreen() -> Element:
        return Element("Text", {"text": "settings"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Tab.Navigator(
        Tab.Screen("Home", component=HomeScreen, options={"title": "Home"}),
        Tab.Screen("Settings", component=SettingsScreen, options={"title": "Settings"}),
    )
    root = rec.mount(el)

    def find_texts(view: MockView) -> list:
        result = []
        if view.type_name == "Text":
            result.append(view.props.get("text"))
        for c in view.children:
            result.extend(find_texts(c))
        return result

    texts = find_texts(root)
    assert "home" in texts


def test_tab_navigator_renders_native_tab_bar() -> None:
    Tab = create_tab_navigator()

    @component
    def ScreenA() -> Element:
        return Element("Text", {"text": "a"}, [])

    @component
    def ScreenB() -> Element:
        return Element("Text", {"text": "b"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Tab.Navigator(
        Tab.Screen("TabA", component=ScreenA, options={"title": "Tab A"}),
        Tab.Screen("TabB", component=ScreenB, options={"title": "Tab B"}),
    )
    root = rec.mount(el)

    def find_tab_bar(view: MockView) -> Any:
        if view.type_name == "TabBar":
            return view
        for c in view.children:
            r = find_tab_bar(c)
            if r is not None:
                return r
        return None

    tab_bar = find_tab_bar(root)
    assert tab_bar is not None
    assert tab_bar.props["items"] == [
        {"name": "TabA", "title": "Tab A"},
        {"name": "TabB", "title": "Tab B"},
    ]
    assert tab_bar.props["active_tab"] == "TabA"
    assert callable(tab_bar.props["on_tab_select"])


def test_tab_navigator_empty_screens() -> None:
    Tab = create_tab_navigator()

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Tab.Navigator()
    root = rec.mount(el)
    assert root.type_name == "View"


# ======================================================================
# create_drawer_navigator
# ======================================================================


def test_drawer_screen_creates_screen_def() -> None:
    Drawer = create_drawer_navigator()
    s = Drawer.Screen("Home", component=lambda: None)
    assert isinstance(s, _ScreenDef)


def test_drawer_navigator_renders_initial_screen() -> None:
    Drawer = create_drawer_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    @component
    def SettingsScreen() -> Element:
        return Element("Text", {"text": "settings"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Drawer.Navigator(
        Drawer.Screen("Home", component=HomeScreen),
        Drawer.Screen("Settings", component=SettingsScreen),
    )
    root = rec.mount(el)

    def find_texts(view: MockView) -> list:
        result = []
        if view.type_name == "Text":
            result.append(view.props.get("text"))
        for c in view.children:
            result.extend(find_texts(c))
        return result

    texts = find_texts(root)
    assert "home" in texts


def test_drawer_navigator_empty_screens() -> None:
    Drawer = create_drawer_navigator()

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Drawer.Navigator()
    root = rec.mount(el)
    assert root.type_name == "View"


# ======================================================================
# use_route
# ======================================================================


def test_use_route_returns_params() -> None:
    stack = [_RouteEntry("Home"), _RouteEntry("Detail", {"id": 99})]
    screens = {"Home": _ScreenDef("Home", lambda: None), "Detail": _ScreenDef("Detail", lambda: None)}
    handle = _DeclarativeNavHandle(screens, lambda: stack, lambda _: None)

    _NavigationContext._stack.append(handle)
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        params = use_route()
        assert params == {"id": 99}
    finally:
        _set_hook_state(None)
        _NavigationContext._stack.pop()


def test_use_route_no_context() -> None:
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        params = use_route()
        assert params == {}
    finally:
        _set_hook_state(None)


# ======================================================================
# use_focus_effect
# ======================================================================


def test_use_focus_effect_runs_when_focused() -> None:
    calls: list = []

    _FocusContext._stack.append(True)
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        use_focus_effect(lambda: calls.append("focused"), [])
    finally:
        _set_hook_state(None)
        _FocusContext._stack.pop()

    ctx.flush_pending_effects()
    assert calls == ["focused"]


def test_use_focus_effect_skips_when_not_focused() -> None:
    calls: list = []

    _FocusContext._stack.append(False)
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        use_focus_effect(lambda: calls.append("focused"), [])
    finally:
        _set_hook_state(None)
        _FocusContext._stack.pop()

    ctx.flush_pending_effects()
    assert calls == []


# ======================================================================
# Integration: stack navigator with reconciler
# ======================================================================


def test_stack_navigator_navigate_and_go_back() -> None:
    Stack = create_stack_navigator()
    captured_nav: list = [None]

    @component
    def HomeScreen() -> Element:
        nav = use_navigation()
        captured_nav[0] = nav
        return Element("Text", {"text": "home"}, [])

    @component
    def DetailScreen() -> Element:
        nav = use_navigation()
        captured_nav[0] = nav
        return Element("Text", {"text": "detail"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    renders: list = []
    rec._screen_re_render = lambda: renders.append(1)

    el = Stack.Navigator(
        Stack.Screen("Home", component=HomeScreen),
        Stack.Screen("Detail", component=DetailScreen),
    )
    rec.mount(el)

    nav = captured_nav[0]
    assert nav is not None

    nav.navigate("Detail", {"id": 1})
    assert len(renders) == 1


def test_stack_navigator_with_navigation_container() -> None:
    Stack = create_stack_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = NavigationContainer(Stack.Navigator(Stack.Screen("Home", component=HomeScreen)))
    root = rec.mount(el)
    assert root.type_name == "View"


# ======================================================================
# Parent forwarding (nested navigators)
# ======================================================================


def test_declarative_handle_forwards_navigate_to_parent() -> None:
    """Unknown routes in a child navigator forward to the parent."""
    parent_calls: list = []

    class _MockParent:
        def navigate(self, route_name: str, params: Any = None) -> None:
            parent_calls.append(("navigate", route_name, params))

        def go_back(self) -> None:
            parent_calls.append(("go_back",))

    child_screens = {"A": _ScreenDef("A", lambda: None)}
    handle = _DeclarativeNavHandle(child_screens, lambda: [_RouteEntry("A")], lambda _: None, parent=_MockParent())

    handle.navigate("UnknownRoute", {"key": "value"})
    assert parent_calls == [("navigate", "UnknownRoute", {"key": "value"})]


def test_declarative_handle_forwards_go_back_at_root() -> None:
    """go_back at the root of a child navigator forwards to the parent."""
    parent_calls: list = []

    class _MockParent:
        def navigate(self, route_name: str, params: Any = None) -> None:
            parent_calls.append(("navigate", route_name))

        def go_back(self) -> None:
            parent_calls.append(("go_back",))

    child_screens = {"A": _ScreenDef("A", lambda: None)}
    stack: List[_RouteEntry] = [_RouteEntry("A")]
    handle = _DeclarativeNavHandle(child_screens, lambda: stack, lambda _: None, parent=_MockParent())

    handle.go_back()
    assert parent_calls == [("go_back",)]


def test_declarative_handle_no_parent_raises_on_unknown() -> None:
    """Without a parent, unknown routes still raise ValueError."""
    handle = _DeclarativeNavHandle({"A": _ScreenDef("A", lambda: None)}, lambda: [], lambda _: None)
    with pytest.raises(ValueError, match="Unknown route"):
        handle.navigate("Missing")


def test_tab_handle_forwards_unknown_to_parent() -> None:
    parent_calls: list = []

    class _MockParent:
        def navigate(self, route_name: str, params: Any = None) -> None:
            parent_calls.append(("navigate", route_name, params))

        def go_back(self) -> None:
            parent_calls.append(("go_back",))

    screens = {"TabA": _ScreenDef("TabA", lambda: None)}

    def noop_switch(name: str, params: Any = None) -> None:
        pass

    handle = _TabNavHandle(screens, lambda: [], lambda _: None, noop_switch, parent=_MockParent())
    handle.navigate("ExternalRoute", {"x": 1})
    assert parent_calls == [("navigate", "ExternalRoute", {"x": 1})]


def test_drawer_handle_forwards_unknown_to_parent() -> None:
    parent_calls: list = []

    class _MockParent:
        def navigate(self, route_name: str, params: Any = None) -> None:
            parent_calls.append(("navigate", route_name, params))

        def go_back(self) -> None:
            parent_calls.append(("go_back",))

    screens = {"DrawerA": _ScreenDef("DrawerA", lambda: None)}

    def noop_switch(n: str, p: Any = None) -> None:
        pass

    handle = _DrawerNavHandle(
        screens, lambda: [], lambda _: None, noop_switch, lambda _: None, lambda: False, parent=_MockParent()
    )
    handle.navigate("ExternalRoute")
    assert parent_calls == [("navigate", "ExternalRoute", None)]


def test_stack_inside_tab_forwards_to_parent() -> None:
    """A Stack.Navigator nested inside a Tab.Navigator can forward."""
    Stack = create_stack_navigator()
    Tab = create_tab_navigator()

    captured_nav: list = [None]

    @component
    def InnerScreen() -> Element:
        nav = use_navigation()
        captured_nav[0] = nav
        return Element("Text", {"text": "inner"}, [])

    @component
    def InnerStack() -> Element:
        return Stack.Navigator(Stack.Screen("Inner", component=InnerScreen))

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Tab.Navigator(
        Tab.Screen("TabA", component=InnerStack),
        Tab.Screen("TabB", component=lambda: Element("Text", {"text": "b"}, [])),
    )
    rec.mount(el)

    nav = captured_nav[0]
    assert nav is not None

    nav.navigate("TabB")
    assert True  # no error means forwarding worked


# ======================================================================
# Public API surface
# ======================================================================


def test_navigation_exports_from_package() -> None:
    import pythonnative as pn

    assert hasattr(pn, "NavigationContainer")
    assert hasattr(pn, "create_stack_navigator")
    assert hasattr(pn, "create_tab_navigator")
    assert hasattr(pn, "create_drawer_navigator")
    assert hasattr(pn, "use_route")
    assert hasattr(pn, "use_focus_effect")


# ======================================================================
# Initial route propagated through host args (native-push pickup)
# ======================================================================


class _ArgsHostHandle:
    """Host nav handle that exposes args via `get_params`."""

    def __init__(self, host_args: Dict[str, Any]) -> None:
        self._host = type("HostStub", (), {"_component_path": "app.demo.App"})()
        self._host_args = host_args

    def get_params(self) -> Dict[str, Any]:
        return self._host_args

    def navigate(self, route_name: str, params: Any = None) -> None:
        return None

    def go_back(self) -> None:
        return None


def test_stack_navigator_initial_route_from_host_args() -> None:
    """When the host's args carry __pn_initial_route__, the Stack starts there."""
    Stack = create_stack_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    @component
    def DetailScreen() -> Element:
        params = use_route()
        return Element("Text", {"text": f"detail:{params.get('id')}"}, [])

    parent = _ArgsHostHandle(
        {
            "__pn_initial_route__": "Detail",
            "__pn_initial_params__": {"id": 99},
        }
    )

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator(
        Stack.Screen("Home", component=HomeScreen),
        Stack.Screen("Detail", component=DetailScreen),
    )
    from pythonnative.hooks import Provider as _Provider

    root = rec.mount(_Provider(_NavigationContext, parent, el))

    def find_text(view: MockView) -> Any:
        if view.type_name == "Text":
            return view.props.get("text")
        for c in view.children:
            r = find_text(c)
            if r:
                return r
        return None

    assert find_text(root) == "detail:99"


def test_stack_navigator_falls_back_when_host_route_unknown() -> None:
    """An unknown route in host args is ignored and the navigator picks its default."""
    Stack = create_stack_navigator()

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    parent = _ArgsHostHandle({"__pn_initial_route__": "MysteryScreen"})

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator(Stack.Screen("Home", component=HomeScreen))
    from pythonnative.hooks import Provider as _Provider

    root = rec.mount(_Provider(_NavigationContext, parent, el))

    def find_text(view: MockView) -> Any:
        if view.type_name == "Text":
            return view.props.get("text")
        for c in view.children:
            r = find_text(c)
            if r:
                return r
        return None

    assert find_text(root) == "home"


def test_stack_navigator_calls_set_screen_options() -> None:
    """The active screen's options['title'] is forwarded to the host."""
    Stack = create_stack_navigator()
    seen_options: list = []

    class _OptionRecorder:
        _component_path = "app.demo.App"

        def _set_screen_options(self, opts: Dict[str, Any]) -> None:
            seen_options.append(opts)

    class _Parent:
        def __init__(self, host: Any) -> None:
            self._host = host

        def get_params(self) -> Dict[str, Any]:
            return {}

        def navigate(self, route_name: str, params: Any = None) -> None:
            return None

        def go_back(self) -> None:
            return None

    @component
    def HomeScreen() -> Element:
        return Element("Text", {"text": "home"}, [])

    parent = _Parent(_OptionRecorder())

    backend = MockBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None

    el = Stack.Navigator(Stack.Screen("Home", component=HomeScreen, options={"title": "Hello"}))
    from pythonnative.hooks import Provider as _Provider

    rec.mount(_Provider(_NavigationContext, parent, el))

    assert seen_options == [{"title": "Hello"}]
