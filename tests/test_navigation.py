"""Tests for the navigation package: state, screens, navigator values, the core, rendering, hooks, and deep links."""

import enum
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional, Tuple

import pytest

import pythonnative as pn
from pythonnative.component import Component, component
from pythonnative.components import Button, Column, Text
from pythonnative.element import Element
from pythonnative.hooks import use_effect, use_state
from pythonnative.native_modules import linking as linking_module
from pythonnative.navigation import (
    DrawerNavigation,
    DrawerNavigator,
    Group,
    LinkTable,
    Navigation,
    NavigationContainer,
    NavigationContext,
    NavigationEvent,
    NavigationRef,
    NavigationState,
    Navigator,
    NavigatorCore,
    Route,
    Screen,
    ScreenOptions,
    StackNavigator,
    TabNavigation,
    TabNavigator,
    use_focus_effect,
    use_is_focused,
    use_navigation,
    use_route,
    use_screen_options,
)
from pythonnative.navigation.screen import flatten_screens
from pythonnative.testing import FakeHost, RenderResult, render, render_hook
from pythonnative.theme import LIGHT_THEME

# ======================================================================
# Screens
# ======================================================================

BOX: Dict[str, Navigation] = {}
"""The ``Navigation`` handle each rendered screen captured, keyed by its label."""

RENDERS: Dict[str, int] = {}
"""Render counts, keyed by screen label."""


@pytest.fixture(autouse=True)
def _reset_screens() -> Iterator[None]:
    BOX.clear()
    RENDERS.clear()
    yield
    BOX.clear()
    RENDERS.clear()


def use_screen_body(label: str, **params: Any) -> Element:
    """Capture the screen's handle, count renders, and show ``label``, a counter, and the params."""
    BOX[label] = use_navigation()
    RENDERS[label] = RENDERS.get(label, 0) + 1
    count, set_count = use_state(0)
    shown = ",".join(f"{key}={value}" for key, value in sorted(params.items()))
    return Column(
        Text(label),
        Text(f"{label} count={count}"),
        Button(f"{label} inc", on_press=lambda: set_count(count + 1)),
        Text(f"{label} params:{shown}"),
    )


def _labelled(name: str) -> Component[[]]:
    """A parameterless screen named ``name`` that renders ``name.lower()``.

    Every screen this returns shares one ``__qualname__``, so the
    navigators must tell them apart by identity.
    """

    def body() -> pn.Node:
        return use_screen_body(name.lower())

    return Component(body, display_name=name)


Home = _labelled("Home")
Login = _labelled("Login")
Settings = _labelled("Settings")
Other = _labelled("Other")
Form = _labelled("Form")
Feed = _labelled("Feed")
Compose = _labelled("Compose")
Preview = _labelled("Preview")
Plain = _labelled("Plain")
Unlisted = _labelled("Unlisted")


@component
def Detail(id: int, tab: str = "info") -> pn.Node:
    return use_screen_body("detail", id=id, tab=tab)


@component
def Post(id: int) -> pn.Node:
    return use_screen_body("post", id=id)


@component
def Profile(user: str = "me") -> pn.Node:
    return use_screen_body("profile", user=user)


@component
def A(flag: bool = False) -> pn.Node:
    return use_screen_body("a", flag=flag)


@component
def B(id: int = 0, more: bool = False) -> pn.Node:
    return use_screen_body("b", id=id, more=more)


@component
def C(id: int = 0) -> pn.Node:
    return use_screen_body("c", id=id)


@component
def D(id: int = 0) -> pn.Node:
    return use_screen_body("d", id=id)


def _names(state: NavigationState) -> List[str]:
    return [route.name for route in state.routes]


def _tabs(label: str) -> TabNavigation:
    handle = BOX[label]
    assert isinstance(handle, TabNavigation)
    return handle


def _drawer(label: str) -> DrawerNavigation:
    handle = BOX[label]
    assert isinstance(handle, DrawerNavigation)
    return handle


def _select_tab(result: RenderResult, name: str) -> None:
    result.fire(result.get_by_type("TabBar"), "on_tab_select", name)


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
    assert _names(s2) == ["A", "B", "C"]
    assert s2.current.name == "C"
    assert s2.can_go_back
    assert s2.pop().current.name == "B"
    assert s2.pop(10).current.name == "A"  # never below one route
    assert len(s2.pop_to_top()) == 1


def test_navigation_state_push_drops_forward_entries() -> None:
    s = NavigationState([Route("A"), Route("B"), Route("C")], index=0)
    assert _names(s.push("D")) == ["A", "D"]


def test_navigation_state_navigate_pops_to_existing_or_pushes() -> None:
    s = NavigationState([Route("A"), Route("B", {"id": 1}), Route("C")])
    back = s.navigate("B", {"extra": True})
    assert _names(back) == ["A", "B"]
    assert back.current.params == {"id": 1, "extra": True}
    assert back.current.key == s.routes[1].key
    assert _names(s.navigate("D")) == ["A", "B", "C", "D"]


def test_navigation_state_replace_uses_fresh_key() -> None:
    s = NavigationState([Route("A"), Route("B")])
    s2 = s.replace("C", {"x": 1})
    assert _names(s2) == ["A", "C"]
    assert s2.current.key != s.current.key


def test_navigation_state_jump_to_and_set_params() -> None:
    s = NavigationState([Route("Home"), Route("Profile")], index=0)
    s2 = s.jump_to("Profile", {"user": "ada"})
    assert s2.index == 1
    assert s2.current.params == {"user": "ada"}
    assert s2.routes[1].key == s.routes[1].key  # same visit
    with pytest.raises(KeyError):
        s.jump_to("Missing")
    assert s.set_params({"q": 1}).current.params == {"q": 1}


def test_navigation_state_serialization_round_trip() -> None:
    s = NavigationState([Route("A"), Route("B", {"id": 2})], index=1)
    d = s.to_dict()
    assert d["index"] == 1
    assert [r["name"] for r in d["routes"]] == ["A", "B"]
    assert NavigationState.from_dict(d) == s


# ======================================================================
# Screen, Group, and navigator values
# ======================================================================


def test_screen_names_default_to_the_component_and_navigator_names() -> None:
    assert Screen(Detail).name == "Detail"
    assert Screen(Detail, name="Item").name == "Item"
    assert Screen(Home).name == "Home"
    nested = StackNavigator(Home, name="Nested")
    assert Screen(nested).name == "Nested"
    assert Screen(nested).navigator is nested
    assert Screen(Home).navigator is None
    assert Screen(Detail, path="/items/{id}/").path == "items/{id}"
    assert repr(Screen(Detail)) == "Screen('Detail')"


def test_screen_rejects_bad_components_names_and_options() -> None:
    with pytest.raises(TypeError, match="@component or a navigator"):
        Screen("Home")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="needs a route name"):
        Screen(StackNavigator(Home))
    with pytest.raises(TypeError, match="Unknown screen option"):
        Screen(Home, titel="Home")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="presentation"):
        Screen(Home, presentation="sheet")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="presentation"):
        Group(Screen(Home), presentation="popover")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="animation"):
        StackNavigator(Home, screen_options=ScreenOptions(animation="zoom"))  # type: ignore[typeddict-item]
    for value in ("card", "modal", "full_screen_modal", "form_sheet", "transparent_modal"):
        assert Screen(Home, presentation=value).options["presentation"] == value


def test_screen_required_params_come_from_the_signature() -> None:
    assert Screen(Detail).required_params() == ["id"]
    assert Screen(Profile).required_params() == []
    assert Screen(StackNavigator(Home, name="N")).required_params() == []


def test_flatten_screens_expands_groups_and_rejects_duplicates() -> None:
    group = Group(Screen(Detail), Compose, presentation="modal")
    screens, group_options = flatten_screens([Home, group])
    assert [s.name for s in screens] == ["Home", "Detail", "Compose"]
    assert group_options == {"Detail": {"presentation": "modal"}, "Compose": {"presentation": "modal"}}
    assert "Detail" in repr(group)

    nested, options = flatten_screens([Group(Group(Home, title="inner"), header_shown=False)])
    assert options == {"Home": {"header_shown": False, "title": "inner"}}
    assert [s.name for s in nested] == ["Home"]

    with pytest.raises(ValueError, match=r"Duplicate screen names.*name="):
        flatten_screens([Home, Group(Home)])
    with pytest.raises(TypeError):
        flatten_screens(["Home"])  # type: ignore[list-item]
    # ``name=`` resolves the clash.
    assert [s.name for s in flatten_screens([Home, Screen(Home, name="Home2")])[0]] == ["Home", "Home2"]


def test_navigators_need_a_screen() -> None:
    with pytest.raises(ValueError, match="at least one screen"):
        StackNavigator()
    with pytest.raises(ValueError, match="at least one screen"):
        TabNavigator()
    with pytest.raises(ValueError, match="at least one screen"):
        DrawerNavigator()


