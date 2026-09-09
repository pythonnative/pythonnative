"""Native contracts derived from the annotated built-in Python factories."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from typing import Any, Callable

from ..layout import LAYOUT_STYLE_KEYS
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
                    invalidates_layout=key in LAYOUT_STYLE_KEYS
                    or key
                    in {
                        "text",
                        "value",
                        "title",
                        "source",
                        "spans",
                        "font_size",
                        "font_family",
                        "font_weight",
                        "bold",
                        "italic",
                        "letter_spacing",
                        "line_height",
                        "number_of_lines",
                        "multiline",
                    },
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
            wire.update(
                text={"type": "string", "native": {"invalidates_layout": True}},
                spans={"type": "array", "native": {"invalidates_layout": True}},
            )
        register_schema(dataclasses.replace(schema, props=wire, required=()))
    base = COMPONENTS["View"]
    extras: dict[str, dict[str, Any]] = {
        "Screen": {
            "route_key": {"type": "string"},
            "title": {"type": "string"},
            "active": {"type": "boolean"},
            "options": {"type": "object"},
        },
        "TabBar": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "icon": {"type": "string"},
                        "badge": {"type": "string"},
                    },
                    "required": ["name", "title"],
                    "additionalProperties": False,
                },
            },
            "active_tab": {"type": "string"},
            "on_tab_select": {"type": "event", "arguments": [{"type": "string"}]},
        },
        "ScreenStack": {"on_native_back": {"type": "event"}},
        "VirtualList": {
            "keys": {"type": "array"},
            "revision": {"type": "integer"},
            "count": {"type": "integer"},
            "estimated_item_size": {"type": "number"},
            "on_bind_row": {"type": "event"},
            "on_scroll": {"type": "event"},
            "horizontal": {"type": "boolean"},
            "row_heights": {"type": "array", "items": {"type": "number"}},
            "item_revisions": {"type": "array", "items": {"type": "integer"}},
            "shows_scroll_indicator": {"type": "boolean"},
            "refresh_control": {"type": "object"},
        },
    }
    for name, extra in extras.items():
        register_schema(ComponentSchema(name, base.props | extra, measurement="container"))

    # Reserved fields travel through the same validation path as public fields.
    runtime: dict[str, Any] = {
        "_pn_events": {"type": "array", "items": {"type": "string"}},
        "_pn_animated_events": {"type": "object"},
        "_pn_list_key": {"type": "string"},
        "_pn_edit_revision": {"type": "integer"},
        "gestures": {"type": "array"},
    }
    from ..navigation.screen import ScreenOptions

    COMPONENTS["Screen"].props.update(
        {name: type_schema(value) for name, value in typing.get_type_hints(ScreenOptions).items()}
    )
    refresh = COMPONENTS["RefreshControl"].props
    for name in ("ScrollView", "VirtualList"):
        COMPONENTS[name].props["refresh_control"] = {
            "type": "object",
            "properties": refresh,
            "additionalProperties": False,
        }
    from .commands import commands

    for name, schema in list(COMPONENTS.items()):
        register_schema(dataclasses.replace(schema, props=schema.props | runtime, commands=commands(name)))
    from .services import install_services

    install_services()


def validate_props(name: str, props: dict[str, Any]) -> None:
    """Validate resolved factory arguments, including reserved runtime fields."""
    schema = COMPONENTS.get(name)
    if schema is not None:
        schema.validate({key: value for key, value in props.items() if value is not None})
