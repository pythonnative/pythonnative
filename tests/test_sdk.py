"""Tests for the public extension SDK (``pythonnative.sdk``).

Exercises the typed prop system (``Props``), ``define_component`` and the
``element_factory`` constructors it returns, and the entry-point
discovery hook used to import third-party PyPI plugins.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

import pytest

import pythonnative as pn
import pythonnative.sdk._components as nc_internals
from pythonnative.element import Element
from pythonnative.sdk import (
    ENTRY_POINT_GROUP,
    Props,
    define_component,
    element_factory,
    get_props_type,
    list_components,
    unregister_component,
)
from pythonnative.sdk.schema import COMPONENTS
from pythonnative.testing import FakeBackend, render

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BadgeProps(Props):
    text: str = ""
    color: str = "#FF3B30"
    style: pn.StyleProp = None


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    """Snapshot the SDK registry before each test, restore on teardown."""
    snapshot = dict(nc_internals._REGISTRY)
    schemas = {name: COMPONENTS[name] for name in snapshot if name in COMPONENTS}
    nc_internals._REGISTRY.clear()
    nc_internals._reset_discovery_state_for_tests()
    yield
    for name in list(nc_internals._REGISTRY):
        if name not in snapshot:
            COMPONENTS.pop(name, None)
    nc_internals._REGISTRY.clear()
    nc_internals._REGISTRY.update(snapshot)
    COMPONENTS.update(schemas)
    nc_internals._reset_discovery_state_for_tests()


# ---------------------------------------------------------------------------
# define_component
# ---------------------------------------------------------------------------


def test_define_component_registers_schema_and_returns_factory() -> None:
    Badge = define_component("Badge", BadgeProps)
    assert "Badge" in list_components()
    assert get_props_type("Badge") is BadgeProps
    assert "Badge" in COMPONENTS
    assert "text" in COMPONENTS["Badge"].props and "color" in COMPONENTS["Badge"].props
    el = Badge(text="3", color="#0A84FF")
    assert isinstance(el, Element)
    assert el.type == "Badge"
    assert el.props["text"] == "3"
    assert el.props["color"] == "#0A84FF"
    assert el.children == ()


def test_define_component_replaces_earlier_definition() -> None:
    @dataclass(frozen=True)
    class First(Props):
        text: str = ""

    @dataclass(frozen=True)
    class Second(Props):
        label: str = ""

    define_component("Badge", First)
    Badge = define_component("Badge", Second)
    assert get_props_type("Badge") is Second
    assert Badge(label="x").props["label"] == "x"
    with pytest.raises(TypeError, match="Invalid props"):
        Badge(text="old field")


def test_define_component_rejects_non_dataclass_props() -> None:
    class NotADataclass:
        pass

    with pytest.raises(TypeError, match="must be a @dataclass type"):
        define_component("Badge", NotADataclass)


def test_define_component_records_platforms() -> None:
    define_component("Badge", BadgeProps, platforms=("ios",))
    assert COMPONENTS["Badge"].platforms == ("ios",)


def test_custom_component_callbacks_cross_the_validated_bridge() -> None:
    from pythonnative.bridge.fake import FakeTransport
    from pythonnative.events import dispatch_event
    from pythonnative.native_views.bridge_backend import BridgeBackend
    from pythonnative.reconciler import Reconciler

    @dataclass(frozen=True)
    class InteractiveBadgeProps:
        on_press: Callable[[int], Any] | None = None

    Badge = define_component("InteractiveBadge", InteractiveBadgeProps)
    received: list[int] = []
    transport = FakeTransport()
    reconciler = Reconciler(BridgeBackend(transport))
    try:
        reconciler.reconcile(Badge(on_press=received.append))
        tag = reconciler.root_tag
        assert tag is not None
        assert transport.views[tag].props["_pn_events"] == ["on_press"]
        dispatch_event(tag, "on_press", 42)
        assert received == [42]
        reconciler.reconcile(Badge())
        assert not transport.views[tag].props.get("_pn_events")
        dispatch_event(tag, "on_press", 43)
        assert received == [42]
    finally:
        reconciler.unmount()
        unregister_component("InteractiveBadge")


def test_unregister_component() -> None:
    define_component("Badge", BadgeProps)
    assert "Badge" in list_components()
    unregister_component("Badge")
    assert "Badge" not in list_components()
    assert "Badge" not in COMPONENTS
    with pytest.raises(KeyError, match="No component defined"):
        element_factory("Badge")


# ---------------------------------------------------------------------------
# element_factory
# ---------------------------------------------------------------------------


def test_element_factory_accepts_props_instance() -> None:
    define_component("Badge", BadgeProps)
    Badge = element_factory("Badge")
    el = Badge(props=BadgeProps(text="Hi", color="#FFFFFF"))
    assert el.props["text"] == "Hi"
    assert el.props["color"] == "#FFFFFF"


def test_element_factory_skips_none_default_fields() -> None:
    Badge = define_component("Badge", BadgeProps)
    el = Badge(props=BadgeProps())
    # ``style`` defaults to None and is dropped.
    assert "style" not in el.props
    # Non-None defaults survive.
    assert el.props["text"] == ""
    assert el.props["color"] == "#FF3B30"


def test_element_factory_resolves_style_arg() -> None:
    Badge = define_component("Badge", BadgeProps)
    el = Badge(text="5", style=pn.style(padding=4, background_color="#000"))
    assert el.props["padding"] == 4
    assert el.props["background_color"] == "#000"
    assert el.props["text"] == "5"


def test_element_factory_adds_style_to_signature_when_props_lack_it() -> None:
    import inspect

    @dataclass(frozen=True)
    class Plain(Props):
        text: str = ""

    Badge = define_component("Badge", Plain)
    assert "style" in inspect.signature(Badge).parameters
    el = Badge(text="x", style=pn.style(padding=2))
    assert el.props["padding"] == 2


def test_element_factory_passes_children() -> None:
    @dataclass(frozen=True)
    class ContainerProps(Props):
        style: pn.StyleProp = None

    Container = define_component("Container", ContainerProps)
    inner = pn.Text("inner")
    el = Container(inner, key="root")
    assert el.children == (inner,)
    assert el.key == "root"


def test_element_factory_unknown_name_raises() -> None:
    with pytest.raises(KeyError, match="No component defined"):
        element_factory("DoesNotExist")


def test_element_factory_kwargs_against_unknown_field_raises() -> None:
    Badge = define_component("Badge", BadgeProps)
    with pytest.raises(TypeError, match="Invalid props"):
        Badge(unknown_field=42)


def test_element_factory_rejects_both_props_and_kwargs() -> None:
    Badge = define_component("Badge", BadgeProps)
    with pytest.raises(TypeError, match="Pass either props"):
        Badge(props=BadgeProps(text="a"), text="b")


def test_element_factory_validates_field_types() -> None:
    Badge = define_component("Badge", BadgeProps)
    with pytest.raises(TypeError):
        Badge(text=3)


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
            define_component(self.name, BadgeProps)

    class FakeEntryPoints:
        def select(self, group: str) -> Any:
            return [FakeEP("FromPlugin")]

    import importlib

    em = importlib.import_module("importlib.metadata")
    monkeypatch.setattr(em, "entry_points", lambda *, group: FakeEntryPoints().select(group=group))

    nc_internals._reset_discovery_state_for_tests()
    nc_internals.discover_components()
    assert calls == ["FromPlugin"]
    assert "FromPlugin" in list_components()
    nc_internals.discover_components()
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
            define_component("Good", BadgeProps)

    good = GoodEP()

    class FakeEntryPoints:
        def select(self, group: str) -> Any:
            return [BrokenEP(), good]

    import importlib

    em = importlib.import_module("importlib.metadata")
    monkeypatch.setattr(em, "entry_points", lambda *, group: FakeEntryPoints().select(group=group))

    nc_internals._reset_discovery_state_for_tests()
    nc_internals.discover_components()
    assert good.loaded
    assert "Good" in list_components()


# ---------------------------------------------------------------------------
# Round-trip: real factory + real reconciler
# ---------------------------------------------------------------------------


def test_sdk_component_renders_through_the_reconciler() -> None:
    @dataclass(frozen=True)
    class GlassProps(Props):
        text: str = ""
        intensity: float = 0.5
        style: Optional[pn.StyleProp] = None

    Glass = define_component("Glass", GlassProps)
    backend = FakeBackend()
    result = render(Glass(text="hi", intensity=0.8, style=pn.style(padding=8)), backend=backend)
    view = result.get_by_type("Glass")
    assert view.props["text"] == "hi"
    assert view.props["intensity"] == 0.8
    assert view.props["padding"] == 8
    result.rerender(Glass(text="bye", intensity=0.8, style=pn.style(padding=8)))
    assert result.get_by_type("Glass").props["text"] == "bye"
    assert backend.last_update_changes == {"text": "bye"}
    result.unmount()


# ---------------------------------------------------------------------------
# Top-level re-exports stay in sync with the SDK package
# ---------------------------------------------------------------------------


def test_top_level_reexports() -> None:
    assert pn.Props is Props
    assert pn.define_component is define_component
    assert pn.element_factory is element_factory
    for removed in ("ViewHandler", "native_component", "register_component"):
        assert not hasattr(pn, removed), removed
        assert not hasattr(pn.sdk, removed), removed
