"""Tests for the navigation package: state, core, navigators, hooks, linking."""

from typing import Any, Dict, List, NotRequired, TypedDict

import pytest

import pythonnative as pn
from pythonnative.component import component
from pythonnative.components import Button, Column, Text
from pythonnative.hooks import use_effect, use_state
from pythonnative.native_modules import linking as linking_module
from pythonnative.navigation import (
    DrawerNavigation,
    LinkingConfig,
    Navigation,
    NavigationContainer,
    NavigationContext,
    NavigationEvent,
    NavigationState,
    NavigatorCore,
    Route,
    ScreenDef,
    TabNavigation,
    create_drawer_navigator,
    create_stack_navigator,
    create_tab_navigator,
    use_focus_effect,
    use_is_focused,
    use_navigation,
    use_route,
)
from pythonnative.testing import FakeHost, render, render_hook

# ======================================================================
# Helpers
# ======================================================================


def _screen(label: str) -> Any:
    """A screen component that shows ``label`` and its route params."""

    @component
    def Screen() -> Any:
        route = use_route()
        params = ",".join(f"{k}={v}" for k, v in sorted(route.params.items()))
        return Column(Text(label), Text(f"params:{params}"))

    return Screen


def _capturing_screen(label: str, box: Dict[str, Any]) -> Any:
    """A screen that stores its ``Navigation`` handle in ``box`` for the test to drive."""

    @component
    def Screen() -> Any:
        box[label] = use_navigation()
        route = use_route()
        params = ",".join(f"{k}={v}" for k, v in sorted(route.params.items()))
        return Column(Text(label), Text(f"params:{params}"))

    return Screen


def _stateful_screen(label: str, box: Dict[str, Any]) -> Any:
    """A screen with a counter so tests can check whether state survived."""

    @component
    def Screen() -> Any:
        box[label] = use_navigation()
        count, set_count = use_state(0)
        return Column(
            Text(f"{label} count={count}"),
            Button(f"{label} inc", on_press=lambda: set_count(count + 1)),
        )

    return Screen


# ======================================================================
# Route / NavigationState (pure)
# ======================================================================


def test_route_defaults_and_key_uniqueness() -> None:
    a = Route("Home")
    b = Route("Home")
    assert a.params == {}
    assert a.key != b.key
    assert a.key.startswith("Home-")
    assert "Home" in repr(a)


def test_route_with_params_merges_and_keeps_key() -> None:
    r = Route("Detail", {"id": 1})
    merged = r.with_params({"tab": "x"})
    assert merged.params == {"id": 1, "tab": "x"}
    assert merged.key == r.key
    replaced = r.with_params({"tab": "x"}, merge=False)
    assert replaced.params == {"tab": "x"}


def test_route_round_trips_through_dict_including_nested_state() -> None:
    nested = NavigationState([Route("Profile", {"user": "ada"})])
    r = Route("Tabs", {"a": 1}, state=nested)
    restored = Route.from_dict(r.to_dict())
    assert restored == r
    assert restored.state is not None
    assert restored.state.current.name == "Profile"
    assert restored.state.current.params == {"user": "ada"}


def test_navigation_state_requires_a_route_and_valid_index() -> None:
    with pytest.raises(ValueError):
        NavigationState([])
    with pytest.raises(IndexError):
        NavigationState([Route("A")], index=3)


def test_navigation_state_push_pop_and_pop_to_top() -> None:
    s = NavigationState([Route("A")])
    s2 = s.push("B", {"id": 1}).push("C")
    assert [r.name for r in s2.routes] == ["A", "B", "C"]
    assert s2.current.name == "C"
    assert s2.can_go_back
    assert s2.pop().current.name == "B"
    assert s2.pop(10).current.name == "A"  # never below one route
    assert len(s2.pop_to_top()) == 1


def test_navigation_state_push_drops_forward_entries() -> None:
    s = NavigationState([Route("A"), Route("B"), Route("C")], index=0)
    s2 = s.push("D")
    assert [r.name for r in s2.routes] == ["A", "D"]


def test_navigation_state_navigate_pops_to_existing_or_pushes() -> None:
    s = NavigationState([Route("A"), Route("B", {"id": 1}), Route("C")])
    back = s.navigate("B", {"extra": True})
    assert [r.name for r in back.routes] == ["A", "B"]
    assert back.current.params == {"id": 1, "extra": True}
    assert back.current.key == s.routes[1].key
    pushed = s.navigate("D")
    assert [r.name for r in pushed.routes] == ["A", "B", "C", "D"]


def test_navigation_state_replace_uses_fresh_key() -> None:
    s = NavigationState([Route("A"), Route("B")])
    s2 = s.replace("C", {"x": 1})
    assert [r.name for r in s2.routes] == ["A", "C"]
    assert s2.current.key != s.current.key


