"""Native contracts derived from the annotated built-in Python factories."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from typing import Any, Callable, Optional

from ..components.events import LayoutEvent
from ..layout import LAYOUT_STYLE_KEYS
from ..style import Style
from ..svg import SvgShape
from .schema import COMPONENTS, RUNTIME_PROPS, ComponentSchema, NativeField, register_schema, type_schema

# These types own native child layout or physical child presentation.
CONTAINERS = frozenset(
    {
        "View",
        "Column",
        "Row",
        "ScrollView",
        "Screen",
        "ScreenStack",
        "Modal",
        "Portal",
        "VirtualList",
        "LinearGradient",
        "BlurView",
    }
)


# Style shorthands ``resolve_style`` expands in Python; the wire carries
# only ``top`` / ``right`` / ``bottom`` / ``left``.
PYTHON_ONLY_STYLE_KEYS = frozenset({"inset", "inset_horizontal", "inset_vertical"})

# Factory keyword arguments the Python side consumes before the element is
# built: ``style`` is flattened into the props, ``ref`` and ``key`` belong to
# the reconciler, and ``content_container_style`` becomes an inner ``View``.
PYTHON_ONLY_PROPS = frozenset({"style", "ref", "key", "content_container_style"})


def install(factories: dict[str, Any]) -> None:
    """Compile ordinary Python annotations into the shared native contract."""
    style_fields = {
        name: type_schema(annotation)
        for name, annotation in typing.get_type_hints(Style).items()
        if name not in PYTHON_ONLY_STYLE_KEYS
    }
    for name, factory in factories.items():
        if name in {"ErrorBoundary", "Fragment", "Suspense", "FlatList", "SectionList"}:
            continue
        if not inspect.isfunction(factory) or not name[:1].isupper() or name.startswith("_"):
            continue
        signature = inspect.signature(factory)
        hints = typing.get_type_hints(factory)
        fields: list[Any] = []
        for key, parameter in signature.parameters.items():
            if key in PYTHON_ONLY_PROPS or parameter.kind in {parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD}:
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
            name,
            props_type,
            measurement="container" if name in CONTAINERS else "intrinsic",
            platforms=("ios", "android", "web"),
        )
        wire = dict(style_fields) | schema.props
        # Some controls supply their role internally rather than exposing an
        # override in their factory signature. It still crosses the bridge.
        wire.setdefault("accessibility_role", {"type": "string"})
        wire.update(ref={}, on_layout=type_schema(Callable[[LayoutEvent], Any]))
        if name == "Text":
            # Spans are pressable through ``Text(on_press=...)`` nesting;
            # native reports the tapped span's index.
            wire["on_span_press"] = {"type": "event", "arguments": [{"type": "integer"}]}
        if name == "TextInput":
            # The factory takes ``(start, end)`` and sends the record the
            # ``set_selection`` command also uses.
            from ..components.text import Selection

            wire["selection"] = type_schema(Optional[Selection])
        for key in wire:
            wire[key] = dict(wire[key])
            wire[key]["native"] = dataclasses.asdict(
                NativeField(
                    python_only=key == "ref",
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
                        "max_lines",
                        "ellipsize_mode",
                        "allow_font_scaling",
                        "text_transform",
                        "multiline",
                        "view_box",
                    },
                    recreate=key == "multiline" or (name == "ProgressBar" and key == "indeterminate"),
                    animated=key
                    in {
                        "opacity",
                        "background_color",
                        "color",
                        "rotate",
                        "rotate_x",
                        "rotate_y",
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
            # Internal: set by the stack navigator while the route has a
            # ``before_remove`` listener; iOS refuses the pop synchronously
            # and lets Python decide through ``on_native_back``.
            "guarded": {"type": "boolean"},
        },
        "TabBar": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "icon": {
                            "type": "object",
                            "properties": {
                                "shapes": {"type": "array", "items": type_schema(SvgShape)},
                                "view_box": {"type": "string"},
                                "uri": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                        "badge": {"type": "string"},
                    },
                    "required": ["name", "title"],
                    "additionalProperties": False,
                },
            },
            "active_tab": {"type": "string"},
            "on_tab_select": {"type": "event", "arguments": [{"type": "string"}]},
            # ``Tab.Navigator(tab_bar_style=...)`` and the navigation theme
            # (``background_color`` comes from the shared view props).
            "tint_color": {"type": "string"},
            "inactive_tint_color": {"type": "string"},
            "translucent": {"type": "boolean"},
            "shows_labels": {"type": "boolean"},
        },
        "ScreenStack": {"on_native_back": {"type": "event", "arguments": [{"type": "integer"}]}},
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

    from ..navigation.screen import PYTHON_ONLY_OPTIONS, ScreenOptions

    COMPONENTS["Screen"].props.update(
        {
            name: type_schema(value)
            for name, value in typing.get_type_hints(ScreenOptions).items()
            # Header slots are rendered by Python; tab icons travel on
            # ``TabBar.items`` after ``tab_icon_spec`` resolves them;
            # ``tab_bar_visible`` and ``freeze_on_blur`` are Python-side.
            if name not in PYTHON_ONLY_OPTIONS
        }
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
        register_schema(dataclasses.replace(schema, props=schema.props | RUNTIME_PROPS, commands=commands(name)))
    from .services import install_services

    install_services()


def validate_props(name: str, props: dict[str, Any]) -> None:
    """Validate resolved factory arguments, including reserved runtime fields."""
    schema = COMPONENTS.get(name)
    if schema is not None:
        schema.validate({key: value for key, value in props.items() if value is not None})
