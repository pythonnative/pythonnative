"""Python definitions for native props, events, commands, and modules."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .types import NativeField, decode_value, encode_value, type_schema, validate  # noqa: F401

# Runtime metadata crosses the bridge for built-in and third-party views alike.
RUNTIME_PROPS: dict[str, dict[str, Any]] = {
    "_pn_layout": {"type": "boolean", "native": {"invalidates_layout": False}},
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

from ..bridge.commits import PROTOCOL_VERSION  # noqa: E402

YOGA_VERSION = "3.2.1"
"""The Yoga release every layout engine (native, WebAssembly, headless) embeds."""

BUILTIN_CONTRACTS = "_builtin_contracts.json"
"""Generated file, beside this module, holding the built-in contracts."""

_fingerprint_cache: tuple[Any, str] | None = None


def register_schema(schema: ComponentSchema | ModuleSchema) -> None:
    """Register the contract used to generate and validate a native extension."""
    if isinstance(schema, ComponentSchema):
        COMPONENTS[schema.name] = schema
    else:
        MODULES[schema.name] = schema


def manifest() -> dict[str, Any]:
    """Return deterministic native metadata for code generation and tooling."""
    return {
        "protocol": PROTOCOL_VERSION,
        "yoga": YOGA_VERSION,
        "components": {name: dataclasses.asdict(value) for name, value in sorted(COMPONENTS.items())},
        "modules": {name: dataclasses.asdict(value) for name, value in sorted(MODULES.items())},
    }


def _registry_identity() -> tuple[Any, ...]:
    """Identify the registered contract objects without serializing them."""
    return (
        tuple((name, id(value)) for name, value in COMPONENTS.items()),
        tuple((name, id(value)) for name, value in MODULES.items()),
    )


def _hash_manifest(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, default=str).encode()).hexdigest()


def fingerprint() -> str:
    """Hash the native contract; incompatible dev clients require rebuilding.

    The hash is cached until a contract is registered or removed, so the
    startup handshake doesn't serialize the manifest again.
    """
    global _fingerprint_cache
    identity = _registry_identity()
    if _fingerprint_cache is None or _fingerprint_cache[0] != identity:
        _fingerprint_cache = (identity, _hash_manifest(manifest()))
    return _fingerprint_cache[1]


def _schema_document(schema: ComponentSchema | ModuleSchema) -> str:
    return json.dumps(dataclasses.asdict(schema), sort_keys=True, default=str)


def _component(value: Mapping[str, Any], props: dict[str, dict[str, Any]] | None = None) -> ComponentSchema:
    """Rebuild a component contract from JSON, restoring tuple fields."""
    return ComponentSchema(
        value["name"],
        dict(value["props"]) if props is None else props,
        tuple(value.get("required", ())),
        dict(value.get("defaults", {})),
        value.get("measurement", "intrinsic"),
        dict(value.get("commands", {})),
        tuple(value.get("platforms", ("ios", "android", "web"))),
    )


def _check_versions(document: Mapping[str, Any]) -> None:
    if document.get("protocol") != PROTOCOL_VERSION or document.get("yoga") != YOGA_VERSION:
        raise ValueError(f"Native contracts require protocol {PROTOCOL_VERSION} and Yoga {YOGA_VERSION}")


def load_manifest(document: Mapping[str, Any]) -> None:
    """Load declarative extension contracts without importing target binaries."""
    _check_versions(document)
    pending: list[ComponentSchema | ModuleSchema] = []
    for group, registered in (("components", COMPONENTS), ("modules", MODULES)):
        for name, value in document.get(group, {}).items():
            if not name.isidentifier() or value.get("name") != name:
                raise ValueError(f"Invalid native contract name: {name!r}")
            schema: ComponentSchema | ModuleSchema = (
                _component(value) if group == "components" else ModuleSchema(**value)
            )
            old = registered.get(name)
            if old is not None and _schema_document(old) != _schema_document(schema):
                raise ValueError(f"Conflicting native contract: {name}")
            if old is None:
                pending.append(schema)
    for schema in pending:
        register_schema(schema)


def encode_builtin_contracts(document: Mapping[str, Any]) -> str:
    """Serialize a manifest compactly, storing each distinct field schema once.

    Most components repeat the same style and accessibility fields, so
    components refer to an interned ``fields`` table by index. Loading
    rebuilds plain prop dictionaries that share those field schemas.
    """
    fields: list[Any] = []
    index: dict[str, int] = {}
    components = {}
    for name, value in document["components"].items():
        props = {}
        for key, prop in value["props"].items():
            # Declaration order matters to code generation, so fields are
            # interned by their exact encoding, never a sorted one.
            encoded = json.dumps(prop)
            if encoded not in index:
                index[encoded] = len(fields)
                fields.append(prop)
            props[key] = index[encoded]
        components[name] = {**value, "props": props}
    compact = {
        "protocol": document["protocol"],
        "yoga": document["yoga"],
        "fingerprint": _hash_manifest(document),
        "fields": fields,
        "components": components,
        "modules": document["modules"],
    }
    return json.dumps(compact, separators=(",", ":")) + "\n"


def load_builtin_contracts() -> bool:
    """Register the generated built-in contracts; return whether they were current.

    ``pn codegen`` derives these from the annotated factories (see
    ``pythonnative.sdk.builtins``) and writes them beside this module, so an
    app's startup reads one JSON document instead of evaluating type hints.
    """
    global _fingerprint_cache
    path = Path(__file__).with_name(BUILTIN_CONTRACTS)
    try:
        document = json.loads(path.read_bytes())
    except FileNotFoundError:
        return False
    if document.get("protocol") != PROTOCOL_VERSION or document.get("yoga") != YOGA_VERSION:
        # A development checkout whose generated file predates a protocol
        # change; the caller derives the contracts instead.
        return False
    fields = document["fields"]
    for name, value in document["components"].items():
        register_schema(_component(value, {key: fields[i] for key, i in value["props"].items()}))
    for name, value in document["modules"].items():
        register_schema(ModuleSchema(**value))
    _fingerprint_cache = (_registry_identity(), document["fingerprint"])
    return True


def load_bundled_contracts() -> None:
    """Install the plugin contracts compiled into this embedded application.

    The build writes only the contracts its plugins add, plus the
    fingerprint of everything the native library was generated from, so
    the startup handshake doesn't hash the manifest again.
    """
    global _fingerprint_cache
    from importlib.resources import files

    path = files("pythonnative").joinpath("_native_contracts.json")
    if not path.is_file():
        return
    document = json.loads(path.read_text(encoding="utf-8"))
    load_manifest(document)
    if isinstance(document.get("fingerprint"), str):
        _fingerprint_cache = (_registry_identity(), document["fingerprint"])


def validate_props(name: str, props: dict[str, Any]) -> None:
    """Validate resolved factory arguments, including reserved runtime fields."""
    schema = COMPONENTS.get(name)
    if schema is not None:
        schema.validate({key: value for key, value in props.items() if value is not None})