def test_navigation_state_jump_to_and_set_params() -> None:
    s = NavigationState([Route("Home"), Route("Profile")], index=0)
    s2 = s.jump_to("Profile", {"user": "ada"})
    assert s2.index == 1
    assert s2.current.params == {"user": "ada"}
    assert s2.routes[1].key == s.routes[1].key  # same visit
    with pytest.raises(KeyError):
        s.jump_to("Missing")
    s3 = s.set_params({"q": 1})
    assert s3.current.params == {"q": 1}


def test_navigation_state_serialization_round_trip() -> None:
    s = NavigationState([Route("A"), Route("B", {"id": 2})], index=1)
    d = s.to_dict()
    assert d["index"] == 1
    assert [r["name"] for r in d["routes"]] == ["A", "B"]
    assert NavigationState.from_dict(d) == s


# ======================================================================
# ScreenDef
# ======================================================================


def test_screen_def_static_and_callable_options() -> None:
    static = ScreenDef("Home", lambda: None, options={"title": "Home"}, header_shown=False)
    assert static.resolve_options(Route("Home")) == {"title": "Home", "header_shown": False}

    dynamic = ScreenDef("Detail", lambda: None, options=lambda route: {"title": f"Item {route.params['id']}"})
    assert dynamic.resolve_options(Route("Detail", {"id": 7}))["title"] == "Item 7"
    assert "Detail" in repr(dynamic)


def test_screen_def_initial_params() -> None:
    s = ScreenDef("Detail", lambda: None, initial_params={"id": 0})
    assert s.initial_params == {"id": 0}
    assert ScreenDef("Home", lambda: None).initial_params == {}


# ======================================================================
# NavigatorCore (no rendering)
# ======================================================================


class _Recorder:
    """Stands in for the ``use_state`` setter: records committed states."""

    def __init__(self, state: NavigationState) -> None:
        self.state = state
        self.commits: List[NavigationState] = []

    def __call__(self, new_state: Any) -> None:
        self.state = new_state(self.state) if callable(new_state) else new_state
        self.commits.append(self.state)


def _make_core(kind: str, *names: str, parent: Any = None, host: Any = None) -> "tuple[NavigatorCore, _Recorder]":
    screens = {n: ScreenDef(n, lambda: None) for n in names}
    if kind == "stack":
        state = NavigationState([Route(names[0])])
    else:
        state = NavigationState([Route(n) for n in names], 0)
    rec = _Recorder(state)
    core = NavigatorCore(kind, screens, state, rec, parent, host)  # type: ignore[arg-type]
    return core, rec


def _sync(core: NavigatorCore, rec: _Recorder) -> None:
    """Mimic the owning component re-rendering with the committed state."""
    core.update(core.screens, rec.state, rec, core.parent, core.host)


def test_core_stack_push_navigate_pop() -> None:
    core, rec = _make_core("stack", "Home", "Detail")
    home = core.handle_for(core.state.current)
    home.navigate("Detail", id=3)
    _sync(core, rec)
    assert [r.name for r in core.state.routes] == ["Home", "Detail"]
    assert core.state.current.params == {"id": 3}

    detail = core.handle_for(core.state.current)
    assert detail.can_go_back()
    assert detail.pop() is True
    _sync(core, rec)
    assert core.state.current.name == "Home"
    assert home.pop() is False  # nothing to pop, no parent


def test_core_stack_navigate_to_existing_pops_back() -> None:
    core, rec = _make_core("stack", "A", "B", "C")
    h = core.handle_for(core.state.current)
    h.push("B")
    _sync(core, rec)
    h.push("C")
    _sync(core, rec)
    h.navigate("A", flag=True)
    _sync(core, rec)
    assert [r.name for r in core.state.routes] == ["A"]
    assert core.state.current.params == {"flag": True}


def test_core_navigate_same_route_only_updates_params() -> None:
    core, rec = _make_core("stack", "A", "B")
    h = core.handle_for(core.state.current)
    key = core.state.current.key
    h.navigate("A")
    assert rec.commits == []  # no-op
    h.navigate("A", x=1)
    _sync(core, rec)
    assert core.state.current.key == key
    assert core.state.current.params == {"x": 1}


def test_core_unknown_route_raises_without_parent() -> None:
    core, _ = _make_core("stack", "A")
    with pytest.raises(ValueError, match="Unknown route"):
        core.handle_for(core.state.current).navigate("Nope")


def test_core_replace_reset_set_params_pop_to_top() -> None:
    core, rec = _make_core("stack", "A", "B", "C")
    h = core.handle_for(core.state.current)
    h.push("B")
    _sync(core, rec)
    h.replace("C", id=9)
    _sync(core, rec)
    assert [r.name for r in core.state.routes] == ["A", "C"]
    assert core.state.current.params == {"id": 9}

    top = core.handle_for(core.state.current)
    top.set_params(more=True)
    _sync(core, rec)
    assert core.state.current.params == {"id": 9, "more": True}

    top.push("B")
    _sync(core, rec)
    core.handle_for(core.state.current).pop_to_top()
    _sync(core, rec)
    assert [r.name for r in core.state.routes] == ["A"]

    core.handle_for(core.state.current).reset(Route("B"), Route("C", {"z": 1}), index=0)
    _sync(core, rec)
    assert [r.name for r in core.state.routes] == ["B", "C"]
    assert core.state.index == 0

    core.handle_for(core.state.current).reset("A", q=2)
    _sync(core, rec)
    assert core.state.current.name == "A"
    assert core.state.current.params == {"q": 2}


