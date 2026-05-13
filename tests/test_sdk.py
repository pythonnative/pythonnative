"""Tests for the public extension SDK (``pythonnative.sdk``).

Exercises the typed prop system (``Props``), the
``@native_component`` decorator, the imperative ``register_component``
helper, ``element_factory`` constructors, and the entry-point discovery
hook used to import third-party PyPI plugins.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

import pythonnative as pn
import pythonnative.sdk._components as nc_internals
from pythonnative.element import Element
from pythonnative.native_views import NativeViewRegistry, set_registry
from pythonnative.sdk import (
    ENTRY_POINT_GROUP,
    Props,
    ViewHandler,
    element_factory,
    get_props_type,
    install_into_registry,
    list_components,
    native_component,
    register_component,
    unregister_component,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BadgeProps(Props):
    text: str = ""
    color: str = "#FF3B30"
    style: pn.StyleProp = None


class StubBadgeHandler(ViewHandler):
    """ViewHandler whose native view is just a dict for assertions."""

    def __init__(self) -> None:
        self.created: list = []

    def create(self, props: Dict[str, Any]) -> Dict[str, Any]:
        view = {"props": dict(props), "type": "badge"}
        self.created.append(view)
        return view

    def update(self, view: Dict[str, Any], changed: Dict[str, Any]) -> None:
        view["props"].update(changed)


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    """Snapshot the SDK registry before each test, restore on teardown."""
    snapshot = dict(nc_internals._REGISTRY)
    nc_internals._REGISTRY.clear()
    nc_internals._reset_discovery_state_for_tests()
    yield
    nc_internals._REGISTRY.clear()
    nc_internals._REGISTRY.update(snapshot)
    nc_internals._reset_discovery_state_for_tests()


# ---------------------------------------------------------------------------
# native_component decorator
# ---------------------------------------------------------------------------


def test_native_component_registers_handler() -> None:
    @native_component("Badge", props=BadgeProps, platforms=("ios",))
    class IOSBadge(StubBadgeHandler):
        pass

    assert "Badge" in list_components()
    assert get_props_type("Badge") is BadgeProps


def test_native_component_default_platforms() -> None:
    @native_component("Spinner")
    class Spinner(StubBadgeHandler):
        pass

    plat_map = nc_internals._REGISTRY["Spinner"][1]
    assert set(plat_map.keys()) == {"android", "ios"}


def test_native_component_two_platform_specific_classes() -> None:
    @native_component("Badge", props=BadgeProps, platforms=("ios",))
    class IOSBadge(StubBadgeHandler):
        pass

    @native_component("Badge", props=BadgeProps, platforms=("android",))
    class AndroidBadge(StubBadgeHandler):
        pass

    plat_map = nc_internals._REGISTRY["Badge"][1]
    assert set(plat_map.keys()) == {"ios", "android"}
    assert isinstance(plat_map["ios"], IOSBadge)
    assert isinstance(plat_map["android"], AndroidBadge)


def test_native_component_replaces_handler_for_same_platform() -> None:
    @native_component("Badge", props=BadgeProps, platforms=("ios",))
    class FirstBadge(StubBadgeHandler):
        pass

    @native_component("Badge", props=BadgeProps, platforms=("ios",))
    class SecondBadge(StubBadgeHandler):
        pass

    plat_map = nc_internals._REGISTRY["Badge"][1]
    assert isinstance(plat_map["ios"], SecondBadge)


def test_native_component_rejects_non_view_handler() -> None:
    with pytest.raises(TypeError, match="ViewHandler subclass"):

        @native_component("BadCoffee")
        class NotAHandler:  # type: ignore[type-var]
            pass


# ---------------------------------------------------------------------------
# register_component (imperative)
# ---------------------------------------------------------------------------


def test_register_component_basic() -> None:
    handler = StubBadgeHandler()
    register_component(name="Badge", props=BadgeProps, handlers={"ios": handler})
    assert get_props_type("Badge") is BadgeProps
    assert nc_internals._REGISTRY["Badge"][1]["ios"] is handler


def test_register_component_merges_platforms() -> None:
    a = StubBadgeHandler()
    b = StubBadgeHandler()
    register_component(name="Badge", handlers={"ios": a})
    register_component(name="Badge", props=BadgeProps, handlers={"android": b})
    plat_map = nc_internals._REGISTRY["Badge"][1]
    assert plat_map == {"ios": a, "android": b}
    # Late-arrived props get installed
    assert get_props_type("Badge") is BadgeProps


def test_register_component_invalid_props_raises() -> None:
    class NotADataclass:
        pass

    with pytest.raises(TypeError, match="must be a @dataclass type"):
        register_component(
            name="Badge",
            props=NotADataclass,
            handlers={"ios": StubBadgeHandler()},
        )


def test_register_component_invalid_handler_raises() -> None:
    with pytest.raises(TypeError, match="ViewHandler instance"):
        register_component(name="Badge", handlers={"ios": "not a handler"})  # type: ignore[dict-item]


def test_unregister_component() -> None:
    register_component(name="Badge", handlers={"ios": StubBadgeHandler()})
    assert "Badge" in list_components()
    unregister_component("Badge")
    assert "Badge" not in list_components()


# ---------------------------------------------------------------------------
# element_factory
# ---------------------------------------------------------------------------


def test_element_factory_validates_kwargs_via_props() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": StubBadgeHandler()})
    Badge = element_factory("Badge")
    el = Badge(text="3", color="#0A84FF")
    assert isinstance(el, Element)
    assert el.type == "Badge"
    assert el.props["text"] == "3"
    assert el.props["color"] == "#0A84FF"
    assert el.children == []


def test_element_factory_accepts_props_instance() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": StubBadgeHandler()})
    Badge = element_factory("Badge")
    el = Badge(props=BadgeProps(text="Hi", color="#FFFFFF"))
    assert el.props["text"] == "Hi"
    assert el.props["color"] == "#FFFFFF"


def test_element_factory_skips_none_default_fields() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": StubBadgeHandler()})
    Badge = element_factory("Badge")
    el = Badge(props=BadgeProps())
    # ``style`` defaults to None and is dropped.
    assert "style" not in el.props
    # Non-None defaults survive.
    assert el.props["text"] == ""
    assert el.props["color"] == "#FF3B30"


def test_element_factory_resolves_style_arg() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": StubBadgeHandler()})
    Badge = element_factory("Badge")
    el = Badge(text="5", style=pn.style(padding=4, background_color="#000"))
    assert el.props["padding"] == 4
    assert el.props["background_color"] == "#000"
    assert el.props["text"] == "5"


def test_element_factory_passes_children() -> None:
    register_component(name="Container", handlers={"ios": StubBadgeHandler()})
    Container = element_factory("Container")
    inner = pn.Text("inner")
    el = Container(inner, key="root")
    assert el.children == [inner]
    assert el.key == "root"


def test_element_factory_unknown_name_raises() -> None:
    with pytest.raises(KeyError, match="No component registered"):
        element_factory("DoesNotExist")


def test_element_factory_kwargs_against_unknown_field_raises() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": StubBadgeHandler()})
    Badge = element_factory("Badge")
    with pytest.raises(TypeError, match="Invalid props"):
        Badge(unknown_field=42)


def test_element_factory_rejects_both_props_and_kwargs() -> None:
    register_component(name="Badge", props=BadgeProps, handlers={"ios": StubBadgeHandler()})
    Badge = element_factory("Badge")
    with pytest.raises(TypeError, match="Pass either props"):
        Badge(props=BadgeProps(text="a"), text="b")


def test_element_factory_without_props_passes_kwargs_through() -> None:
    register_component(name="Anything", handlers={"ios": StubBadgeHandler()})
    Anything = element_factory("Anything")
    el = Anything(arbitrary="value", number=42)
    assert el.props == {"arbitrary": "value", "number": 42}


# ---------------------------------------------------------------------------
# install_into_registry
# ---------------------------------------------------------------------------


def test_install_copies_handlers_for_active_platform() -> None:
    handler = StubBadgeHandler()
    register_component(name="Badge", props=BadgeProps, handlers={"ios": handler, "android": handler})

    reg = NativeViewRegistry()
    install_into_registry(reg, "ios")

    view = reg.create_view("Badge", {"text": "hi"})
    assert view["type"] == "badge"
    assert view["props"]["text"] == "hi"


def test_install_skips_handlers_not_targeting_platform() -> None:
    register_component(name="IOSOnly", props=BadgeProps, handlers={"ios": StubBadgeHandler()})

    reg = NativeViewRegistry()
    install_into_registry(reg, "android")

    with pytest.raises(ValueError, match="Unknown element type"):
        reg.create_view("IOSOnly", {})


def test_install_supports_multiple_components() -> None:
    register_component(name="A", handlers={"ios": StubBadgeHandler()})
    register_component(name="B", handlers={"ios": StubBadgeHandler()})

    reg = NativeViewRegistry()
    install_into_registry(reg, "ios")

    reg.create_view("A", {})
    reg.create_view("B", {})


# ---------------------------------------------------------------------------
# Entry-point discovery
# ---------------------------------------------------------------------------


def test_entry_point_group_constant() -> None:
    """Public entry-point group name is part of the SDK contract."""
    assert ENTRY_POINT_GROUP == "pythonnative.handlers"


def test_entry_point_discovery_runs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []

    class FakeEP:
        def __init__(self, name: str) -> None:
            self.name = name

        def load(self) -> None:
            calls.append(self.name)
            register_component(name=self.name, handlers={"ios": StubBadgeHandler()})

    class FakeEntryPoints:
        def select(self, group: str) -> Any:
            return [FakeEP("FromPlugin")]

    import importlib

    em = importlib.import_module("importlib.metadata")
    monkeypatch.setattr(em, "entry_points", lambda: FakeEntryPoints())

    nc_internals._reset_discovery_state_for_tests()
    nc_internals._discover_entry_points()
    assert calls == ["FromPlugin"]
    nc_internals._discover_entry_points()
    assert calls == ["FromPlugin"]  # second call is a no-op


def test_entry_point_failure_does_not_break_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken plugin is logged but never propagates."""

    class BrokenEP:
        name = "Broken"

        def load(self) -> None:
            raise RuntimeError("boom")

    class GoodEP:
        name = "Good"

        def __init__(self) -> None:
            self.loaded = False

        def load(self) -> None:
            self.loaded = True
            register_component(name="Good", handlers={"ios": StubBadgeHandler()})

    good = GoodEP()

    class FakeEntryPoints:
        def select(self, group: str) -> Any:
            return [BrokenEP(), good]

    import importlib

    em = importlib.import_module("importlib.metadata")
    monkeypatch.setattr(em, "entry_points", lambda: FakeEntryPoints())

    nc_internals._reset_discovery_state_for_tests()
    nc_internals._discover_entry_points()
    assert good.loaded
    assert "Good" in list_components()


