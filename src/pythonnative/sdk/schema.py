"""Python definitions for native props, events, commands, and modules."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import typing
from dataclasses import dataclass, field
from typing import Any, Mapping

from .types import NativeField, decode_value, encode_value, type_schema, validate  # noqa: F401

# Runtime metadata crosses the bridge for built-in and third-party views alike.
RUNTIME_PROPS: dict[str, dict[str, Any]] = {
    "_pn_events": {"type": "array", "items": {"type": "string"}},
    "_pn_animated_events": {"type": "object"},
    "_pn_list_key": {"type": "string"},
    "_pn_header_slot": {"enum": ["left", "right"]},
    "_pn_edit_revision": {"type": "integer"},
    "gestures": {"type": "array"},
}


@dataclass(frozen=True)
class ComponentSchema:
    """The portable contract shared by every renderer and the component SDK."""

    name: str
    props: dict[str, dict[str, Any]]
    required: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    measurement: str = "intrinsic"
    commands: dict[str, Any] = field(default_factory=dict)
    platforms: tuple[str, ...] = ("ios", "android", "web")

    @classmethod
    def from_dataclass(
        cls,
        name: str,
        props: type,
        *,
        measurement: str = "intrinsic",
        platforms: tuple[str, ...] = ("ios", "android"),
    ) -> ComponentSchema:
        """Describe a native widget with a frozen Python props dataclass."""
        if not dataclasses.is_dataclass(props):
            raise TypeError("Native props must be a dataclass")
        if not platforms or set(platforms) - {"ios", "android", "web"}:
            raise TypeError("Native component platforms must name ios, android, or web")
        record = type_schema(props)
        return cls(
            name,
            record["properties"],
            tuple(record["required"]),
            record["defaults"],
            measurement,
            platforms=platforms,
        )

    def validate(self, props: Mapping[str, Any], *, partial: bool = False, platform: str | None = None) -> None:
        """Validate a construction or a partial update against this contract."""
        if platform is not None and platform not in self.platforms:
            raise TypeError(f"{self.name} isn't supported on {platform}")
        if not partial:
            missing = set(self.required) - props.keys()
            if missing:
                raise TypeError(f"{self.name} requires {', '.join(sorted(missing))}")
        for key, value in props.items():
            if key not in self.props:
                raise TypeError(f"Unknown {self.name} prop {key!r}")
            platforms = self.props[key].get("native", {}).get("platforms")
            if platform is not None and platforms is not None and platform not in platforms:
                raise TypeError(f"{self.name}.{key} isn't supported on {platform}")
            from ..mutations import UNSET

            if partial and value is UNSET:
                if key in self.required:
                    raise TypeError(f"Cannot remove required {self.name}.{key}")
                continue
            validate(value, self.props[key], f"{self.name}.{key}")

    def validate_event(self, name: str, arguments: list[Any]) -> None:
        """Validate a typed callback payload before application code receives it."""
        if name.startswith("gesture:"):
            return
        schema = self.props.get(name, {})
        if name == "on_refresh":
            schema = self.props.get("refresh_control", {}).get("properties", {}).get(name, {})
        alternatives = schema.get("anyOf", [schema])
        event = next((item for item in alternatives if item.get("type") == "event"), None)
        if event is None:
            raise TypeError(f"Unknown event {self.name}.{name}")
        expected = event.get("arguments")
        if expected is not None:
            if len(arguments) != len(expected):
                raise TypeError(f"{self.name}.{name} requires {len(expected)} event arguments")
            for index, (value, field) in enumerate(zip(arguments, expected)):
                validate(value, field, f"{self.name}.{name}[{index}]")

    def decode_event(self, name: str, arguments: list[Any]) -> list[Any]:
        """Reconstruct declared payload records after validating an event."""
        self.validate_event(name, arguments)
        if name.startswith("gesture:"):
            return arguments
        schema = self.props.get(name, {})
        if name == "on_refresh":
            schema = self.props.get("refresh_control", {}).get("properties", {}).get(name, {})
        event = next(item for item in schema.get("anyOf", [schema]) if item.get("type") == "event")
        expected = event.get("arguments")
        return (
            arguments
            if expected is None
            else [
                decode_value(value, field, f"{self.name}.{name}[{index}]")
                for index, (value, field) in enumerate(zip(arguments, expected))
            ]
        )


@dataclass(frozen=True)
class ModuleSchema:
    """Typed native module methods, arguments, results, and async behavior."""

    name: str
    methods: dict[str, dict[str, Any]]
    events: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_protocol(cls, name: str, protocol: type, *, events: Mapping[str, Any] | None = None) -> ModuleSchema:
        """Read annotated methods from a Python protocol or interface class."""
        methods = {}
        for method_name, method in inspect.getmembers(protocol, inspect.isfunction):
            if method_name.startswith("_"):
                continue
            hints = typing.get_type_hints(method, include_extras=True)
            signature = inspect.signature(method)
            if any(
                param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD, param.POSITIONAL_ONLY)
                for key, param in signature.parameters.items()
                if key != "self"
            ):
                raise TypeError(f"Native method {name}.{method_name} requires named arguments")
            methods[method_name] = {
                "arguments": {key: type_schema(hints.get(key, Any)) for key in signature.parameters if key != "self"},
                "result": type_schema(hints.get("return", Any)),
                "async": inspect.iscoroutinefunction(method),
                "required": [
                    key
                    for key, param in signature.parameters.items()
                    if key != "self" and param.default is inspect.Parameter.empty
                ],
                "defaults": {
                    key: encode_value(param.default)
                    for key, param in signature.parameters.items()
                    if key != "self" and param.default is not inspect.Parameter.empty
                },
            }
        event_types = {event: type_schema(annotation) for event, annotation in (events or {}).items()}
        if any(not event.isidentifier() for event in event_types):
            raise TypeError("Native event names must be identifiers")
        return cls(name, methods, event_types)

    def validate_call(self, method: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and normalize a method invocation before crossing a bridge."""
        contract = self.methods.get(method)
        if contract is None:
            raise TypeError(f"Unknown command {self.name}.{method}")
        validate(
            arguments,
            {
                "type": "object",
                "properties": contract["arguments"],
                "required": contract.get("required", list(contract["arguments"])),
                "additionalProperties": False,
            },
            f"{self.name}.{method}",
        )
        values = {**contract.get("defaults", {}), **arguments}
        return {
            key: decode_value(value, contract["arguments"][key], f"{self.name}.{method}.{key}")
            for key, value in values.items()
        }

    def decode_event(self, event: str, payload: Any) -> Any:
        """Validate and restore the declared Python payload of a module event."""
        if event not in self.events:
            raise TypeError(f"Unknown native event {self.name}.{event}")
        return decode_value(payload, self.events[event], f"{self.name}.{event}")

    def validate_result(self, method: str, result: Any) -> Any:
        """Reject a native result that doesn't satisfy its declared return type."""
        contract = self.methods.get(method)
        if contract is None:
            raise TypeError(f"Unknown command {self.name}.{method}")
        validate(result, contract["result"], f"{self.name}.{method} result")
        return decode_value(result, contract["result"], f"{self.name}.{method} result")