def test_core_reset_validates_routes_and_arguments() -> None:
    core, _ = _make_core("stack", "A")
    h = core.handle_for(core.state.current)
    with pytest.raises(ValueError, match="Unknown route"):
        h.reset("Nope")
    with pytest.raises(TypeError):
        h.reset()
    with pytest.raises(TypeError):
        h.reset(Route("A"), Route("A"), q=1)


def test_core_push_merges_initial_params() -> None:
    screens = {
        "A": ScreenDef("A", lambda: None),
        "B": ScreenDef("B", lambda: None, initial_params={"id": 0, "tab": "x"}),
    }
    rec = _Recorder(NavigationState([Route("A")]))
    core = NavigatorCore("stack", screens, rec.state, rec)
    core.handle_for(core.state.current).push("B", id=5)
    _sync(core, rec)
    assert core.state.current.params == {"id": 5, "tab": "x"}


def test_core_before_remove_can_prevent_pop() -> None:
    core, rec = _make_core("stack", "A", "B")
    core.handle_for(core.state.current).push("B")
    _sync(core, rec)
    b = core.handle_for(core.state.current)
    seen: List[str] = []

    def guard(evt: NavigationEvent) -> None:
        seen.append(evt.data["action"])
        evt.prevent_default()

    unsub = b.add_listener("before_remove", guard)
    assert b.go_back() is True  # handled (prevented)
    assert core.state.current.name == "B"
    assert seen == ["go_back"]

    unsub()
    assert b.pop() is True
    _sync(core, rec)
    assert core.state.current.name == "A"


def test_core_set_options_merges_and_requests_render() -> None:
    renders: List[int] = []
    screens = {"A": ScreenDef("A", lambda: None, title="Static")}
    rec = _Recorder(NavigationState([Route("A")]))
    core = NavigatorCore("stack", screens, rec.state, rec, request_render=lambda: renders.append(1))
    h = core.handle_for(core.state.current)
    assert h.get_options()["title"] == "Static"
    h.set_options(title="Dynamic", header_shown=False)
    assert h.get_options() == {"title": "Dynamic", "header_shown": False}
    assert renders == [1]
    h.set_options(title="Dynamic")  # unchanged: no re-render
    assert renders == [1]


def test_core_tab_and_drawer_handles() -> None:
    core, rec = _make_core("tab", "Home", "Profile")
    h = core.handle_for(core.state.current)
    assert isinstance(h, TabNavigation)
    h.jump_to("Profile", user="ada")
    _sync(core, rec)
    assert core.state.index == 1
    assert core.state.current.params == {"user": "ada"}
    assert h.pop() is False
    assert not h.can_go_back()

    dcore, _ = _make_core("drawer", "Feed", "Settings")
    dh = dcore.handle_for(dcore.state.current)
    assert isinstance(dh, DrawerNavigation)
    opened: List[bool] = []
    dcore._set_drawer_open = opened.append
    dh.open_drawer()
    dh.close_drawer()
    dcore.drawer_open = False
    dh.toggle_drawer()
    assert opened == [True, False, True]


def test_core_forwards_unknown_routes_and_pops_to_parent() -> None:
    parent_core, parent_rec = _make_core("stack", "Root", "Other")
    parent_handle = parent_core.handle_for(parent_core.state.current)
    parent_core.handle_for(parent_core.state.current).push("Other")
    _sync(parent_core, parent_rec)
    parent_handle = parent_core.handle_for(parent_core.state.current)

    child_core, child_rec = _make_core("tab", "Feed", "Search", parent=parent_handle)
    child = child_core.handle_for(child_core.state.current)
    assert child.get_parent() is parent_handle
    assert child.can_go_back()  # parent stack can pop

    child.navigate("Root")
    _sync(parent_core, parent_rec)
    assert parent_core.state.current.name == "Root"

    with pytest.raises(ValueError):
        child.navigate("Nowhere")


def test_core_native_root_delegates_to_host() -> None:
    host = FakeHost()
    screens = {"A": ScreenDef("A", lambda: None), "B": ScreenDef("B", lambda: None, title="Bee")}
    rec = _Recorder(NavigationState([Route("A")]))
    core = NavigatorCore("stack", screens, rec.state, rec, host=host)
    assert core.is_native_root
    h = core.handle_for(core.state.current)

    h.push("B", id=1)
    assert rec.commits == []  # state lives on the pushed native screen
    state, options = host.pushed[0]
    assert [r["name"] for r in state["routes"]] == ["A", "B"]
    assert state["routes"][1]["params"] == {"id": 1}
    assert options["title"] == "Bee"

    h.replace("B")
    assert host.replaced[0][0]["routes"][0]["name"] == "B"

    h.reset(Route("B"))
    assert host.resets[0][1]["title"] == "Bee"

    two = NavigatorCore("stack", screens, NavigationState([Route("A"), Route("B")]), rec, host=host)
    assert two.handle_for(two.state.current).pop() is True
    assert host.popped == [1]
    two.handle_for(two.state.current).navigate("A")
    assert host.popped == [1, 1]