def test_navigator_initial_accepts_components_and_elements_with_params() -> None:
    stack = StackNavigator(Home, Detail)
    assert (stack.initial_name, stack.initial_params) == ("Home", {})
    with_params = StackNavigator(Home, Detail, initial=Detail(id=7))
    assert with_params.initial_name == "Detail"
    assert with_params.initial_params == {"id": 7}
    assert StackNavigator(Home, Settings, initial=Settings).initial_name == "Settings"

    with pytest.raises(ValueError, match="isn't one of this navigator's screens"):
        StackNavigator(Home, initial=Unlisted())
    with pytest.raises(TypeError, match=r"requires \['id'\]"):
        StackNavigator(Detail)
    with pytest.raises(TypeError, match=r"requires \['id'\]"):
        StackNavigator(Home, Detail, initial=Detail)


def test_keep_alive_navigators_reject_screens_with_required_params() -> None:
    with pytest.raises(TypeError, match=r"TabNavigator screen 'Detail' requires \['id'\]"):
        TabNavigator(Home, Detail)
    with pytest.raises(TypeError, match=r"DrawerNavigator screen 'Post' requires \['id'\]"):
        DrawerNavigator(Home, Post)
    # The initial screen's params come from ``initial``.
    tabs = TabNavigator(Home, Detail, initial=Detail(id=1))
    assert tabs.initial_name == "Detail"
    # Stacks only need the initial screen to be parameterless.
    assert StackNavigator(Home, Detail, Post).initial_name == "Home"


def test_navigator_path_to_searches_direct_then_nested_screens() -> None:
    inner = StackNavigator(Feed, Post, name="FeedTab")
    tabs = TabNavigator(inner, Profile, name="Tabs")
    root = StackNavigator(Screen(tabs), Login)
    chain = root.path_to(Post)
    assert chain is not None
    assert [s.name for s in chain] == ["Tabs", "FeedTab", "Post"]
    direct = root.path_to(Login)
    assert direct is not None and [s.name for s in direct] == ["Login"]
    nav_chain = root.path_to(inner)
    assert nav_chain is not None and [s.name for s in nav_chain] == ["Tabs", "FeedTab"]
    assert root.path_to(Unlisted) is None
    assert "Tabs" in repr(root) and "'Tabs'" in repr(tabs)


def test_screens_with_the_same_qualified_name_resolve_by_identity() -> None:
    # Every ``_labelled`` screen shares one ``__qualname__`` (the Fast Refresh
    # fallback key); the identical component must still win, even when it
    # sits in a nested navigator and a direct screen matches by name.
    stack = StackNavigator(Home, Login, Settings, initial=Settings)
    assert stack.initial_name == "Settings"
    chain = stack.path_to(Login)
    assert chain is not None and chain[0].name == "Login"

    nested = StackNavigator(Screen(TabNavigator(Feed, Other, name="Tabs")), Login)
    chain = nested.path_to(Other)
    assert chain is not None and [s.name for s in chain] == ["Tabs", "Other"]


def test_screen_matches_a_fast_refresh_replacement_by_module_and_name() -> None:
    @component
    def Replaced() -> pn.Node:
        return None

    first = Replaced

    @component  # type: ignore[no-redef]
    def Replaced() -> pn.Node:
        return None

    assert first is not Replaced
    assert Screen(first).matches(Replaced)
    assert not Screen(first).matches(Detail)
    stack = StackNavigator(Home, first)
    chain = stack.path_to(Replaced)
    assert chain is not None and chain[0].component is first


def test_calling_a_navigator_returns_its_element() -> None:
    stack = StackNavigator(Home)
    element = stack()
    assert isinstance(element, Element)
    assert element.props["navigator"] is stack


# ======================================================================
# NavigatorCore (no rendering)
# ======================================================================


class _Recorder:
    """Stands in for the ``use_state`` setter: records committed states and render requests."""

    def __init__(self, state: NavigationState) -> None:
        self.state = state
        self.commits: List[NavigationState] = []
        self.renders = 0

    def __call__(self, new_state: Any) -> None:
        self.state = new_state(self.state) if callable(new_state) else new_state
        self.commits.append(self.state)

    def request_render(self) -> None:
        self.renders += 1


def _initial_state(navigator: Navigator) -> NavigationState:
    if navigator.kind == "stack":
        return NavigationState([Route(navigator.initial_name, navigator.initial_params)])
    names = [screen.name for screen in navigator.screens]
    return NavigationState([Route(name) for name in names], names.index(navigator.initial_name))


def _make_core(
    navigator: Navigator, parent: Optional[Navigation] = None, host: Optional[FakeHost] = None
) -> Tuple[NavigatorCore, _Recorder]:
    state = _initial_state(navigator)
    rec = _Recorder(state)
    core = NavigatorCore(navigator, state, rec, parent, host, request_render=rec.request_render)
    return core, rec


def _top(core: NavigatorCore) -> Navigation:
    return core.handle_for(core.state.current)


def test_core_stack_push_navigate_pop() -> None:
    core, _ = _make_core(StackNavigator(Home, Detail))
    home = _top(core)
    home.navigate(Detail(id=3))
    assert _names(core.state) == ["Home", "Detail"]
    assert core.state.current.params == {"id": 3}

    detail = _top(core)
    assert detail.can_go_back()
    assert detail.pop() is True
    assert core.state.current.name == "Home"
    assert home.pop() is False  # nothing to pop, no parent


def test_core_params_are_the_explicit_element_props() -> None:
    core, _ = _make_core(StackNavigator(A, B))
    _top(core).push(B())
    assert core.state.current.params == {}
    _top(core).push(B(id=5, more=True))
    assert core.state.current.params == {"id": 5, "more": True}


def test_navigating_back_merges_only_the_params_passed() -> None:
    core, _ = _make_core(StackNavigator(A, B, C))
    h = _top(core)
    h.push(B(id=5, more=True))
    h.push(C())
    # ``B(id=6)`` binds ``more=False`` from the signature, but only ``id``
    # was passed, so the existing route keeps ``more=True``.
    h.navigate(B(id=6))
    assert _names(core.state) == ["A", "B"]
    assert core.state.current.params == {"id": 6, "more": True}


def test_core_stack_navigate_to_existing_pops_back() -> None:
    core, _ = _make_core(StackNavigator(A, B, C))
    h = _top(core)
    h.push(B())
    h.push(C())
    h.navigate(A(flag=True))
    assert _names(core.state) == ["A"]
    assert core.state.current.params == {"flag": True}


def test_core_navigate_same_route_only_updates_params() -> None:
    core, rec = _make_core(StackNavigator(Home, A))
    h = _top(core)
    key = core.state.current.key
    h.navigate(Home())
    assert rec.commits == []  # no params, same route: no-op
    h.push(A())
    h.navigate(A(flag=True))
    assert _names(core.state) == ["Home", "A"]
    assert core.state.current.params == {"flag": True}
    assert core.state.routes[0].key == key


def test_core_unknown_target_raises_without_parent() -> None:
    core, _ = _make_core(StackNavigator(A))
    with pytest.raises(ValueError, match=r"Unlisted isn't a screen of this navigator tree"):
        _top(core).navigate(Unlisted())
    with pytest.raises(TypeError, match="Navigation targets are screen elements"):
        _top(core).navigate("A")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="can't carry children"):
        _top(core).navigate(Element(A, {}, [Text("child")]))


def test_core_replace_reset_set_params_pop_to_top() -> None:
    core, _ = _make_core(StackNavigator(A, B, C))
    h = _top(core)
    h.push(B())
    h.replace(C(id=9))
    assert _names(core.state) == ["A", "C"]
    assert core.state.current.params == {"id": 9}

    top = _top(core)
    top.set_params(id=10)
    assert core.state.current.params == {"id": 10}

    top.push(B())
    _top(core).pop_to_top()
    assert _names(core.state) == ["A"]

    _top(core).reset(B(), C(id=1), index=0)
    assert _names(core.state) == ["B", "C"]
    assert core.state.index == 0
    assert core.state.routes[1].params == {"id": 1}

    _top(core).reset(A(flag=True))
    assert _names(core.state) == ["A"]
    assert core.state.current.params == {"flag": True}


def test_core_reset_validates_targets_and_arguments() -> None:
    core, _ = _make_core(StackNavigator(A))
    h = _top(core)
    with pytest.raises(ValueError, match="isn't a screen of this navigator"):
        h.reset(Unlisted())
    with pytest.raises(TypeError, match="at least one screen"):
        h.reset()


def test_core_set_params_validates_against_the_signature() -> None:
    core, rec = _make_core(StackNavigator(A, C))
    _top(core).push(C(id=1))
    before = len(rec.commits)
    with pytest.raises(TypeError):
        _top(core).set_params(nope=1)
    assert len(rec.commits) == before
    assert core.state.current.params == {"id": 1}


def test_core_before_remove_can_prevent_pop() -> None:
    core, _ = _make_core(StackNavigator(A, B))
    _top(core).push(B())
    b = _top(core)
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
    assert core.state.current.name == "A"