def test_get_registry_runs_sdk_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_registry pulls SDK handlers in for the active platform."""
    handler = StubBadgeHandler()
    register_component(name="Badge", props=BadgeProps, handlers={"ios": handler, "android": handler})

    # Force the lazy registry to rebuild against a stub backend
    set_registry(None)

    # Patch `_register_builtin_handlers` so we don't need the real
    # platform-specific handler module.
    import pythonnative.native_views as nv

    original_register_builtin = nv._register_builtin_handlers
    monkeypatch.setattr(nv, "_register_builtin_handlers", lambda registry: None)

    try:
        reg = nv.get_registry()
        view = reg.create_view("Badge", {"text": "hi"})
        assert view["type"] == "badge"
    finally:
        set_registry(None)
        monkeypatch.setattr(nv, "_register_builtin_handlers", original_register_builtin)


# ---------------------------------------------------------------------------
# Round-trip: real factory + real reconciler
# ---------------------------------------------------------------------------


class RecordingHandler(ViewHandler):
    def __init__(self) -> None:
        self.creates: list = []
        self.updates: list = []

    def create(self, props: Dict[str, Any]) -> Dict[str, Any]:
        self.creates.append(dict(props))
        return {"props": dict(props), "kids": []}

    def update(self, view: Dict[str, Any], changed: Dict[str, Any]) -> None:
        view["props"].update(changed)
        self.updates.append(dict(changed))


def test_sdk_component_drives_reconciler_end_to_end() -> None:
    @dataclass(frozen=True)
    class Props2(Props):
        text: str = ""
        intensity: float = 0.5
        style: Optional[pn.StyleProp] = None

    handler = RecordingHandler()
    register_component(name="Glass", props=Props2, handlers={"ios": handler, "android": handler})

    Glass = element_factory("Glass")

    reg = NativeViewRegistry()
    install_into_registry(reg, "ios")

    el = Glass(text="hi", intensity=0.8, style=pn.style(padding=8))

    from pythonnative.reconciler import Reconciler

    rec = Reconciler(reg)
    view = rec.mount(el)
    assert view["props"]["text"] == "hi"
    assert view["props"]["intensity"] == 0.8
    assert view["props"]["padding"] == 8
    assert handler.creates == [view["props"]]


# ---------------------------------------------------------------------------
# Top-level re-exports stay in sync with the SDK package
# ---------------------------------------------------------------------------


def test_top_level_reexports() -> None:
    assert pn.Props is Props
    assert pn.ViewHandler is ViewHandler
    assert pn.native_component is native_component
    assert pn.register_component is register_component
    assert pn.element_factory is element_factory