# ======================================================================
# Stack navigator (rendered)
# ======================================================================


def test_stack_renders_initial_screen_with_header() -> None:
    Stack = create_stack_navigator()
    result = render(
        NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", _screen("HOME"), title="Welcome"),
                Stack.Screen("Detail", _screen("DETAIL")),
            )
        )
    )
    assert result.get_by_text("HOME")
    assert result.get_by_text("Welcome")  # header title
    assert result.query_by_text("DETAIL") is None
    assert result.query_by_label("Back") is None


def test_stack_respects_initial_route_and_initial_params() -> None:
    Stack = create_stack_navigator()
    result = render(
        Stack.Navigator(
            Stack.Screen("Home", _screen("HOME")),
            Stack.Screen("Detail", _screen("DETAIL"), initial_params={"id": 7}),
            initial_route="Detail",
        )
    )
    assert result.get_by_text("DETAIL")
    assert result.get_by_text("params:id=7")
    assert result.get_by_text("Detail")  # falls back to route name for the title


def test_stack_navigate_back_and_state_preservation() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("Home", _stateful_screen("home", box)),
            Stack.Screen("Detail", _capturing_screen("detail", box), title="Detail"),
        )
    )
    result.press(result.get_by_text("home inc"))
    assert result.get_by_text("home count=1")

    box["home"].navigate("Detail", id=42)
    result.settle()
    assert result.get_by_text("detail")
    assert result.get_by_text("params:id=42")
    assert result.query_by_text("home count=1") is None  # hidden below
    assert result.get_by_text("home count=1", hidden=True)

    result.press(result.get_by_label("Back"))
    assert result.get_by_text("home count=1")  # state survived the round trip
    assert result.query_by_text("detail") is None
    assert result.query_by_text("detail", hidden=True) is None  # unmounted


def test_stack_replace_resets_screen_state_and_pop_to_top() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("A", _stateful_screen("a", box)),
            Stack.Screen("B", _stateful_screen("b", box)),
            Stack.Screen("C", _stateful_screen("c", box)),
        )
    )
    box["a"].push("B")
    result.settle()
    result.press(result.get_by_text("b inc"))
    assert result.get_by_text("b count=1")

    box["b"].replace("B")
    result.settle()
    assert result.get_by_text("b count=0")  # fresh key, fresh state
    assert box["b"].get_state().routes[0].name == "A"

    box["b"].push("C")
    result.settle()
    assert result.get_by_text("c count=0")
    box["c"].pop_to_top()
    result.settle()
    assert result.get_by_text("a count=0")
    assert len(box["a"].get_state()) == 1


def test_stack_system_back_pops_and_reports_consumption() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("A", _capturing_screen("a", box)),
            Stack.Screen("B", _capturing_screen("b", box)),
        )
    )
    assert result.back() is False  # at root, nothing to pop
    box["a"].push("B")
    result.settle()
    assert result.get_by_text("b")
    assert result.back() is True
    assert result.get_by_text("a")


def test_stack_header_options_callable_set_options_and_hidden_header() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("Home", _capturing_screen("home", box), header_shown=False),
            Stack.Screen(
                "Detail",
                _capturing_screen("detail", box),
                options=lambda route: {"title": f"Item {route.params['id']}", "header_back_title": "Home"},
            ),
        )
    )
    assert result.query_by_text("Home") is None  # header hidden
    box["home"].navigate("Detail", id=5)
    result.settle()
    assert result.get_by_text("Item 5")
    assert result.get_by_text("\u2039 Home")

    box["detail"].set_options(title="Edited")
    result.settle()
    assert result.get_by_text("Edited")
    assert result.query_by_text("Item 5") is None


def test_stack_header_slots_and_custom_left() -> None:
    Stack = create_stack_navigator()
    right = Text("RIGHT")
    result = render(
        Stack.Navigator(
            Stack.Screen(
                "Home",
                _screen("HOME"),
                header_right=lambda: right,
                header_left=Text("LEFT"),
            ),
        )
    )
    assert result.get_by_text("RIGHT")
    assert result.get_by_text("LEFT")


def test_stack_empty_navigator_renders_placeholder() -> None:
    Stack = create_stack_navigator()
    result = render(Stack.Navigator())
    assert result.root is not None
    assert result.text() == []


def test_stack_unknown_navigate_raises_from_handler() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    render(Stack.Navigator(Stack.Screen("Home", _capturing_screen("home", box))))
    with pytest.raises(ValueError, match="Unknown route"):
        box["home"].navigate("Nope")


# ======================================================================
# Stack navigator as native root (FakeHost)
# ======================================================================


