"""Public Python values survive the native transport without type erasure."""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Iterator, Literal, Mapping, NotRequired, Protocol, Sequence, TypedDict

import pytest

import pythonnative as pn
from pythonnative.native_modules.registry import BridgeModule, PythonModule
from pythonnative.sdk.schema import COMPONENTS, MODULES, ModuleSchema
from pythonnative.sdk.types import decode_value, encode_value, type_schema


class Accuracy(Enum):
    BALANCED = "balanced"
    HIGH = "high"


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float
    accuracy: Accuracy = Accuracy.BALANCED
    labels: list[str] = field(default_factory=list)


class Note(TypedDict):
    title: str
    body: NotRequired[str]


class NullableNote(TypedDict):
    required: str | None
    optional: NotRequired[str | None]


class LocationAPI(Protocol):
    async def locate(self, *, hint: Coordinate, timeout: float = 10) -> Coordinate: ...


@pytest.fixture
def location_contract() -> Iterator[ModuleSchema]:
    old = MODULES.get("TypedLocationTest")
    schema = ModuleSchema.from_protocol("TypedLocationTest", LocationAPI)
    MODULES[schema.name] = schema
    yield schema
    if old is None:
        MODULES.pop(schema.name, None)
    else:
        MODULES[schema.name] = old


def test_nested_record_enum_and_collection_round_trip() -> None:
    value = {"home": (Coordinate(12.5, -70.25, Accuracy.HIGH, ["favorite"]), None)}
    schema = type_schema(Mapping[str, tuple[Coordinate, str | None]])
    wire = json.loads(json.dumps(encode_value(value, schema)))
    assert wire["home"][0]["accuracy"] == "high"
    assert decode_value(wire, schema) == value
    assert isinstance(decode_value(wire, schema)["home"][0], Coordinate)


def test_record_defaults_and_typed_dict_absence() -> None:
    result = decode_value({"latitude": 1, "longitude": 2}, type_schema(Coordinate))
    assert result == Coordinate(1, 2)
    assert decode_value({"title": "Draft"}, type_schema(Note)) == {"title": "Draft"}
    with pytest.raises(TypeError, match="requires title"):
        decode_value({}, type_schema(Note))


def test_nullable_record_fields_preserve_presence() -> None:
    schema = type_schema(NullableNote)
    for value in ({"required": None}, {"required": None, "optional": None}, {"required": "yes", "optional": "yes"}):
        assert decode_value(encode_value(value, schema), schema) == value
    with pytest.raises(TypeError, match="requires required"):
        decode_value({"optional": None}, schema)


def test_record_field_names_fail_before_native_compilation() -> None:
    Invalid = TypedDict("Invalid", {"user-name": str})
    with pytest.raises(TypeError, match="Python identifier"):
        type_schema(Invalid)


def test_sequences_and_dataclass_class_variables_keep_python_semantics() -> None:
    @dataclass
    class Batch:
        version: ClassVar[int] = 1
        values: Sequence[int]

    schema = type_schema(Batch)
    assert encode_value(Batch(range(3)), schema) == {"values": [0, 1, 2]}
    assert decode_value({"values": [0, 1, 2]}, schema) == Batch([0, 1, 2])
    with pytest.raises(TypeError, match="must be number"):
        decode_value(10**1000, type_schema(float))


def test_custom_component_defaults_and_platforms_survive_factory_creation() -> None:
    from pythonnative.platform import _set_platform_for_test
    from pythonnative.sdk import element_factory, register_component, unregister_component

    @dataclass(frozen=True)
    class MarkerProps:
        coordinate: Coordinate = field(default_factory=lambda: Coordinate(1, 2))

    try:
        register_component(name="TypedMarkerTest", props=MarkerProps, platforms=("ios",))
        marker = element_factory("TypedMarkerTest")
        element = marker(style={"padding": 4, "opacity": 0.5})
        assert element.props["coordinate"] == Coordinate(1, 2)
        assert element.props["padding"] == 4
        COMPONENTS["TypedMarkerTest"].validate(element.props)
        assert COMPONENTS["TypedMarkerTest"].defaults["coordinate"]["accuracy"] == "balanced"
        _set_platform_for_test("ios")
        assert pn.Platform.supports("TypedMarkerTest")
        _set_platform_for_test("android")
        assert not pn.Platform.supports("TypedMarkerTest")
    finally:
        unregister_component("TypedMarkerTest")
        _set_platform_for_test(None)


def test_literal_discriminated_records() -> None:
    class Success(TypedDict):
        status: Literal["ok"]
        value: int

    class Failure(TypedDict):
        status: Literal["error"]
        message: str

    schema = type_schema(Success | Failure)
    assert decode_value({"status": "error", "message": "offline"}, schema) == {"status": "error", "message": "offline"}
    with pytest.raises(TypeError, match="annotation"):
        decode_value({"status": "ok", "message": "wrong shape"}, schema)


@pytest.mark.parametrize("annotation", [object, dict[int, str], complex])
def test_unsupported_annotations_fail_during_declaration(annotation: Any) -> None:
    with pytest.raises(TypeError):
        type_schema(annotation)


