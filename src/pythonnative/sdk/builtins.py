"""Native contracts derived from the annotated built-in Python factories."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from typing import Any, Callable

from ..style import Style
from .schema import COMPONENTS, ComponentSchema, NativeField, register_schema, type_schema

# These types own native child layout or physical child presentation.
CONTAINERS = frozenset(
    {"View", "Column", "Row", "ScrollView", "Screen", "ScreenStack", "Modal", "Portal", "VirtualList"}
)


def install(factories: dict[str, Any]) -> None:
    """Compile ordinary Python annotations into the shared native contract."""
    style_fields = {name: type_schema(annotation) for name, annotation in typing.get_type_hints(Style).items()}
    for name, factory in factories.items():
        if not inspect.isfunction(factory) or not name[:1].isupper() or name.startswith("_"):
            continue
        signature = inspect.signature(factory)
        hints = typing.get_type_hints(factory)
        fields: list[Any] = []
        for key, parameter in signature.parameters.items():
            if key in {"style", "ref", "key"} or parameter.kind in {parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD}:
                continue
            annotation = hints.get(key, Any)
            default = parameter.default
            fields.append(
                (key, annotation)
                if default is inspect.Parameter.empty
                else (key, annotation, dataclasses.field(default=default))
            )
        props_type = dataclasses.make_dataclass(f"{name}Props", fields, frozen=True, kw_only=True)
        schema = ComponentSchema.from_dataclass(
            name, props_type, measurement="container" if name in CONTAINERS else "intrinsic"
        )
        wire = dict(style_fields) | schema.props
        wire.update(ref={}, on_layout=type_schema(Callable[..., Any]))
        for key in wire:
            wire[key] = dict(wire[key])
            wire[key]["native"] = dataclasses.asdict(
                NativeField(
                    invalidates_layout=key in style_fields or key in {"text", "value", "title", "source", "spans"},
                    recreate=key in {"multiline"},
                    animated=key
                    in {
                        "opacity",
                        "background_color",
                        "color",
                        "rotate",
                        "translate_x",
                        "translate_y",
                        "scale",
                        "scale_x",
                        "scale_y",
                    },
                )
            )
        if name == "Text":
            wire.update(text={"type": "string"}, spans={"type": "array"})
        register_schema(dataclasses.replace(schema, props=wire, required=()))
    base = COMPONENTS["View"]
    for name, extra in {
        "Screen": {"route_key": {"type": "string"}, "title": {"type": "string"}, "active": {"type": "boolean"}},
        "ScreenStack": {"on_native_back": {"type": "event"}},
        "VirtualList": {
            "keys": {"type": "array"},
            "revision": {"type": "integer"},
            "count": {"type": "integer"},
            "estimated_item_size": {"type": "number"},
            "on_bind_row": {"type": "event"},
        },
    }.items():
        register_schema(ComponentSchema(name, base.props | extra, measurement="container"))


def validate_props(name: str, props: dict[str, Any]) -> None:
    """Check known built-in arguments while preserving composed internal props."""
    schema = COMPONENTS.get(name)
    if schema is None:
        return
    for key, value in props.items():
        if value is not None and key in schema.props:
            from .schema import validate

            validate(value, schema.props[key], f"{name}.{key}")