def test_native_root_stack_pushes_to_host_and_syncs_options() -> None:
    Stack = create_stack_navigator()
    host = FakeHost()
    box: Dict[str, Any] = {}
    result = render(
        NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", _capturing_screen("home", box), title="Home!"),
                Stack.Screen("Detail", _capturing_screen("detail", box), title="Detail!"),
            )
        ),
        host=host,
    )
    assert host.title == "Home!"
    assert result.query_by_label("Back") is None  # host draws the nav bar

    box["home"].navigate("Detail", id=1)
    result.settle()
    assert result.get_by_text("home")  # this screen is unchanged
    assert result.query_by_text("detail") is None
    state, options = host.pushed[0]
    assert [r["name"] for r in state["routes"]] == ["Home", "Detail"]
    assert options["title"] == "Detail!"


def test_native_root_stack_boots_from_host_state_and_pops_via_host() -> None:
    Stack = create_stack_navigator()
    pushed_state = NavigationState([Route("Home"), Route("Detail", {"id": 9})]).to_dict()
    host = FakeHost(initial_state=pushed_state)
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("Home", _capturing_screen("home", box)),
            Stack.Screen("Detail", _capturing_screen("detail", box)),
        ),
        host=host,
    )
    assert result.get_by_text("detail")
    assert result.get_by_text("params:id=9")
    assert box["detail"].can_go_back()
    assert box["detail"].get_state().routes[0].name == "Home"

    box["detail"].go_back()
    result.settle()
    assert host.popped == [1]
    assert result.get_by_text("detail")  # host removes the screen, not Python


def test_native_root_stack_ignores_host_state_with_unknown_routes() -> None:
    Stack = create_stack_navigator()
    host = FakeHost(initial_state=NavigationState([Route("Ghost")]).to_dict())
    result = render(Stack.Navigator(Stack.Screen("Home", _screen("HOME"))), host=host)
    assert result.get_by_text("HOME")


def test_native_root_stack_before_remove_blocks_system_back() -> None:
    Stack = create_stack_navigator()
    host = FakeHost(initial_state=NavigationState([Route("Home"), Route("Form")]).to_dict())
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("Home", _capturing_screen("home", box)),
            Stack.Screen("Form", _capturing_screen("form", box)),
        ),
        host=host,
    )
    box["form"].add_listener("before_remove", lambda e: e.prevent_default())
    assert result.back() is True  # consumed: host must not pop
    assert host.popped == []


def test_native_host_focus_drives_use_is_focused() -> None:
    Stack = create_stack_navigator()
    host = FakeHost()
    focus_log: List[bool] = []

    @component
    def Home() -> Any:
        focused = use_is_focused()
        focus_log.append(focused)
        return Text("focused" if focused else "blurred")

    result = render(Stack.Navigator(Stack.Screen("Home", Home)), host=host)
    assert result.get_by_text("focused")
    host.set_focused(False)
    result.settle()
    assert result.get_by_text("blurred")
    host.set_focused(True)
    result.settle()
    assert result.get_by_text("focused")


# ======================================================================
# Tab navigator
# ======================================================================


def test_tab_renders_tab_bar_items_with_icons_and_badges() -> None:
    Tab = create_tab_navigator()
    result = render(
        Tab.Navigator(
            Tab.Screen("Home", _screen("HOME"), title="Home", tab_bar_icon="house.fill"),
            Tab.Screen("Alerts", _screen("ALERTS"), tab_bar_label="Inbox", tab_bar_badge=3),
        )
    )
    bar = result.get_by_type("TabBar")
    assert bar.props["active_tab"] == "Home"
    assert bar.props["items"] == [
        {"name": "Home", "title": "Home", "icon": "house.fill"},
        {"name": "Alerts", "title": "Inbox", "badge": "3"},
    ]
    assert result.get_by_text("HOME")
    assert result.query_by_text("ALERTS", hidden=True) is None  # lazy: not mounted yet


def test_tab_select_switches_and_keeps_visited_tabs_alive() -> None:
    Tab = create_tab_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Tab.Navigator(
            Tab.Screen("Home", _stateful_screen("home", box)),
            Tab.Screen("Profile", _stateful_screen("profile", box)),
        )
    )
    result.press(result.get_by_text("home inc"))
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "Profile")
    assert result.get_by_text("profile count=0")
    assert result.query_by_text("home count=1") is None
    assert result.get_by_text("home count=1", hidden=True)  # kept alive
    assert result.get_by_type("TabBar").props["active_tab"] == "Profile"

    box["profile"].jump_to("Home")
    result.settle()
    assert result.get_by_text("home count=1")
    assert result.get_by_text("profile count=0", hidden=True)


def test_tab_lazy_false_mounts_eagerly_and_unmount_on_blur_tears_down() -> None:
    Tab = create_tab_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Tab.Navigator(
            Tab.Screen("A", _stateful_screen("a", box)),
            Tab.Screen("B", _stateful_screen("b", box), lazy=False),
            Tab.Screen("C", _stateful_screen("c", box), unmount_on_blur=True),
        )
    )
    assert result.get_by_text("b count=0", hidden=True)  # eager
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "C")
    result.press(result.get_by_text("c inc"))
    assert result.get_by_text("c count=1")
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "A")
    assert result.query_by_text("c count=1", hidden=True) is None
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "C")
    assert result.get_by_text("c count=0")  # remounted fresh


