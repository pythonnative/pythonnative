"""Python definitions for native props, events, commands, and modules."""

from __future__ import annotations

import collections.abc
import dataclasses
import enum
import hashlib
import inspect
import json
import math
import types
import typing
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class NativeField:
    """Native behavior attached to an annotated dataclass field.

    Use ``Annotated[T, NativeField(...)]`` for native-specific metadata.
    """

    invalidates_layout: bool = False
    recreate: bool = False
    animated: bool = False
    platforms: tuple[str, ...] = ("ios", "android", "web")
    description: str = ""


def type_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python annotation into a portable JSON type description."""
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is typing.Annotated:
        result = type_schema(args[0])
        for metadata in args[1:]:
            if isinstance(metadata, NativeField):
                result["native"] = dataclasses.asdict(metadata)
        return result
    if origin in (typing.Union, types.UnionType):
        return {"anyOf": [type_schema(arg) for arg in args]}
    if origin is typing.Literal:
        return {"enum": list(args)}
    if annotation is type(None):
        return {"type": "null"}
    if annotation in (str, bool, int, float):
        return {"type": {str: "string", bool: "boolean", int: "integer", float: "number"}[annotation]}
    if origin in (list, tuple, set, collections.abc.Sequence):
        return {"type": "array", "items": type_schema(args[0]) if args else {}}
    if origin in (dict, collections.abc.Mapping) or annotation is dict:
        return {"type": "object", "additionalProperties": type_schema(args[-1]) if args else {}}
    if origin in (typing.Callable, collections.abc.Callable):
        return {
            "type": "event",
            "arguments": [type_schema(arg) for arg in args[0]] if args and args[0] is not Ellipsis else None,
        }
    if inspect.isclass(annotation) and issubclass(annotation, enum.Enum):
        return {"enum": [value.value for value in annotation]}
    if dataclasses.is_dataclass(annotation) or typing.is_typeddict(annotation):
        hints = typing.get_type_hints(annotation, include_extras=True)
        required = (
            list(annotation.__required_keys__)
            if typing.is_typeddict(annotation)
            else [
                f.name
                for f in dataclasses.fields(annotation)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            ]
        )
        return {
            "type": "object",
            "properties": {name: type_schema(value) for name, value in hints.items()},
            "required": sorted(required),
            "additionalProperties": False,
        }
    if origin in (typing.Required, typing.NotRequired):
        return type_schema(args[0])
    return {}


def validate(value: Any, schema: Mapping[str, Any], path: str = "value") -> None:
    """Validate wire values without coercion or ambiguous boolean comparisons."""
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                validate(value, alternative, path)
                return
            except TypeError:
                pass
        raise TypeError(f"{path} does not match its annotation")
    if "enum" in schema:
        candidate = value.value if isinstance(value, enum.Enum) else value
        if not any(
            (type(candidate) is type(item) or type(candidate) in (int, float) and type(item) in (int, float))
            and candidate == item
            for item in schema["enum"]
        ):
            raise TypeError(f"{path} must be one of {schema['enum']!r}")
    kind = schema.get("type")
    checks = {
        "null": lambda: value is None,
        "string": lambda: isinstance(value, str),
        "boolean": lambda: type(value) is bool,
        "integer": lambda: type(value) in (int, float)
        and math.isfinite(value)
        and value == int(value)
        and abs(value) <= 2**53 - 1,
        "number": lambda: type(value) in (int, float) and math.isfinite(value),
        "array": lambda: isinstance(value, (list, tuple, set)),
        "object": lambda: isinstance(value, Mapping) or dataclasses.is_dataclass(value),
        "event": lambda: callable(value) or type(value) is bool,
    }
    if kind in checks and not checks[kind]():
        raise TypeError(f"{path} must be {kind}, received {type(value).__name__}")
    if kind == "array":
        for index, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{index}]")
    if kind == "object":
        values = dataclasses.asdict(value) if dataclasses.is_dataclass(value) and not isinstance(value, type) else value
        missing = set(schema.get("required", ())) - values.keys()
        if missing:
            raise TypeError(f"{path} requires {', '.join(sorted(missing))}")
        for name, item in values.items():
            if not isinstance(name, str):
                raise TypeError(f"{path} requires string keys")
            nested = schema.get("properties", {}).get(name, schema.get("additionalProperties", {}))
            if nested is False:
                raise TypeError(f"Unknown {path}.{name}")
            validate(item, nested if isinstance(nested, Mapping) else {}, f"{path}.{name}")


@dataclass(frozen=True)
class ComponentSchema:
    """The portable contract shared by every renderer and the component SDK."""

    name: str
    props: dict[str, dict[str, Any]]
    required: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    measurement: str = "intrinsic"
    commands: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dataclass(cls, name: str, props: type, *, measurement: str = "intrinsic") -> ComponentSchema:
        """Describe a native widget with a frozen Python props dataclass."""
        if not dataclasses.is_dataclass(props):
            raise TypeError("Native props must be a dataclass")
        hints = typing.get_type_hints(props, include_extras=True)
        required, defaults = [], {}
        for item in dataclasses.fields(props):
            if item.default is not dataclasses.MISSING:
                defaults[item.name] = item.default
            elif item.default_factory is not dataclasses.MISSING:
                defaults[item.name] = item.default_factory()
            else:
                required.append(item.name)
        return cls(
            name, {key: type_schema(value) for key, value in hints.items()}, tuple(required), defaults, measurement
        )

    def validate(self, props: Mapping[str, Any], *, partial: bool = False, platform: str | None = None) -> None:
        """Validate a construction or a partial update against this contract."""
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
            if partial and value is None:
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


@dataclass(frozen=True)
class ModuleSchema:
    """Typed native module methods, arguments, results, and async behavior."""

    name: str
    methods: dict[str, dict[str, Any]]

    @classmethod
    def from_protocol(cls, name: str, protocol: type) -> ModuleSchema:
        """Read annotated methods from a Python protocol or interface class."""
        methods = {}
        for method_name, method in inspect.getmembers(protocol, inspect.isfunction):
            if method_name.startswith("_"):
                continue
            hints = typing.get_type_hints(method, include_extras=True)
            signature = inspect.signature(method)
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
                    key: param.default
                    for key, param in signature.parameters.items()
                    if key != "self" and param.default is not inspect.Parameter.empty
                },
            }
        return cls(name, methods)

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
        return {**contract.get("defaults", {}), **arguments}

    def validate_result(self, method: str, result: Any) -> Any:
        """Reject a native result that doesn't satisfy its declared return type."""
        contract = self.methods.get(method)
        if contract is None:
            raise TypeError(f"Unknown command {self.name}.{method}")
        validate(result, contract["result"], f"{self.name}.{method} result")
        return result


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
        "protocol": 2,
        "yoga": "3.2.1",
        "components": {name: dataclasses.asdict(value) for name, value in sorted(COMPONENTS.items())},
        "modules": {name: dataclasses.asdict(value) for name, value in sorted(MODULES.items())},
    }


def fingerprint() -> str:
    """Hash the native contract; incompatible dev clients require rebuilding."""
    return hashlib.sha256(json.dumps(manifest(), sort_keys=True, default=str).encode()).hexdigest()


def load_manifest(document: Mapping[str, Any]) -> None:
    """Load declarative extension contracts without importing target binaries."""
    if document.get("protocol") != 2 or document.get("yoga") != "3.2.1":
        raise ValueError("Native contracts require protocol 2 and Yoga 3.2.1")
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