def test_core_set_options_merges_and_requests_render() -> None:
    core, rec = _make_core(StackNavigator(Screen(A, title="Static")))
    h = _top(core)
    assert h.get_options()["title"] == "Static"
    h.set_options(title="Dynamic", header_shown=False)
    assert h.get_options() == {"title": "Dynamic", "header_shown": False}
    assert rec.renders == 1
    h.set_options(title="Dynamic")  # unchanged: no re-render
    assert rec.renders == 1
    with pytest.raises(TypeError, match="Unknown screen option"):
        h.set_options(titel="x")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="animation"):
        h.set_options(animation="zoom")  # type: ignore[arg-type]


def test_core_tab_and_drawer_handles() -> None:
    core, _ = _make_core(TabNavigator(Home, Profile))
    h = _top(core)
    assert isinstance(h, TabNavigation)
    assert h.kind == "tab"
    h.jump_to(Profile(user="ada"))
    assert core.state.index == 1
    assert core.state.current.params == {"user": "ada"}
    h.jump_to(Home)
    assert core.state.current.name == "Home"
    assert h.pop() is False
    assert not h.can_go_back()

    dcore, _ = _make_core(DrawerNavigator(Feed, Settings))
    dh = _top(dcore)
    assert isinstance(dh, DrawerNavigation)
    opened: List[bool] = []
    dcore._set_drawer_open = opened.append
    dh.open_drawer()
    dh.close_drawer()
    dcore.drawer_open = False
    dh.toggle_drawer()
    assert opened == [True, False, True]
    dh.jump_to(Settings)
    assert dcore.state.current.name == "Settings"
    assert opened[-1] is False  # jump_to closes the drawer


def test_core_forwards_unknown_targets_and_pops_to_parent() -> None:
    parent_core, _ = _make_core(StackNavigator(Home, Other))
    _top(parent_core).push(Other())
    parent_handle = _top(parent_core)

    child_core, _ = _make_core(TabNavigator(Feed, Settings), parent=parent_handle)
    child = _top(child_core)
    assert child.get_parent() is parent_handle
    assert child.can_go_back()  # parent stack can pop

    child.navigate(Home())
    assert parent_core.state.current.name == "Home"
    assert _names(parent_core.state) == ["Home"]

    with pytest.raises(ValueError, match="isn't a screen of this navigator tree"):
        child.navigate(Unlisted())


def test_core_native_root_commits_one_logical_navigation_state() -> None:
    core, rec = _make_core(StackNavigator(A, Screen(B, title="Bee")), host=FakeHost())
    assert core.is_native_root
    handle = _top(core)
    handle.push(B(id=1))
    assert _names(core.state) == ["A", "B"]
    assert core.state.current.params == {"id": 1}
    assert rec.commits
    handle.replace(B(id=2))
    assert core.state.current.params == {"id": 2}
    handle.reset(A())
    assert _names(core.state) == ["A"]


def test_core_options_layer_navigator_group_screen_then_runtime() -> None:
    navigator = StackNavigator(
        A,
        Group(Screen(B, title="Screen B"), title="Group B", presentation="modal"),
        screen_options=ScreenOptions(title="Nav", header_shown=False, animation="fade"),
    )
    core, _ = _make_core(navigator)
    _top(core).push(B())
    a, b = core.state.routes
    assert core.options_for(a) == {"title": "Nav", "header_shown": False, "animation": "fade"}
    assert core.options_for(b) == {
        "title": "Screen B",
        "header_shown": False,
        "animation": "fade",
        "presentation": "modal",
    }
    core.handle_for(b).set_options(title="Runtime", header_shown=True)
    assert core.options_for(b)["title"] == "Runtime"
    assert core.options_for(b)["header_shown"] is True
    assert core.options_for(b)["presentation"] == "modal"


def test_core_pop_to_pops_replaces_or_updates_params() -> None:
    core, _ = _make_core(StackNavigator(A, B, C, D))
    h = _top(core)
    h.push(B())
    h.push(C())
    assert _names(core.state) == ["A", "B", "C"]  # eager state
    b_key = core.state.routes[1].key

    _top(core).pop_to(B)  # a component: no params
    assert _names(core.state) == ["A", "B"]
    assert core.state.current.key == b_key
    assert core.state.current.params == {}

    _top(core).pop_to(B(id=4, more=True))  # already active: params only
    assert core.state.current.key == b_key
    assert core.state.current.params == {"id": 4, "more": True}

    _top(core).push(C())
    _top(core).pop_to(B(id=5))  # an element: its passed params merge into the existing route
    assert _names(core.state) == ["A", "B"]
    assert core.state.current.key == b_key
    assert core.state.current.params == {"id": 5, "more": True}

    _top(core).pop_to(D(id=4))  # not in history: replace
    assert _names(core.state) == ["A", "D"]
    assert core.state.current.params == {"id": 4}

    with pytest.raises(ValueError, match="isn't a screen"):
        _top(core).pop_to(Unlisted)

    tabs, _ = _make_core(TabNavigator(Home, Settings))
    _top(tabs).pop_to(Settings)  # non-stack: jump
    assert tabs.state.current.name == "Settings"


def test_core_pop_to_bubbles_to_parent() -> None:
    parent_core, _ = _make_core(StackNavigator(Home, Other))
    _top(parent_core).push(Other())
    child_core, _ = _make_core(TabNavigator(Feed), parent=_top(parent_core))
    _top(child_core).pop_to(Home)
    assert _names(parent_core.state) == ["Home"]


_REMOVALS: Dict[str, Callable[[Navigation], Any]] = {
    "pop": lambda h: h.pop(),
    "go_back": lambda h: h.go_back(),
    "pop_to_top": lambda h: h.pop_to_top(),
    "pop_to": lambda h: h.pop_to(A),
    "navigate": lambda h: h.navigate(A()),
    "replace": lambda h: h.replace(B()),
    "reset": lambda h: h.reset(A()),
}
_EXPECTED_AFTER: Dict[str, List[str]] = {
    "pop": ["A", "B"],
    "go_back": ["A", "B"],
    "pop_to_top": ["A"],
    "pop_to": ["A"],
    "navigate": ["A"],
    "replace": ["A", "B", "B"],
    "reset": ["A"],
}


@pytest.mark.parametrize("action", sorted(_REMOVALS))
@pytest.mark.parametrize("veto", [False, True])
def test_core_before_remove_fires_for_every_removal_and_veto_cancels(action: str, veto: bool) -> None:
    core, rec = _make_core(StackNavigator(A, B, C))
    root = _top(core)
    root.push(B())
    root.push(C())
    top = _top(core)
    seen: List[str] = []

    def guard(evt: NavigationEvent) -> None:
        seen.append(evt.data["action"])
        if veto:
            evt.prevent_default()

    top.add_listener("before_remove", guard)
    before = core.state
    commits = len(rec.commits)
    _REMOVALS[action](top)
    assert seen == [action]
    if veto:
        assert core.state is before
        assert len(rec.commits) == commits
    else:
        assert _names(core.state) == _EXPECTED_AFTER[action]


def test_core_veto_on_a_lower_route_cancels_the_whole_pop_to_and_orders_events_topmost_first() -> None:
    core, _ = _make_core(StackNavigator(A, B, C))
    root = _top(core)
    root.push(B())
    b = _top(core)
    root.push(C())
    c = _top(core)
    order: List[str] = []
    c.add_listener("before_remove", lambda e: order.append("C"))

    def veto_b(evt: NavigationEvent) -> None:
        order.append("B")
        evt.prevent_default()

    b.add_listener("before_remove", veto_b)
    c.pop_to(A)
    assert order == ["C", "B"]
    assert _names(core.state) == ["A", "B", "C"]
    c.navigate(A())
    assert _names(core.state) == ["A", "B", "C"]


def test_core_reset_fires_before_remove_only_for_routes_that_leave() -> None:
    core, _ = _make_core(StackNavigator(A, B))
    _top(core).push(B())
    a_route, b_route = core.state.routes
    seen: List[str] = []
    core.handle_for(a_route).add_listener("before_remove", lambda e: seen.append("A"))
    core.handle_for(b_route).add_listener("before_remove", lambda e: seen.append("B"))
    core.reset([a_route, Route("B")])  # A stays (same key), old B leaves
    assert seen == ["B"]
    assert core.state.routes[0].key == a_route.key
    assert core.state.routes[1].key != b_route.key

    # ``Navigation.reset`` builds fresh routes, so every current route leaves.
    seen.clear()
    top = _top(core)
    core.handle_for(core.state.routes[0]).add_listener("before_remove", lambda e: seen.append("A2"))
    top.add_listener("before_remove", lambda e: seen.append("B2"))
    top.reset(A(), B())
    assert seen == ["B2", "A", "A2"]  # topmost first; the kept A route still has its first listener


def test_core_commit_updates_state_eagerly_and_handles_follow() -> None:
    core, rec = _make_core(StackNavigator(A, B))
    h = _top(core)
    h.push(B())
    assert core.state.current.name == "B"
    assert h.get_state() is core.state
    assert rec.commits[-1] is core.state
    assert not h.is_focused()