COMPONENTS: dict[str, ComponentSchema] = {}
MODULES: dict[str, ModuleSchema] = {}


def register_schema(schema: ComponentSchema | ModuleSchema) -> None:
    """Register the contract used to generate and validate a native extension."""
    if isinstance(schema, ComponentSchema):
        COMPONENTS[schema.name] = schema
    else:
        MODULES[schema.name] = schema


def manifest() -> dict[str, Any]:
    """Return deterministic native metadata for code generation and tooling."""
    return {
        "protocol": 3,
        "yoga": "3.2.1",
        "components": {name: dataclasses.asdict(value) for name, value in sorted(COMPONENTS.items())},
        "modules": {name: dataclasses.asdict(value) for name, value in sorted(MODULES.items())},
    }


def fingerprint() -> str:
    """Hash the native contract; incompatible dev clients require rebuilding."""
    return hashlib.sha256(json.dumps(manifest(), sort_keys=True, default=str).encode()).hexdigest()


def load_manifest(document: Mapping[str, Any]) -> None:
    """Load declarative extension contracts without importing target binaries."""
    if document.get("protocol") != 3 or document.get("yoga") != "3.2.1":
        raise ValueError("Native contracts require protocol 3 and Yoga 3.2.1")
    pending = []
    for group, constructor, registered in (
        ("components", ComponentSchema, COMPONENTS),
        ("modules", ModuleSchema, MODULES),
    ):
        for name, value in document.get(group, {}).items():
            if not name.isidentifier() or value.get("name") != name:
                raise ValueError(f"Invalid native contract name: {name!r}")
            schema = constructor(**value)
            old = registered.get(name)
            if old is not None and json.dumps(dataclasses.asdict(old), sort_keys=True, default=str) != json.dumps(
                dataclasses.asdict(schema), sort_keys=True, default=str
            ):
                raise ValueError(f"Conflicting native contract: {name}")
            pending.append(schema)
    for schema in pending:
        register_schema(schema)


def load_bundled_contracts() -> None:
    """Install the exact contracts compiled into this embedded application."""
    from importlib.resources import files

    path = files("pythonnative").joinpath("_native_contracts.json")
    if path.is_file():
        load_manifest(json.loads(path.read_text(encoding="utf-8")))