def test_tab_initial_route_and_empty() -> None:
    Tab = create_tab_navigator()
    result = render(Tab.Navigator(Tab.Screen("A", _screen("A!")), Tab.Screen("B", _screen("B!")), initial_route="B"))
    assert result.get_by_text("B!")
    assert result.get_by_type("TabBar").props["active_tab"] == "B"
    assert render(Tab.Navigator()).text() == []


# ======================================================================
# Drawer navigator
# ======================================================================


def test_drawer_open_select_close_and_back() -> None:
    Drawer = create_drawer_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Drawer.Navigator(
            Drawer.Screen("Feed", _stateful_screen("feed", box), title="My Feed"),
            Drawer.Screen("Settings", _stateful_screen("settings", box)),
        )
    )
    nav = box["feed"]
    assert isinstance(nav, DrawerNavigation)
    assert not nav.is_drawer_open()
    assert result.query_by_text("My Feed") is None

    nav.open_drawer()
    result.settle()
    assert nav.is_drawer_open()
    assert result.get_by_text("My Feed")
    assert result.get_by_text("Settings")

    result.press(result.get_by_text("Settings").parent)
    assert result.get_by_text("settings count=0")
    assert not nav.is_drawer_open()
    assert result.query_by_text("My Feed") is None  # closed on select
    assert result.get_by_text("feed count=0", hidden=True)  # kept alive

    box["settings"].toggle_drawer()
    result.settle()
    assert result.get_by_text("My Feed")
    assert result.back() is True  # back closes the drawer first
    assert result.query_by_text("My Feed") is None
    assert result.back() is False

    box["settings"].jump_to("Feed")
    result.settle()
    assert result.get_by_text("feed count=0")


def test_drawer_empty_renders_placeholder() -> None:
    Drawer = create_drawer_navigator()
    assert render(Drawer.Navigator()).text() == []


# ======================================================================
# Hooks
# ======================================================================


def test_use_navigation_outside_navigator_raises() -> None:
    @component
    def Lonely() -> Any:
        use_navigation()
        return Text("x")

    with pytest.raises(RuntimeError, match="outside a navigator"):
        render(Lonely())


def test_use_route_outside_navigator_returns_placeholder() -> None:
    hook = render_hook(use_route)
    assert hook.current.name == "__root__"
    assert hook.current.params == {}


class _DetailParams(TypedDict):
    id: int
    title: NotRequired[str]


def test_use_route_with_params_type_returns_typed_route() -> None:
    Stack = create_stack_navigator()
    seen: List[Route[_DetailParams]] = []

    @component
    def Detail() -> Any:
        route = use_route(_DetailParams)
        seen.append(route)
        return Text(f"id={route.params['id']}")

    result = render(
        Stack.Navigator(
            Stack.Screen("Detail", Detail, initial_params={"id": 7}),
        )
    )
    assert result.get_by_text("id=7")
    assert seen[-1].params == {"id": 7}


def test_use_route_with_params_type_reports_missing_required_keys() -> None:
    Stack = create_stack_navigator()

    @component
    def Detail() -> Any:
        route = use_route(_DetailParams)
        return Text(str(route.params))

    with pytest.raises(TypeError, match=r"missing required params \['id'\] declared by _DetailParams"):
        render(Stack.Navigator(Stack.Screen("Detail", Detail, initial_params={"title": "x"})))


def test_use_route_with_params_type_skips_validation_outside_navigator() -> None:
    hook = render_hook(lambda: use_route(_DetailParams))
    assert hook.current.name == "__root__"


def test_use_is_focused_defaults_true_outside_navigator() -> None:
    assert render_hook(use_is_focused).current is True


def test_use_focus_effect_runs_on_focus_and_cleans_up_on_blur() -> None:
    Tab = create_tab_navigator()
    log: List[str] = []

    @component
    def Home() -> Any:
        def effect() -> Any:
            log.append("focus")
            return lambda: log.append("blur")

        use_focus_effect(effect, [])
        return Text("home")

    result = render(Tab.Navigator(Tab.Screen("Home", Home), Tab.Screen("Other", _screen("OTHER"))))
    assert log == ["focus"]
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "Other")
    assert log == ["focus", "blur"]
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "Home")
    assert log == ["focus", "blur", "focus"]


def test_use_focus_effect_without_deps_reruns_each_focused_render() -> None:
    runs: List[int] = []

    @component
    def Comp() -> Any:
        count, set_count = use_state(0)
        use_focus_effect(lambda: runs.append(count))
        return Button("go", on_press=lambda: set_count(count + 1))

    result = render(Comp())
    result.press(result.get_by_text("go"))
    assert runs == [0, 1]