# ======================================================================
# Stack navigator (rendered)
# ======================================================================


def test_stack_renders_initial_screen_with_header() -> None:
    Root = StackNavigator(Screen(Home, title="Welcome"), Detail)
    result = render(NavigationContainer(Root))
    assert result.get_by_text("home")
    assert result.get_by_text("Welcome")  # header title
    assert result.query_by_text("detail") is None
    assert result.query_by_label("Back") is None


def test_stack_renders_without_a_container() -> None:
    result = render(StackNavigator(Home)())
    assert result.get_by_text("home")
    assert result.get_by_text("Home")  # the title falls back to the route name


def test_stack_initial_screen_with_params() -> None:
    result = render(StackNavigator(Home, Detail, initial=Detail(id=7))())
    assert result.get_by_text("detail")
    assert result.get_by_text("detail params:id=7,tab=info")
    assert result.get_by_text("Detail")  # falls back to the route name for the title


def test_stack_navigate_back_and_state_preservation() -> None:
    result = render(StackNavigator(Home, Screen(Detail, title="Detail"))())
    result.press(result.get_by_text("home inc"))
    assert result.get_by_text("home count=1")

    BOX["home"].navigate(Detail(id=42))
    result.settle()
    assert result.get_by_text("detail")
    assert result.get_by_text("detail params:id=42,tab=info")
    assert result.query_by_text("home count=1") is None  # hidden below
    assert result.get_by_text("home count=1", hidden=True)

    result.press(result.get_by_label("Back"))
    assert result.get_by_text("home count=1")  # state survived the round trip
    assert result.query_by_text("detail") is None
    assert result.query_by_text("detail", hidden=True) is None  # unmounted


def test_stack_replace_resets_screen_state_and_pop_to_top() -> None:
    result = render(StackNavigator(A, B, C)())
    BOX["a"].push(B())
    result.settle()
    result.press(result.get_by_text("b inc"))
    assert result.get_by_text("b count=1")

    BOX["b"].replace(B())
    result.settle()
    assert result.get_by_text("b count=0")  # fresh key, fresh state
    assert BOX["b"].get_state().routes[0].name == "A"

    BOX["b"].push(C())
    result.settle()
    assert result.get_by_text("c count=0")
    BOX["c"].pop_to_top()
    result.settle()
    assert result.get_by_text("a count=0")
    assert len(BOX["a"].get_state()) == 1


def test_stack_system_back_pops_and_reports_consumption() -> None:
    result = render(StackNavigator(A, B)())
    assert result.back() is False  # at root, nothing to pop
    BOX["a"].push(B())
    result.settle()
    assert result.get_by_text("b")
    assert result.back() is True
    assert result.get_by_text("a")


def test_stack_header_options_set_options_and_hidden_header() -> None:
    result = render(
        StackNavigator(
            Screen(Home, header_shown=False),
            Screen(Detail, title="Detail", header_back_title="Home"),
        )()
    )
    assert result.query_by_text("Home") is None  # header hidden
    BOX["home"].navigate(Detail(id=5))
    result.settle()
    assert result.get_by_text("Detail")
    assert result.get_by_text("‹ Home")

    BOX["detail"].set_options(title="Edited")
    result.settle()
    assert result.get_by_text("Edited")
    assert result.query_by_text("Detail") is None


def test_stack_header_slots_take_elements() -> None:
    result = render(StackNavigator(Screen(Home, header_right=Text("RIGHT"), header_left=Text("LEFT")))())
    assert result.get_by_text("RIGHT")
    assert result.get_by_text("LEFT")


def test_stack_unknown_navigate_raises_from_handler() -> None:
    render(StackNavigator(Home)())
    with pytest.raises(ValueError, match="isn't a screen of this navigator tree"):
        BOX["home"].navigate(Unlisted())


def test_stack_header_uses_theme_colors() -> None:
    result = render(StackNavigator(Screen(Home, title="Themed"))())
    title = result.get_by_text("Themed")
    assert title.props["color"] == LIGHT_THEME.colors.text
    header = title.parent
    assert header is not None
    assert header.props["background_color"] == LIGHT_THEME.colors.surface


# ======================================================================
# use_screen_options, set_params, and cached screen bodies
# ======================================================================


@component
def Titled(id: int = 1) -> pn.Node:
    RENDERS["titled"] = RENDERS.get("titled", 0) + 1
    use_screen_options(title=f"Item {id}")
    BOX["titled"] = use_navigation()
    return Text(f"titled {id}")


def test_use_screen_options_sets_the_title_without_looping() -> None:
    result = render(StackNavigator(Titled)())
    assert result.get_by_text("Item 1")
    assert RENDERS["titled"] == 1  # the navigator re-render doesn't re-render the screen
    assert BOX["titled"].get_options()["title"] == "Item 1"

    BOX["titled"].set_params(id=2)
    result.settle()
    assert result.get_by_text("titled 2")
    assert result.get_by_text("Item 2")
    assert result.query_by_text("Item 1") is None
    assert RENDERS["titled"] == 2


def test_use_screen_options_with_a_fresh_header_element_each_render_settles() -> None:
    pressed: List[int] = []

    @component
    def Sharing() -> pn.Node:
        RENDERS["sharing"] = RENDERS.get("sharing", 0) + 1
        count, set_count = use_state(0)
        use_screen_options(
            title=f"Shared {count}", header_right=Button("Share", on_press=lambda: pressed.append(count))
        )
        return Button("bump", on_press=lambda: set_count(count + 1))

    result = render(StackNavigator(Sharing)())
    assert RENDERS["sharing"] == 1
    result.press(result.get_by_text("Share"))
    assert pressed == [0]
    result.press(result.get_by_text("bump"))
    assert result.get_by_text("Shared 1")
    assert RENDERS["sharing"] == 2
    result.press(result.get_by_text("Share"))
    assert pressed == [0, 1]  # the header slot follows the latest render


def test_use_screen_options_rejects_unknown_keys() -> None:
    @component
    def Bad() -> pn.Node:
        use_screen_options(titel="x")  # type: ignore[call-arg]
        return None

    with pytest.raises(TypeError, match="Unknown screen option"):
        render(StackNavigator(Bad)())


def test_use_screen_options_outside_a_navigator_raises() -> None:
    @component
    def Lonely() -> pn.Node:
        use_screen_options(title="x")
        return None

    with pytest.raises(RuntimeError, match="outside a navigator"):
        render(Lonely())


def test_set_params_re_renders_the_screen_with_new_props_and_validates() -> None:
    result = render(StackNavigator(Home, Detail)())
    BOX["home"].push(Detail(id=1))
    result.settle()
    result.press(result.get_by_text("detail inc"))
    BOX["detail"].set_params(tab="reviews")
    result.settle()
    assert result.get_by_text("detail params:id=1,tab=reviews")
    assert result.get_by_text("detail count=1")  # same route, same state
    assert BOX["detail"].route.params == {"id": 1, "tab": "reviews"}
    with pytest.raises(TypeError):
        BOX["detail"].set_params(nope=True)
    assert BOX["detail"].route.params == {"id": 1, "tab": "reviews"}


def test_navigator_re_renders_reuse_cached_screen_bodies() -> None:
    result = render(StackNavigator(Home, Screen(Other, title="Other"))())
    BOX["home"].push(Other())
    result.settle()
    home, other = RENDERS["home"], RENDERS["other"]

    # An option change re-renders the navigator (the header shows it), not the screens.
    BOX["other"].set_options(title="Renamed")
    result.settle()
    assert result.get_by_text("Renamed")
    assert (RENDERS["home"], RENDERS["other"]) == (home, other)

    # The screen's own state still renders it.
    result.press(result.get_by_text("other inc"))
    assert RENDERS["other"] == other + 1
    assert RENDERS["home"] == home


# ======================================================================
# Stack navigator as native root (FakeHost)
# ======================================================================


def _native_screens(result: RenderResult) -> List[Any]:
    return [view for view in result.views(hidden=True) if view.type_name == "Screen"]


def test_native_root_stack_renders_screens_and_syncs_options() -> None:
    Root = StackNavigator(Screen(Home, title="Home!"), Screen(Detail, title="Detail!"))
    result = render(NavigationContainer(Root), host=FakeHost())
    assert _native_screens(result)[0].props["title"] == "Home!"
    assert result.query_by_label("Back") is None  # the host draws the nav bar

    BOX["home"].navigate(Detail(id=1))
    result.settle()
    assert result.get_by_text("home", hidden=True)  # the logical state stays mounted
    assert result.get_by_text("detail")
    assert _names(BOX["detail"].get_state()) == ["Home", "Detail"]
    assert [screen.props["title"] for screen in _native_screens(result)] == ["Home!", "Detail!"]


