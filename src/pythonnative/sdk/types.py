"""Portable Python type descriptions and lossless native value conversion.

Only declared records are reconstructed. Reading a manifest never imports an
extension; resolving a record happens when application code consumes a value.
"""

from __future__ import annotations

import collections.abc
import dataclasses
import enum
import importlib
import inspect
import math
import types
import typing
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NativeField:
    """Native behavior attached with ``Annotated[T, NativeField(...)]``."""

    invalidates_layout: bool = False
    recreate: bool = False
    animated: bool = False
    platforms: tuple[str, ...] = ("ios", "android", "web")
    description: str = ""
    python_only: bool = False


_record_types: dict[str, type] = {}


def _record_name(annotation: type) -> str:
    name = f"{annotation.__module__}:{annotation.__qualname__}"
    _record_types[name] = annotation
    return name


def resolve_type(name: str) -> type:
    """Resolve a declared Python record lazily, after its package is loaded."""
    if name not in _record_types:
        module, separator, qualname = name.partition(":")
        if not separator or "<locals>" in qualname:
            raise TypeError(f"Native record {name!r} must be declared at module scope")
        value: Any = importlib.import_module(module)
        for part in qualname.split("."):
            if not part.isidentifier():
                raise TypeError(f"Invalid native record name {name!r}")
            value = getattr(value, part)
        if not isinstance(value, type) or not (
            dataclasses.is_dataclass(value) or typing.is_typeddict(value) or issubclass(value, enum.Enum)
        ):
            raise TypeError(f"{name} isn't a native record or enum")
        _record_types[name] = value
    return _record_types[name]


def type_schema(annotation: Any, *, _parents: tuple[type, ...] = ()) -> dict[str, Any]:
    """Compile supported annotations; reject unsupported or recursive types."""
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if annotation is Any:
        return {"type": "json"}
    if origin is typing.Annotated:
        metadata = next((item for item in args[1:] if isinstance(item, NativeField)), None)
        result = {} if metadata is not None and metadata.python_only else type_schema(args[0], _parents=_parents)
        if metadata is not None:
            result["native"] = dataclasses.asdict(metadata)
        return result
    if origin in (typing.Required, typing.NotRequired):
        return type_schema(args[0], _parents=_parents)
    if origin in (typing.Union, types.UnionType):
        return {"anyOf": [type_schema(arg, _parents=_parents) for arg in args]}
    if origin is typing.Literal:
        values = [encode_value(arg) for arg in args]
        if not all(value is None or type(value) in (str, int, bool, float) for value in values):
            raise TypeError("Native literals must be JSON scalars")
        return {"enum": values}
    if annotation is None or annotation is type(None):
        return {"type": "null"}
    if annotation in (str, bool, int, float):
        return {"type": {str: "string", bool: "boolean", int: "integer", float: "number"}[annotation]}
    if origin in (list, tuple, set, frozenset, collections.abc.Sequence) or annotation in (list, tuple, set, frozenset):
        container = origin or annotation
        result: dict[str, Any] = {"type": "array"}
        if container is tuple and args and args[-1] is not Ellipsis:
            result["prefixItems"] = [type_schema(arg, _parents=_parents) for arg in args]
        else:
            result["items"] = type_schema(args[0], _parents=_parents) if args else {"type": "json"}
        if container in (tuple, set, frozenset):
            result["python_container"] = container.__name__
        return result
    if origin in (dict, collections.abc.Mapping) or annotation is dict:
        if args and args[0] is not str:
            raise TypeError("Native mappings require str keys")
        return {
            "type": "object",
            "additionalProperties": type_schema(args[1], _parents=_parents) if args else {"type": "json"},
        }
    if origin in (typing.Callable, collections.abc.Callable):
        return {
            "type": "event",
            "arguments": (
                [type_schema(arg, _parents=_parents) for arg in args[0]] if args and args[0] is not Ellipsis else None
            ),
        }
    if inspect.isclass(annotation) and issubclass(annotation, enum.Enum):
        return {
            "enum": [encode_value(value.value) for value in annotation],
            "python_type": _record_name(annotation),
            "python_kind": "enum",
        }
    if dataclasses.is_dataclass(annotation) or typing.is_typeddict(annotation):
        if annotation in _parents:
            raise TypeError(f"Recursive native record {annotation.__name__} isn't supported")
        hints = typing.get_type_hints(annotation, include_extras=True)
        for name in hints:
            if not name.isidentifier():
                raise TypeError(f"Native record field {name!r} must use a Python identifier")
        defaults = {}
        if typing.is_typeddict(annotation):
            required = set(annotation.__required_keys__)
            # Postponed annotations can make __required_keys__ incomplete.
            for key, hint in hints.items():
                if typing.get_origin(hint) is typing.NotRequired:
                    required.discard(key)
                elif typing.get_origin(hint) is typing.Required:
                    required.add(key)
        else:
            required = set()
            hints = {field.name: hints[field.name] for field in dataclasses.fields(annotation) if field.init}
            for field in dataclasses.fields(annotation):
                if not field.init:
                    hints.pop(field.name, None)
                    continue
                if field.default is not dataclasses.MISSING:
                    defaults[field.name] = encode_value(field.default)
                elif field.default_factory is not dataclasses.MISSING:
                    defaults[field.name] = encode_value(field.default_factory())
                else:
                    required.add(field.name)
        return {
            "type": "object",
            "properties": {name: type_schema(value, _parents=(*_parents, annotation)) for name, value in hints.items()},
            "required": sorted(required),
            "defaults": defaults,
            "additionalProperties": False,
            "python_type": _record_name(annotation),
            "python_kind": "typeddict" if typing.is_typeddict(annotation) else "dataclass",
        }
    raise TypeError(f"Unsupported native annotation {annotation!r}; use a dataclass, typed record, or JSON value")