def test_navigation_listeners_focus_blur_state_and_unsubscribe() -> None:
    Tab = create_tab_navigator()
    box: Dict[str, Any] = {}
    events: List[str] = []

    @component
    def Home() -> Any:
        nav = use_navigation()
        box["home"] = nav

        def subscribe() -> Any:
            unsub_focus = nav.add_listener("focus", lambda e: events.append(f"focus:{e.route.name}"))
            unsub_blur = nav.add_listener("blur", lambda e: events.append(f"blur:{e.route.name}"))

            def both() -> None:
                unsub_focus()
                unsub_blur()

            return both

        use_effect(subscribe, [])
        return Text("home")

    result = render(Tab.Navigator(Tab.Screen("Home", Home), Tab.Screen("Other", _screen("OTHER"))))
    assert events == ["focus:Home"]
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "Other")
    assert events == ["focus:Home", "blur:Home"]

    states: List[NavigationState] = []
    unsub = box["home"].add_listener("state", lambda e: states.append(e.data["state"]))
    box["home"].jump_to("Home")
    result.settle()
    assert events[-1] == "focus:Home"
    assert states and states[-1].current.name == "Home"
    unsub()
    result.fire(result.get_by_type("TabBar"), "on_tab_select", "Other")
    assert len(states) == 1


def test_navigation_handle_introspection() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    result = render(
        Stack.Navigator(
            Stack.Screen("Home", _capturing_screen("home", box), title="H"),
            Stack.Screen("Detail", _capturing_screen("detail", box)),
        )
    )
    home: Navigation = box["home"]
    assert home.kind == "stack"
    assert home.route.name == "Home"
    assert home.get_params() == {}
    assert home.get_options()["title"] == "H"
    assert home.get_parent() is None
    assert home.is_focused()
    assert "stack" in repr(home) and "Home" in repr(home)

    home.push("Detail", id=1)
    result.settle()
    assert not home.is_focused()
    assert box["detail"].is_focused()
    assert box["detail"].get_params() == {"id": 1}
    assert use_route  # imported symbol is the public hook
    assert box["detail"].route.params == {"id": 1}


# ======================================================================
# Nesting
# ======================================================================


def _nested_app(box: Dict[str, Any], **container_kwargs: Any) -> Any:
    Root = create_stack_navigator()
    Tabs = create_tab_navigator()
    Feed = create_stack_navigator()

    @component
    def FeedStack() -> Any:
        return Feed.Navigator(
            Feed.Screen("List", _stateful_screen("list", box)),
            Feed.Screen("Post", _capturing_screen("post", box)),
        )

    @component
    def TabsScreen() -> Any:
        return Tabs.Navigator(
            Tabs.Screen("FeedTab", FeedStack),
            Tabs.Screen("Profile", _capturing_screen("profile", box)),
        )

    return NavigationContainer(
        Root.Navigator(
            Root.Screen("Tabs", TabsScreen, header_shown=False),
            Root.Screen("Login", _capturing_screen("login", box)),
        ),
        **container_kwargs,
    )


def test_nested_navigate_bubbles_to_ancestor_and_pop_falls_through() -> None:
    box: Dict[str, Any] = {}
    result = render(_nested_app(box))
    assert result.get_by_text("list count=0")

    # Unknown in Feed stack and Tabs: bubbles to the root stack.
    box["list"].navigate("Login")
    result.settle()
    assert result.get_by_text("login")
    assert box["list"].get_parent() is not None
    assert box["login"].get_state().routes[0].name == "Tabs"

    assert result.back() is True
    assert result.get_by_text("list count=0")

    # Inner stack pop at its root falls through to the outer stack (nothing above: False).
    assert box["list"].pop() is False
    box["list"].push("Post", id=3)
    result.settle()
    assert result.get_by_text("params:id=3")
    assert box["post"].can_go_back()
    box["post"].pop()
    result.settle()
    assert result.get_by_text("list count=0")


def test_nested_navigate_with_screen_seeds_child_navigators() -> None:
    box: Dict[str, Any] = {}
    result = render(_nested_app(box))
    box["list"].navigate("Login")
    result.settle()
    box["login"].navigate("Tabs", screen="Profile", user="ada")
    result.settle()
    assert result.get_by_text("profile")
    assert result.get_by_text("params:user=ada")
    assert result.get_by_type("TabBar").props["active_tab"] == "Profile"


def test_deep_link_into_nested_stack_keeps_initial_route_beneath() -> None:
    box: Dict[str, Any] = {}
    initial = NavigationState(
        [Route("Tabs", state=NavigationState([Route("FeedTab", state=NavigationState([Route("Post", {"id": 8})]))]))]
    )
    result = render(_nested_app(box, initial_state=initial))
    assert result.get_by_text("params:id=8")
    assert box["post"].can_go_back()
    box["post"].go_back()
    result.settle()
    assert result.get_by_text("list count=0")


# ======================================================================
# NavigationContainer
# ======================================================================


def test_container_reports_state_changes_and_ready() -> None:
    Stack = create_stack_navigator()
    box: Dict[str, Any] = {}
    states: List[NavigationState] = []
    ready: List[bool] = []
    result = render(
        NavigationContainer(
            Stack.Navigator(
                Stack.Screen("A", _capturing_screen("a", box)),
                Stack.Screen("B", _capturing_screen("b", box)),
            ),
            on_state_change=states.append,
            on_ready=lambda: ready.append(True),
        )
    )
    assert ready == [True]
    assert states and states[-1].current.name == "A"
    box["a"].push("B")
    result.settle()
    assert states[-1].current.name == "B"
    assert NavigationState.from_dict(states[-1].to_dict()) == states[-1]