def test_native_root_stack_boots_from_host_state_and_pops_via_host() -> None:
    pushed_state = NavigationState([Route("Home"), Route("Detail", {"id": 9})]).to_dict()
    result = render(StackNavigator(Home, Detail)(), host=FakeHost(initial_state=pushed_state))
    assert result.get_by_text("detail")
    assert result.get_by_text("detail params:id=9,tab=info")
    assert BOX["detail"].can_go_back()
    assert BOX["detail"].get_state().routes[0].name == "Home"

    BOX["detail"].go_back()
    result.settle()
    assert result.get_by_text("home")
    assert result.query_by_text("detail", hidden=True) is None


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(NavigationState([Route("Ghost")]), id="unknown-route"),
        pytest.param(NavigationState([Route("Home"), Route("Detail")]), id="missing-required-param"),
    ],
)
def test_native_root_stack_ignores_unrestorable_host_state(state: NavigationState) -> None:
    result = render(StackNavigator(Home, Detail)(), host=FakeHost(initial_state=state.to_dict()))
    assert result.get_by_text("home")
    assert result.query_by_text("detail", hidden=True) is None


def test_native_root_stack_before_remove_blocks_system_back() -> None:
    host = FakeHost(initial_state=NavigationState([Route("Home"), Route("Form")]).to_dict())
    result = render(StackNavigator(Home, Form)(), host=host)
    BOX["form"].add_listener("before_remove", lambda e: e.prevent_default())
    assert result.back() is True  # consumed: the host must not pop
    assert result.get_by_text("form")


def test_native_host_focus_drives_use_is_focused() -> None:
    host = FakeHost()

    @component
    def Focus() -> pn.Node:
        return Text("focused" if use_is_focused() else "blurred")

    result = render(StackNavigator(Focus)(), host=host)
    assert result.get_by_text("focused")
    host.set_focused(False)
    result.settle()
    assert result.get_by_text("blurred")
    host.set_focused(True)
    result.settle()
    assert result.get_by_text("focused")


@component
def OpenDetail() -> pn.Node:
    navigation = use_navigation()
    return Button("Open detail", on_press=lambda: navigation.navigate(Detail(id=1)))


def test_native_header_slots_keep_route_context_and_update_without_serializing_elements() -> None:
    result = render(StackNavigator(Screen(Home, header_right=OpenDetail()), Detail)(), host=FakeHost())
    screens = _native_screens(result)
    assert "header_right" not in screens[0].props
    slots = [view for view in result.views() if view.props.get("_pn_header_slot") == "right"]
    assert len(slots) == 1
    result.press(result.get_by_text("Open detail"))
    assert result.get_by_text("detail")
    result.unmount()


def test_native_screen_props_omit_python_only_options() -> None:
    result = render(
        StackNavigator(
            Screen(
                Home,
                header_left=Text("L"),
                tab_bar_icon="house",
                tab_bar_visible=False,
                freeze_on_blur=True,
                presentation="form_sheet",
                animation="slide_from_bottom",
            )
        )(),
        host=FakeHost(),
    )
    screen = result.get_by_type("Screen")
    for key in ("header_left", "tab_bar_icon", "tab_bar_visible", "freeze_on_blur"):
        assert key not in screen.props
    assert screen.props["presentation"] == "form_sheet"
    assert screen.props["animation"] == "slide_from_bottom"
    # Theme colors fill in the chrome defaults.
    assert screen.props["header_tint_color"] == LIGHT_THEME.colors.primary
    assert screen.props["header_style"]["background_color"] == LIGHT_THEME.colors.surface
    assert screen.props["header_title_style"]["color"] == LIGHT_THEME.colors.text


# ======================================================================
# Native back veto: restore_stack
# ======================================================================


def _native_stack(host: FakeHost) -> RenderResult:
    return render(StackNavigator(Home, Form)(), host=host)


def _restore_commands(result: RenderResult) -> List[Any]:
    return [command for command in result.backend.commands if command[1] == "restore_stack"]


def test_native_back_veto_issues_restore_stack() -> None:
    host = FakeHost(initial_state=NavigationState([Route("Home"), Route("Form")]).to_dict())
    result = _native_stack(host)
    actions: List[str] = []

    def guard(evt: NavigationEvent) -> None:
        actions.append(evt.data["action"])
        evt.prevent_default()

    BOX["form"].add_listener("before_remove", guard)
    stack = result.get_by_type("ScreenStack")
    result.fire(stack, "on_native_back", 1)
    assert actions == ["back"]
    assert result.get_by_text("form")
    assert _names(BOX["form"].get_state()) == ["Home", "Form"]
    restores = _restore_commands(result)
    assert len(restores) == 1
    assert restores[0][0] == stack.tag


def test_native_back_without_veto_pops_and_does_not_restore() -> None:
    host = FakeHost(initial_state=NavigationState([Route("Home"), Route("Form")]).to_dict())
    result = _native_stack(host)
    result.fire(result.get_by_type("ScreenStack"), "on_native_back", 1)
    assert result.get_by_text("home")
    assert result.query_by_text("form", hidden=True) is None
    assert _restore_commands(result) == []


def test_native_back_at_root_restores_stack() -> None:
    result = _native_stack(FakeHost())
    result.fire(result.get_by_type("ScreenStack"), "on_native_back", 1)
    assert result.get_by_text("home")
    assert len(_restore_commands(result)) == 1


def test_native_screen_guarded_prop_follows_before_remove_listeners() -> None:
    host = FakeHost(initial_state=NavigationState([Route("Home"), Route("Form")]).to_dict())
    result = _native_stack(host)

    def screen(name: str) -> Any:
        return next(view for view in _native_screens(result) if view.props.get("route_key", "").startswith(name))

    assert screen("Home").props["guarded"] is False
    assert screen("Form").props["guarded"] is False

    unsubscribe = BOX["form"].add_listener("before_remove", lambda e: e.prevent_default())
    result.settle()  # adding the first listener re-renders on its own
    assert screen("Form").props["guarded"] is True
    assert screen("Home").props["guarded"] is False

    second = BOX["form"].add_listener("before_remove", lambda e: None)
    unsubscribe()
    result.settle()
    assert screen("Form").props["guarded"] is True  # one listener left
    second()
    result.settle()
    assert screen("Form").props["guarded"] is False

    BOX["home"].add_listener("focus", lambda e: None)  # other events don't guard
    result.settle()
    assert screen("Home").props["guarded"] is False


# ======================================================================
# Tab navigator
# ======================================================================


def test_tab_renders_tab_bar_items_with_icons_and_badges() -> None:
    result = render(
        TabNavigator(
            Screen(Home, title="Home", tab_bar_icon="house"),
            Screen(Other, tab_bar_label="Inbox", tab_bar_badge=3),
            Screen(Profile, tab_bar_icon=pn.asset("icons/me.png")),
        )()
    )
    bar = result.get_by_type("TabBar")
    assert bar.props["active_tab"] == "Home"
    items = bar.props["items"]
    assert items[0]["name"] == "Home" and items[0]["title"] == "Home"
    assert items[0]["icon"]["view_box"] == "0 0 24 24"
    assert items[0]["icon"]["shapes"] and all(shape["kind"] == "path" for shape in items[0]["icon"]["shapes"])
    assert items[1] == {"name": "Other", "title": "Inbox", "badge": "3"}
    assert items[2]["icon"] == {"uri": "asset://icons/me.png"}
    assert result.get_by_text("home")
    assert result.query_by_text("other", hidden=True) is None  # lazy: not mounted yet


def test_tab_bar_style_and_theme_defaults() -> None:
    result = render(TabNavigator(Home, Other, tab_bar_style={"active_tint_color": "#FF0000", "show_labels": False})())
    props = result.get_by_type("TabBar").props
    assert props["tint_color"] == "#FF0000"
    assert props["shows_labels"] is False
    assert props["background_color"] == LIGHT_THEME.colors.surface

    themed = render(TabNavigator(Home)()).get_by_type("TabBar").props
    assert themed["tint_color"] == LIGHT_THEME.colors.primary


def test_tab_select_switches_and_keeps_visited_tabs_alive() -> None:
    result = render(TabNavigator(Home, Profile)())
    result.press(result.get_by_text("home inc"))
    _select_tab(result, "Profile")
    assert result.get_by_text("profile count=0")
    assert result.query_by_text("home count=1") is None
    assert result.get_by_text("home count=1", hidden=True)  # kept alive
    assert result.get_by_type("TabBar").props["active_tab"] == "Profile"

    _tabs("profile").jump_to(Home)
    result.settle()
    assert result.get_by_text("home count=1")
    assert result.get_by_text("profile count=0", hidden=True)


def test_tab_jump_to_an_element_merges_params() -> None:
    result = render(TabNavigator(Home, Profile)())
    _tabs("home").jump_to(Profile(user="ada"))
    result.settle()
    assert result.get_by_text("profile params:user=ada")


def test_tab_lazy_false_mounts_eagerly_and_unmount_on_blur_tears_down() -> None:
    result = render(TabNavigator(A, Screen(B, lazy=False), Screen(C, unmount_on_blur=True))())
    assert result.get_by_text("b count=0", hidden=True)  # eager
    _select_tab(result, "C")
    result.press(result.get_by_text("c inc"))
    assert result.get_by_text("c count=1")
    _select_tab(result, "A")
    assert result.query_by_text("c count=1", hidden=True) is None
    _select_tab(result, "C")
    assert result.get_by_text("c count=0")  # remounted fresh