@pytest.mark.parametrize("value", [{1: "numeric key"}, object(), float("nan"), 2**53])
def test_values_cannot_be_silently_dropped_or_coerced(value: Any) -> None:
    with pytest.raises(TypeError):
        encode_value(value)


def test_typed_native_call_preserves_defaults_and_results(location_contract: ModuleSchema) -> None:
    class Transport:
        def call(self, module: str, method: str, envelope: str) -> str:
            request = json.loads(envelope)
            assert request["args"]["timeout"] == 10
            assert request["args"]["hint"]["accuracy"] == "balanced"
            return json.dumps({"ok": True, "value": request["args"]["hint"]})

    result = asyncio.run(BridgeModule("TypedLocationTest", Transport()).call_async("locate", hint=Coordinate(1, 2)))
    assert type(result) is Coordinate
    assert result == Coordinate(1, 2)


def test_fallback_receives_same_typed_arguments(location_contract: ModuleSchema) -> None:
    class Implementation:
        async def locate(self, *, hint: Coordinate, timeout: float) -> Coordinate:
            assert type(hint) is Coordinate
            assert timeout == 10
            return hint

    result = asyncio.run(
        PythonModule("TypedLocationTest", Implementation()).call_async("locate", hint={"latitude": 1, "longitude": 2})
    )
    assert result == Coordinate(1, 2)


def test_media_event_shapes_match_real_native_payloads() -> None:
    image = COMPONENTS["Image"].decode_event("on_load", [{"width": 64, "height": 32}])
    assert image == [pn.ImageLoadEvent(64, 32)]
    web = COMPONENTS["WebView"].decode_event(
        "on_navigation_state_change",
        [
            {
                "url": "https://example.com",
                "loading": False,
                "can_go_back": True,
                "can_go_forward": False,
                "title": "Example",
            }
        ],
    )
    assert web[0].can_go_back is True
    assert web[0].title == "Example"
    for property_name in ("max_lines", "text_transform"):
        assert COMPONENTS["Text"].props[property_name]["native"]["invalidates_layout"]


def test_null_and_property_removal_have_distinct_wire_and_native_state() -> None:
    from pythonnative.bridge import codec
    from pythonnative.bridge.commits import PROTOCOL_VERSION, CommitError, CommitState
    from pythonnative.mutations import UNSET, CreateOp, UpdateOp

    operations, _ = codec.encode_transaction(
        [
            CreateOp(1, "Picker", {"value": "draft"}),
            UpdateOp(1, {"value": None}),
        ]
    )
    state = (
        CommitState()
        .prepare(
            {
                "version": PROTOCOL_VERSION,
                "application": "null-test",
                "surface": 1,
                "revision": 1,
                "ops": json.loads(operations),
            }
        )
        .publish()
    )
    assert state.views[1].props["value"] is None
    operations, _ = codec.encode_transaction([UpdateOp(1, {"value": UNSET})])
    assert json.loads(operations) == [["u", 1, {}, ["value"]]]
    envelope = {
        "version": PROTOCOL_VERSION,
        "application": "null-test",
        "surface": 1,
        "revision": 2,
        "ops": json.loads(operations),
    }
    state = state.prepare(envelope).publish()
    assert "value" not in state.views[1].props
    with pytest.raises(CommitError, match="both set and removed"):
        state.prepare({**envelope, "revision": 3, "ops": [["u", 1, {"value": "conflict"}, ["value"]]]})


def test_unserializable_native_props_are_errors_unless_declared_python_only() -> None:
    from pythonnative.bridge.codec import split_props

    value = object()
    with pytest.raises(TypeError, match="bridge-serializable"):
        split_props({"value": value})
    assert split_props({"value": value}, frozenset({"value"})) == ({}, {"value": value})


def test_typed_module_events_decode_before_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative.native_modules import registry

    schema = ModuleSchema.from_protocol("TypedLocationTest", LocationAPI, events={"changed": Coordinate})
    monkeypatch.setitem(MODULES, schema.name, schema)
    module = PythonModule(schema.name)
    monkeypatch.setitem(registry._modules, schema.name, module)
    received: list[Coordinate] = []
    unsubscribe = module.add_listener("changed", received.append)
    registry.emit(schema.name, "changed", {"latitude": 2, "longitude": 3})
    assert received == [Coordinate(2, 3)]
    with pytest.raises(TypeError):
        registry.emit(schema.name, "changed", {"latitude": "bad", "longitude": 3})
    assert len(received) == 1
    unsubscribe()
    registry.emit(schema.name, "changed", {"latitude": 4, "longitude": 5})
    assert len(received) == 1


def test_cancelling_typed_native_call_releases_native_work(location_contract: ModuleSchema) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class Transport:
        def call(self, module: str, method: str, envelope: str) -> str:
            request = json.loads(envelope)
            calls.append((method, request))
            return json.dumps({"pending": True} if method == "locate" else {"ok": True})

    async def exercise() -> None:
        task = asyncio.create_task(
            BridgeModule("TypedLocationTest", Transport()).call_async("locate", hint=Coordinate(1, 2))
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert [method for method, _ in calls] == ["locate", "_pn_cancel"]
    assert calls[1][1]["args"]["call_id"] == calls[0][1]["call_id"]