def test_container_initial_state_accepts_dict() -> None:
    Stack = create_stack_navigator()
    saved = NavigationState([Route("A"), Route("B", {"id": 2})]).to_dict()
    result = render(
        NavigationContainer(
            Stack.Navigator(Stack.Screen("A", _screen("A!")), Stack.Screen("B", _screen("B!"))),
            initial_state=saved,
        )
    )
    assert result.get_by_text("B!")
    assert result.get_by_text("params:id=2")
    assert result.get_by_label("Back")


def test_container_wraps_arbitrary_children() -> None:
    result = render(NavigationContainer(Text("alone")))
    assert result.get_by_text("alone")


# ======================================================================
# Linking
# ======================================================================


def _linking() -> LinkingConfig:
    return LinkingConfig(
        prefixes=["myapp://", "https://example.com"],
        screens={
            "Home": "",
            "Detail": {"path": "item/:id", "parse": {"id": int}},
            "Tabs": {
                "path": "tabs",
                "screens": {"Feed": "feed", "Profile": {"path": "u/:user"}},
            },
        },
    )


def test_linking_strip_prefix_variants() -> None:
    cfg = _linking()
    assert cfg.strip_prefix("myapp://item/1") == "item/1"
    assert cfg.strip_prefix("MYAPP://item/1") == "item/1"
    assert cfg.strip_prefix("https://example.com/item/1") == "/item/1"
    assert cfg.strip_prefix("https://example.com") == ""
    assert cfg.strip_prefix("https://example.com?x=1") == "?x=1"
    assert cfg.strip_prefix("https://other.com/item/1") is None
    assert cfg.strip_prefix("/item/1") == "/item/1"  # bare paths pass through


def test_linking_state_from_url_flat_nested_and_query() -> None:
    cfg = _linking()
    home = cfg.state_from_url("myapp://")
    assert home is not None and home.current.name == "Home"

    detail = cfg.state_from_url("https://example.com/item/42?ref=mail")
    assert detail is not None
    assert detail.current.name == "Detail"
    assert detail.current.params == {"id": 42, "ref": "mail"}  # parsed + query

    nested = cfg.state_from_url("myapp://tabs/u/ada")
    assert nested is not None
    assert nested.current.name == "Tabs"
    assert nested.current.state is not None
    assert nested.current.state.current.name == "Profile"
    assert nested.current.state.current.params == {"user": "ada"}

    assert cfg.state_from_url("myapp://nothing/here") is None
    assert cfg.state_from_url("otherapp://item/1") is None


def test_linking_url_from_state() -> None:
    cfg = _linking()
    assert cfg.url_from_state(NavigationState([Route("Home")])) == "myapp://"
    assert cfg.url_from_state(NavigationState([Route("Detail", {"id": 3, "ref": "x"})])) == "myapp://item/3?ref=x"
    nested = NavigationState([Route("Tabs", state=NavigationState([Route("Profile", {"user": "a b"})]))])
    assert cfg.url_from_state(nested) == "myapp://tabs/u/a%20b"
    unknown = NavigationState([Route("Tabs", state=NavigationState([Route("Ghost")]))])
    assert cfg.url_from_state(unknown) == "myapp://tabs"  # deepest ancestor with a path
    assert cfg.url_from_state(NavigationState([Route("Nowhere")])) is None


def test_container_seeds_from_launch_url_and_follows_later_links(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linking_module, "_initial_url", "myapp://item/5")
    monkeypatch.setattr(linking_module, "_url_listeners", [])
    Stack = create_stack_navigator()
    result = render(
        NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", _screen("HOME")),
                Stack.Screen("Detail", _screen("DETAIL")),
            ),
            linking=_linking(),
        )
    )
    assert result.get_by_text("DETAIL")
    assert result.get_by_text("params:id=5")
    assert result.get_by_label("Back")  # Home sits beneath the deep-linked screen

    linking_module.dispatch_url("myapp://")
    result.settle()
    assert result.get_by_text("HOME")
    assert result.query_by_text("DETAIL", hidden=True) is None


# ======================================================================
# Public API
# ======================================================================


def test_navigation_exports_from_package() -> None:
    for name in (
        "NavigationContainer",
        "Navigation",
        "NavigationState",
        "Route",
        "ScreenOptions",
        "LinkingConfig",
        "create_stack_navigator",
        "create_tab_navigator",
        "create_drawer_navigator",
        "use_navigation",
        "use_route",
        "use_is_focused",
        "use_focus_effect",
    ):
        assert hasattr(pn, name), name
        assert name in pn.__all__, name
    assert pn.use_navigation is use_navigation
    assert pn.NavigationContext is NavigationContext if hasattr(pn, "NavigationContext") else True