def test_tab_initial_screen() -> None:
    result = render(TabNavigator(A, B, initial=B)())
    assert result.get_by_text("b")
    assert result.get_by_type("TabBar").props["active_tab"] == "B"

    with_params = render(TabNavigator(A, Detail, initial=Detail(id=4))())
    assert with_params.get_by_text("detail params:id=4,tab=info")


def test_tab_bar_visible_false_hides_the_tab_bar_while_that_tab_is_focused() -> None:
    result = render(TabNavigator(Screen(Home, tab_bar_visible=False), Other)())
    assert result.query_by_type("TabBar") is None
    _tabs("home").jump_to(Other)
    result.settle()
    assert result.get_by_type("TabBar").props["active_tab"] == "Other"
    BOX["other"].set_options(tab_bar_visible=False)
    result.settle()
    assert result.query_by_type("TabBar") is None
    BOX["other"].set_options(tab_bar_visible=True)
    result.settle()
    assert result.get_by_type("TabBar")


@component
def FrozenTab(n: int = 0) -> pn.Node:
    RENDERS["frozen"] = RENDERS.get("frozen", 0) + 1
    BOX["frozen"] = use_navigation()
    return Text(f"frozen {n}")


@component
def PlainTab(n: int = 0) -> pn.Node:
    RENDERS["plain"] = RENDERS.get("plain", 0) + 1
    BOX["plain"] = use_navigation()
    return Text(f"plain {n}")


def test_blurred_tabs_skip_navigator_re_renders() -> None:
    result = render(TabNavigator(Screen(FrozenTab, freeze_on_blur=True), Screen(PlainTab, lazy=False), Other)())
    assert (RENDERS["frozen"], RENDERS["plain"]) == (1, 1)
    _select_tab(result, "Other")
    frozen, plain = RENDERS["frozen"], RENDERS["plain"]

    # A navigator re-render reuses every cached screen body.
    BOX["other"].set_options(title="Changed")
    result.settle()
    assert (RENDERS["frozen"], RENDERS["plain"]) == (frozen, plain)
    assert result.get_by_text("frozen 0", hidden=True)  # still mounted


def test_freeze_on_blur_holds_new_params_until_focus() -> None:
    result = render(TabNavigator(Screen(FrozenTab, freeze_on_blur=True), Screen(PlainTab, lazy=False), Other)())
    _select_tab(result, "Other")
    frozen = RENDERS["frozen"]

    BOX["frozen"].set_params(n=1)
    BOX["plain"].set_params(n=1)
    result.settle()
    assert result.get_by_text("plain 1", hidden=True)  # unfrozen: renders while hidden
    assert result.get_by_text("frozen 0", hidden=True)  # frozen: keeps its last body
    assert RENDERS["frozen"] == frozen

    _select_tab(result, "FrozenTab")
    assert result.get_by_text("frozen 1")
    assert RENDERS["frozen"] == frozen + 1


# ======================================================================
# Drawer navigator
# ======================================================================


def test_drawer_open_select_close_and_back() -> None:
    result = render(DrawerNavigator(Screen(Feed, title="My Feed"), Settings, drawer_width=200)())
    nav = _drawer("feed")
    assert not nav.is_drawer_open()
    assert result.query_by_text("My Feed") is None

    nav.open_drawer()
    result.settle()
    assert nav.is_drawer_open()
    assert result.get_by_text("My Feed")
    assert result.get_by_text("Settings")
    panel = result.get_by_text("My Feed").parent
    assert panel is not None and panel.parent is not None
    assert panel.parent.props["width"] == 200

    row = result.get_by_text("Settings").parent
    assert row is not None
    result.press(row)
    assert result.get_by_text("settings count=0")
    assert not nav.is_drawer_open()
    assert result.query_by_text("My Feed") is None  # closed on select
    assert result.get_by_text("feed count=0", hidden=True)  # kept alive

    _drawer("settings").toggle_drawer()
    result.settle()
    assert result.get_by_text("My Feed")
    assert result.back() is True  # back closes the drawer first
    assert result.query_by_text("My Feed") is None
    assert result.back() is False

    _drawer("settings").jump_to(Feed)
    result.settle()
    assert result.get_by_text("feed count=0")


def test_tab_and_drawer_navigators_accept_groups_and_screen_options() -> None:
    result = render(
        TabNavigator(
            Home,
            Group(Feed, tab_bar_label="Grouped"),
            screen_options=ScreenOptions(tab_bar_badge=1),
        )()
    )
    items = result.get_by_type("TabBar").props["items"]
    assert items == [
        {"name": "Home", "title": "Home", "badge": "1"},
        {"name": "Feed", "title": "Grouped", "badge": "1"},
    ]

    result = render(DrawerNavigator(Group(Feed, title="Menu Feed"), screen_options=ScreenOptions(title="Nav"))())
    _drawer("feed").open_drawer()
    result.settle()
    assert result.get_by_text("Menu Feed")


def test_stack_navigator_screen_options_and_groups_render_layered_titles() -> None:
    result = render(
        StackNavigator(
            Screen(Home, title="Home!"),
            Group(Compose, Screen(Preview, title="Preview!"), title="Grouped"),
            Plain,
            screen_options=ScreenOptions(title="Nav"),
        )()
    )
    assert result.get_by_text("Home!")  # screen beats navigator
    BOX["home"].push(Compose())
    result.settle()
    assert result.get_by_text("Grouped")  # group beats navigator
    BOX["compose"].push(Preview())
    result.settle()
    assert result.get_by_text("Preview!")  # screen beats group
    BOX["preview"].push(Plain())
    result.settle()
    assert result.get_by_text("Nav")  # navigator options apply to ungrouped screens
    BOX["plain"].set_options(title="Runtime")
    result.settle()
    assert result.get_by_text("Runtime")
    assert BOX["plain"].get_options()["title"] == "Runtime"


# ======================================================================
# Hooks
# ======================================================================


def test_use_navigation_outside_navigator_raises() -> None:
    @component
    def Lonely() -> pn.Node:
        use_navigation()
        return Text("x")

    with pytest.raises(RuntimeError, match="outside a navigator"):
        render(Lonely())


def test_use_route_outside_navigator_returns_placeholder() -> None:
    hook = render_hook(use_route)
    assert hook.current.name == "__root__"
    assert hook.current.params == {}


def test_use_route_returns_the_screen_route() -> None:
    seen: List[Route] = []

    @component
    def Routed(id: int = 0) -> pn.Node:
        seen.append(use_route())
        return Text(f"routed {id}")

    render(StackNavigator(Routed, initial=Routed(id=7))())
    assert seen[-1].name == "Routed"
    assert seen[-1].params == {"id": 7}
    assert seen[-1].key.startswith("Routed-")


def test_use_is_focused_defaults_true_outside_navigator() -> None:
    assert render_hook(use_is_focused).current is True


def test_use_focus_effect_runs_on_focus_and_cleans_up_on_blur() -> None:
    log: List[str] = []

    @component
    def Focused() -> pn.Node:
        def effect() -> Any:
            log.append("focus")
            return lambda: log.append("blur")

        use_focus_effect(effect, [])
        return Text("focused screen")

    result = render(TabNavigator(Focused, Other)())
    assert log == ["focus"]
    _select_tab(result, "Other")
    assert log == ["focus", "blur"]
    _select_tab(result, "Focused")
    assert log == ["focus", "blur", "focus"]


def test_use_focus_effect_without_deps_reruns_each_focused_render() -> None:
    runs: List[int] = []

    @component
    def Comp() -> pn.Node:
        count, set_count = use_state(0)
        use_focus_effect(lambda: runs.append(count))
        return Button("go", on_press=lambda: set_count(count + 1))

    result = render(Comp())
    result.press(result.get_by_text("go"))
    assert runs == [0, 1]


def test_navigation_listeners_focus_blur_state_and_unsubscribe() -> None:
    events: List[str] = []

    @component
    def Listening() -> pn.Node:
        nav = use_navigation()
        BOX["listening"] = nav

        def subscribe() -> Any:
            unsub_focus = nav.add_listener("focus", lambda e: events.append(f"focus:{e.route.name}"))
            unsub_blur = nav.add_listener("blur", lambda e: events.append(f"blur:{e.route.name}"))

            def both() -> None:
                unsub_focus()
                unsub_blur()

            return both

        use_effect(subscribe, [])
        return Text("listening")

    result = render(TabNavigator(Listening, Other)())
    assert events == ["focus:Listening"]
    _select_tab(result, "Other")
    assert events == ["focus:Listening", "blur:Listening"]

    states: List[NavigationState] = []
    handle = _tabs("listening")
    unsub = handle.add_listener("state", lambda e: states.append(e.data["state"]))
    handle.jump_to(Listening)
    result.settle()
    assert events[-1] == "focus:Listening"
    assert states and states[-1].current.name == "Listening"
    unsub()
    _select_tab(result, "Other")
    assert len(states) == 1