def encode_value(value: Any, schema: Mapping[str, Any] | None = None, path: str = "value") -> Any:
    """Encode records, enums, and collections without dropping values or keys."""
    if schema is not None:
        validate(value, schema, path)
    if isinstance(value, enum.Enum):
        return encode_value(value.value, path=path)
    if value is None or type(value) in (str, bool, int):
        if type(value) is int and abs(value) > 2**53 - 1:
            raise TypeError(f"{path} exceeds the portable integer range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise TypeError(f"{path} must be finite")
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: encode_value(getattr(value, field.name), path=f"{path}.{field.name}")
            for field in dataclasses.fields(value)
            if field.init
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError(f"{path} requires string keys")
        return {key: encode_value(item, path=f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, (collections.abc.Sequence, set, frozenset)) and not isinstance(value, (str, bytes, bytearray)):
        items = [encode_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
        if isinstance(value, (set, frozenset)):
            import json

            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return items
    raise TypeError(f"{path}: {type(value).__name__} isn't a native value")


def decode_value(value: Any, schema: Mapping[str, Any], path: str = "value") -> Any:
    """Validate a result and reconstruct its declared Python value types."""
    validate(value, schema, path)
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                validate(value, alternative, path)
            except TypeError:
                continue
            return decode_value(value, alternative, path)
    if schema.get("python_kind") == "enum":
        return resolve_type(schema["python_type"])(value.value if isinstance(value, enum.Enum) else value)
    if schema.get("type") == "object":
        values = encode_value(value) if dataclasses.is_dataclass(value) else value
        fields = schema.get("properties", {})
        defaults = schema.get("defaults", {})
        decoded = {
            key: decode_value(item, fields.get(key, schema.get("additionalProperties", {})), f"{path}.{key}")
            for key, item in {**defaults, **values}.items()
        }
        if schema.get("python_kind") == "dataclass":
            return resolve_type(schema["python_type"])(**decoded)
        return decoded
    if schema.get("type") == "array":
        prefix = schema.get("prefixItems")
        items = [
            decode_value(item, prefix[index] if prefix is not None else schema.get("items", {}), f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
        constructor = {"tuple": tuple, "set": set, "frozenset": frozenset}.get(schema.get("python_container"), list)
        return constructor(items)
    if schema.get("type") == "integer":
        return int(value)
    if schema.get("type") == "number":
        return float(value)
    return value


def validate(value: Any, schema: Mapping[str, Any], path: str = "value") -> None:
    """Validate declared values without coercion or ambiguous comparisons."""
    if schema.get("native", {}).get("python_only"):
        return
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
        "integer": lambda: type(value) in (int, float) and abs(value) <= 2**53 - 1 and value == int(value),
        "number": lambda: (type(value) is int and abs(value) <= 2**53 - 1)
        or (type(value) is float and math.isfinite(value)),
        "array": lambda: isinstance(value, (collections.abc.Sequence, set, frozenset))
        and not isinstance(value, (str, bytes, bytearray)),
        "object": lambda: isinstance(value, Mapping) or dataclasses.is_dataclass(value) and not isinstance(value, type),
        "event": lambda: callable(value) or type(value) is bool,
    }
    if kind in checks and not checks[kind]():
        raise TypeError(f"{path} must be {kind}, received {type(value).__name__}")
    if kind == "json":
        encode_value(value, path=path)
    if kind == "array":
        prefix = schema.get("prefixItems")
        if prefix is not None and len(value) != len(prefix):
            raise TypeError(f"{path} requires {len(prefix)} tuple items")
        for index, item in enumerate(value):
            validate(item, prefix[index] if prefix is not None else schema.get("items", {}), f"{path}[{index}]")
    if kind == "object":
        values = (
            {f.name: getattr(value, f.name) for f in dataclasses.fields(value) if f.init}
            if dataclasses.is_dataclass(value)
            else value
        )
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