def test_navigation_handle_introspection() -> None:
    result = render(StackNavigator(Screen(Home, title="H"), Detail)())
    home = BOX["home"]
    assert home.kind == "stack"
    assert home.route.name == "Home"
    assert home.route.params == {}
    assert home.get_options()["title"] == "H"
    assert home.get_parent() is None
    assert home.is_focused()
    assert "stack" in repr(home) and "Home" in repr(home)

    home.push(Detail(id=1))
    result.settle()
    assert not home.is_focused()
    assert BOX["detail"].is_focused()
    assert BOX["detail"].route.params == {"id": 1}


# ======================================================================
# Static nesting
# ======================================================================

FeedStack = StackNavigator(Feed, Post, name="FeedTab")
Tabs = TabNavigator(FeedStack, Profile, name="Tabs")
NestedRoot = StackNavigator(Screen(Tabs, header_shown=False), Login)


def test_nested_navigate_bubbles_to_ancestor_and_pop_falls_through() -> None:
    result = render(NavigationContainer(NestedRoot))
    assert result.get_by_text("feed count=0")

    # Unknown in the feed stack and the tabs: bubbles to the root stack.
    BOX["feed"].navigate(Login())
    result.settle()
    assert result.get_by_text("login")
    assert BOX["feed"].get_parent() is not None
    assert BOX["login"].get_state().routes[0].name == "Tabs"

    assert result.back() is True
    assert result.get_by_text("feed count=0")

    # An inner stack's pop at its root falls through to the outer stack (nothing above: False).
    assert BOX["feed"].pop() is False
    BOX["feed"].push(Post(id=3))
    result.settle()
    assert result.get_by_text("post params:id=3")
    assert BOX["post"].can_go_back()
    BOX["post"].pop()
    result.settle()
    assert result.get_by_text("feed count=0")


def test_navigate_from_a_stack_screen_to_a_screen_inside_a_nested_tab_navigator() -> None:
    result = render(NavigationContainer(NestedRoot))
    BOX["feed"].navigate(Login())
    result.settle()
    BOX["login"].navigate(Profile(user="ada"))
    result.settle()
    assert result.get_by_text("profile")
    assert result.get_by_text("profile params:user=ada")
    assert result.get_by_type("TabBar").props["active_tab"] == "Profile"
    assert _names(BOX["profile"].get_parent().get_state()) == ["Tabs"]  # type: ignore[union-attr]


def test_navigate_reaches_a_screen_two_navigators_down() -> None:
    result = render(NavigationContainer(NestedRoot))
    BOX["feed"].navigate(Login())
    result.settle()
    BOX["login"].navigate(Post(id=8))
    result.settle()
    assert result.get_by_text("post params:id=8")
    assert result.get_by_type("TabBar").props["active_tab"] == "FeedTab"
    assert _names(BOX["post"].get_state()) == ["Feed", "Post"]  # the stack's initial screen stays beneath
    BOX["post"].go_back()
    result.settle()
    assert result.get_by_text("feed count=0")


def test_navigate_to_a_nested_navigator_switches_to_it() -> None:
    result = render(NavigationContainer(NestedRoot))
    BOX["feed"].navigate(Login())
    result.settle()
    BOX["login"].navigate(Tabs())
    result.settle()
    assert result.get_by_text("feed")
    assert _names(BOX["feed"].get_parent().get_parent().get_state()) == ["Tabs"]  # type: ignore[union-attr]


def test_initial_state_into_a_nested_stack_keeps_the_initial_route_beneath() -> None:
    initial = NavigationState(
        [Route("Tabs", state=NavigationState([Route("FeedTab", state=NavigationState([Route("Post", {"id": 8})]))]))]
    )
    result = render(NavigationContainer(NestedRoot, initial_state=initial))
    assert result.get_by_text("post params:id=8")
    assert BOX["post"].can_go_back()
    BOX["post"].go_back()
    result.settle()
    assert result.get_by_text("feed count=0")


# ======================================================================
# NavigationContainer
# ======================================================================


def test_container_reports_state_changes_and_ready() -> None:
    states: List[NavigationState] = []
    ready: List[bool] = []
    result = render(
        NavigationContainer(StackNavigator(A, B), on_state_change=states.append, on_ready=lambda: ready.append(True))
    )
    assert ready == [True]
    assert states and states[-1].current.name == "A"
    BOX["a"].push(B())
    result.settle()
    assert states[-1].current.name == "B"
    assert NavigationState.from_dict(states[-1].to_dict()) == states[-1]


def test_container_initial_state_accepts_dict_and_ignores_garbage() -> None:
    saved = NavigationState([Route("A"), Route("Detail", {"id": 2})]).to_dict()
    result = render(NavigationContainer(StackNavigator(A, Detail), initial_state=saved))
    assert result.get_by_text("detail params:id=2,tab=info")  # a missing default comes from the signature
    assert result.get_by_label("Back")

    for garbage in ({"routes": "nope"}, {"routes": [{"name": "Ghost"}]}, {"routes": [{"name": "Detail"}]}):
        fallback = render(NavigationContainer(StackNavigator(A, Detail), initial_state=garbage))
        assert fallback.get_by_text("a"), garbage
        fallback.unmount()


# ======================================================================
# Deep links
# ======================================================================


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@component
def Typed(
    id: int,
    ratio: float = 1.0,
    flag: bool = False,
    color: Color = Color.RED,
    note: Optional[str] = None,
    count: Optional[int] = None,
    mode: Literal["list", "grid"] = "list",
) -> pn.Node:
    return Text(f"typed {id}")


@component
def Search(**filters: str) -> pn.Node:
    return Text(f"search {sorted(filters.items())}")


LinkTabs = TabNavigator(Screen(Feed, path="feed"), Screen(Profile, path="u/{user}"), name="Tabs")
LinkRoot = StackNavigator(
    Screen(Home, path=""),
    Screen(Detail, path="items/{id}"),
    Screen(Typed, path="typed/{id}"),
    Screen(Search, path="search"),
    Screen(LinkTabs, path="tabs"),
    Login,  # no path: not linkable
)


def _links() -> LinkTable:
    return LinkTable(LinkRoot, ["myapp://", "https://example.com/"])


def _leaf(state: Optional[NavigationState]) -> Route:
    assert state is not None
    route = state.current
    while route.state is not None:
        route = route.state.current
    return route


def test_link_table_strip_prefix_variants() -> None:
    links = _links()
    assert links.strip_prefix("myapp://items/1") == "items/1"
    assert links.strip_prefix("MYAPP://items/1") == "items/1"
    assert links.strip_prefix("https://example.com/items/1") == "/items/1"
    assert links.strip_prefix("https://example.com") == ""
    assert links.strip_prefix("https://example.com?x=1") == "?x=1"
    assert links.strip_prefix("https://other.com/items/1") is None
    assert links.strip_prefix("/items/1") == "/items/1"  # bare paths pass through


def test_link_table_state_from_url_flat_nested_and_query() -> None:
    links = _links()
    home = links.state_from_url("myapp://")
    assert home is not None and home.current.name == "Home"

    detail = links.state_from_url("https://example.com/items/42?tab=reviews&ref=mail")
    assert detail is not None
    assert detail.current.name == "Detail"
    assert detail.current.params == {"id": 42, "tab": "reviews"}  # converted; unknown query ignored

    nested = links.state_from_url("myapp://tabs/u/ada")
    assert nested is not None
    assert nested.current.name == "Tabs"
    assert nested.current.state is not None
    assert nested.current.state.current.name == "Profile"
    assert nested.current.state.current.params == {"user": "ada"}

    assert links.state_from_url("myapp://tabs/feed") is not None
    assert links.state_from_url("myapp://nothing/here") is None
    assert links.state_from_url("otherapp://items/1") is None
    assert links.state_from_url("myapp://Login") is None


def test_link_table_converts_params_with_annotations() -> None:
    links = _links()
    route = _leaf(links.state_from_url("myapp://typed/7?ratio=2.5&flag=yes&color=blue&note=hi&count=3&mode=grid"))
    assert route.name == "Typed"
    assert route.params == {
        "id": 7,
        "ratio": 2.5,
        "flag": True,
        "color": Color.BLUE,
        "note": "hi",
        "count": 3,
        "mode": "grid",
    }
    # Enum members also match by name; bool accepts 0/1/false/true.
    route = _leaf(links.state_from_url("myapp://typed/1?color=RED&flag=0"))
    assert route.params == {"id": 1, "color": Color.RED, "flag": False}


@pytest.mark.parametrize(
    "url",
    [
        "myapp://typed/seven",
        "myapp://typed/1?ratio=fast",
        "myapp://typed/1?flag=maybe",
        "myapp://typed/1?color=green",
        "myapp://typed/1?count=many",
        "myapp://typed/1?mode=table",
    ],
)
def test_link_table_rejects_urls_whose_values_do_not_convert(url: str) -> None:
    assert _links().state_from_url(url) is None


def test_link_table_open_keyword_components_accept_any_query() -> None:
    route = _leaf(_links().state_from_url("myapp://search?q=pie&sort=new"))
    assert route.name == "Search"
    assert route.params == {"q": "pie", "sort": "new"}


def test_link_table_rejects_bad_paths() -> None:
    with pytest.raises(ValueError, match="isn't a parameter of its component"):
        LinkTable(StackNavigator(Screen(Home, path="h/{nope}")), ["myapp://"])
    with pytest.raises(ValueError, match="whole"):
        LinkTable(StackNavigator(Home, Screen(Detail, path="items-{id}")), ["myapp://"])


def test_link_table_url_from_state() -> None:
    links = _links()
    assert links.url_from_state(NavigationState([Route("Home")])) == "myapp://"
    assert links.url_from_state(NavigationState([Route("Detail", {"id": 3, "tab": "x"})])) == "myapp://items/3?tab=x"
    nested = NavigationState([Route("Tabs", state=NavigationState([Route("Profile", {"user": "a b"})]))])
    assert links.url_from_state(nested) == "myapp://tabs/u/a%20b"
    typed = NavigationState([Route("Typed", {"id": 1, "color": Color.BLUE, "flag": True})])
    assert links.url_from_state(typed) == "myapp://typed/1?color=blue&flag=true"
    assert links.url_from_state(NavigationState([Route("Login")])) is None
    unknown = NavigationState([Route("Tabs", state=NavigationState([Route("Ghost")]))])
    assert links.url_from_state(unknown) is None

    web = LinkTable(LinkRoot, ["https://example.com/"])
    assert web.url_from_state(NavigationState([Route("Detail", {"id": 3})])) == "https://example.com/items/3"


def test_link_table_round_trips_urls() -> None:
    links = _links()
    for url in ("myapp://items/3?tab=x", "myapp://tabs/u/ada", "myapp://typed/2?flag=true"):
        state = links.state_from_url(url)
        assert state is not None
        assert links.url_from_state(state) == url


@pytest.fixture
def launch_url(monkeypatch: pytest.MonkeyPatch) -> Callable[[Optional[str]], None]:
    monkeypatch.setattr(linking_module, "_url_listeners", [])

    def set_url(url: Optional[str]) -> None:
        monkeypatch.setattr(linking_module, "_initial_url", url)

    set_url(None)
    return set_url


def test_container_seeds_from_the_launch_url_and_follows_later_links(
    launch_url: Callable[[Optional[str]], None],
) -> None:
    launch_url("myapp://items/5")
    result = render(NavigationContainer(LinkRoot, link_prefixes=["myapp://"]))
    assert result.get_by_text("detail params:id=5,tab=info")
    assert result.get_by_label("Back")  # Home sits beneath the deep-linked screen

    linking_module.dispatch_url("myapp://")
    result.settle()
    assert result.get_by_text("home")
    assert result.query_by_text("detail", hidden=True) is None

    linking_module.dispatch_url("myapp://tabs/u/ada")
    result.settle()
    assert result.get_by_text("profile params:user=ada")

    linking_module.dispatch_url("myapp://nowhere")  # no match: ignored
    result.settle()
    assert result.get_by_text("profile params:user=ada")


def test_container_ignores_the_launch_url_without_link_prefixes(launch_url: Callable[[Optional[str]], None]) -> None:
    launch_url("myapp://items/5")
    result = render(NavigationContainer(LinkRoot))
    assert result.get_by_text("home")


def test_container_initial_state_wins_over_the_launch_url(launch_url: Callable[[Optional[str]], None]) -> None:
    launch_url("myapp://items/5")
    initial = NavigationState([Route("Login")])
    result = render(NavigationContainer(LinkRoot, link_prefixes=["myapp://"], initial_state=initial))
    assert result.get_by_text("login")


def test_container_launch_url_with_a_bad_value_falls_back_to_the_initial_screen(
    launch_url: Callable[[Optional[str]], None],
) -> None:
    launch_url("myapp://items/not-a-number")
    result = render(NavigationContainer(LinkRoot, link_prefixes=["myapp://"]))
    assert result.get_by_text("home")


# ======================================================================
# NavigationRef
# ======================================================================


def test_navigation_ref_raises_until_a_container_binds_it() -> None:
    ref = NavigationRef()
    assert not ref.is_ready()
    assert ref.current is None
    assert "unbound" in repr(ref)
    calls: List[Callable[[], Any]] = [
        lambda: ref.navigate(Home()),
        lambda: ref.push(Home()),
        lambda: ref.replace(Home()),
        lambda: ref.pop(),
        lambda: ref.go_back(),
        lambda: ref.pop_to(Home),
        lambda: ref.pop_to_top(),
        lambda: ref.reset(Home()),
        lambda: ref.get_state(),
    ]
    for call in calls:
        with pytest.raises(RuntimeError, match="Navigation container is not mounted"):
            call()


def test_navigation_ref_binds_to_root_navigator_and_unbinds_on_unmount() -> None:
    ref = NavigationRef()
    result = render(NavigationContainer(StackNavigator(Home, Detail, Login), ref=ref))
    assert ref.is_ready()
    assert "ready" in repr(ref)
    assert ref.current is not None
    assert ref.current.route.name == "Home"

    ref.navigate(Detail(id=1))
    result.settle()
    assert result.get_by_text("detail params:id=1,tab=info")
    assert ref.get_state().current.name == "Detail"
    assert ref.current.route.name == "Detail"  # the ref's handle follows the active route

    ref.push(Login())
    result.settle()
    ref.pop_to(Detail)
    result.settle()
    assert _names(ref.get_state()) == ["Home", "Detail"]
    ref.replace(Detail(id=2))
    result.settle()
    assert result.get_by_text("detail params:id=2,tab=info")
    assert ref.go_back() is True
    result.settle()
    assert result.get_by_text("home")
    ref.push(Login())
    result.settle()
    ref.pop_to_top()
    result.settle()
    assert _names(ref.get_state()) == ["Home"]
    ref.reset(Login())
    result.settle()
    assert result.get_by_text("login")
    assert ref.pop() is False

    result.unmount()
    assert not ref.is_ready()
    assert ref.current is None


def test_navigation_ref_moves_when_the_container_gets_a_new_ref() -> None:
    first, second = NavigationRef(), NavigationRef()
    Root = StackNavigator(Home)
    result = render(NavigationContainer(Root, ref=first))
    assert first.is_ready()
    result.rerender(NavigationContainer(Root, ref=second))
    assert second.is_ready()
    assert not first.is_ready()


def test_navigation_ref_reaches_nested_navigators() -> None:
    ref = NavigationRef()
    result = render(NavigationContainer(NestedRoot, ref=ref))
    ref.navigate(Profile(user="ada"))
    result.settle()
    assert result.get_by_text("profile params:user=ada")
    assert result.get_by_type("TabBar").props["active_tab"] == "Profile"


# ======================================================================
# Public API
# ======================================================================


def test_navigation_exports_from_package() -> None:
    for name in (
        "DrawerNavigator",
        "Group",
        "Navigation",
        "NavigationContainer",
        "NavigationRef",
        "NavigationState",
        "Navigator",
        "Route",
        "Screen",
        "ScreenOptions",
        "StackNavigator",
        "TabBarStyle",
        "TabNavigator",
        "use_focus_effect",
        "use_is_focused",
        "use_navigation",
        "use_route",
        "use_screen_options",
    ):
        assert hasattr(pn, name), name
        assert name in pn.__all__, name
    assert pn.use_navigation is use_navigation
    assert pn.StackNavigator is StackNavigator
    assert not hasattr(pn, "NavigationContext")
    assert NavigationContext is not None


def test_removed_navigation_api_is_gone() -> None:
    from pythonnative import navigation

    for name in (
        "create_stack_navigator",
        "create_tab_navigator",
        "create_drawer_navigator",
        "create_navigation_ref",
        "LinkingConfig",
        "ScreenDef",
        "ScreenGroup",
        "RouteParams",
        "NavigationTheme",
        "NavigationColors",
        "DEFAULT_NAVIGATION_THEME",
        "DARK_NAVIGATION_THEME",
        "use_navigation_theme",
    ):
        assert not hasattr(pn, name), name
        assert not hasattr(navigation, name), name
        assert name not in pn.__all__, name


def test_native_screens_paint_the_theme_background_except_transparent_modals() -> None:
    from pythonnative.navigation.navigators import _native_screen

    navigator = StackNavigator(A, pn.Screen(B, presentation="transparent_modal"))
    core, _ = _make_core(navigator)
    _top(core).push(B())
    theme = pn.LIGHT_THEME
    first, second = (
        _native_screen(core, route, route is core.state.current, True, theme) for route in core.state.routes
    )
    assert first.props["background_color"] == theme.colors.background
    assert second.props["background_color"] == "#00000000"
