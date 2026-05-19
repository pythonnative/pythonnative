"""Public extension surface for PythonNative.

The ``pythonnative.sdk`` package collects the *stable* extension
contract that third-party packages rely on: the
[`ViewHandler`][pythonnative.sdk.ViewHandler] protocol, the
[`Style`][pythonnative.sdk.Style] type, the
[`@native_component`][pythonnative.sdk.native_component] registration
decorator, and an
[`element_factory`][pythonnative.sdk.element_factory] helper for
producing strongly-typed element constructors.

A custom native component is three things:

1. A typed, frozen [`Props`][pythonnative.sdk.Props] dataclass listing
   the public properties the component accepts.
2. One or more
   [`ViewHandler`][pythonnative.sdk.ViewHandler] subclasses (one per
   target platform) implementing creation, update, and child management
   for the underlying native widget.
3. A registration call (the
   [`@native_component`][pythonnative.sdk.native_component] decorator,
   or
   [`register_component`][pythonnative.sdk.register_component] for
   imperative use) that binds the props type and handler into the
   process-wide registry.

Once registered, the component appears alongside the built-ins: the
reconciler, layout engine, and Fast Refresh treat it identically.

PyPI packages can ship handlers without users importing them
explicitly by declaring an entry point in the
``pythonnative.handlers`` group; PythonNative discovers and imports
those modules the first time the registry is asked for a handler.

Example:
    ```python
    from dataclasses import dataclass
    import pythonnative as pn
    from pythonnative.sdk import (
        Props,
        ViewHandler,
        element_factory,
        native_component,
    )


    @dataclass(frozen=True)
    class BadgeProps(Props):
        text: str = ""
        color: str = "#FF3B30"
        style: pn.StyleProp = None


    @native_component("Badge", props=BadgeProps, platforms=("ios",))
    class IOSBadgeHandler(ViewHandler):
        def create(self, props):
            ...

        def update(self, view, changed):
            ...


    Badge = element_factory("Badge")

    @pn.component
    def App():
        return pn.Column(
            Badge(text="3", color="#0A84FF"),
            pn.Text("Inbox"),
        )
    ```
"""

from ..element import Element
from ..native_views.base import ViewHandler, parse_color_int
from ..style import (
    Color,
    Dimension,
    EdgeInsets,
    EdgeValue,
    FlexDirection,
    JustifyContent,
    Overflow,
    Position,
    Style,
    StyleProp,
    TransformSpec,
    style,
)
from ._components import (
    ENTRY_POINT_GROUP,
    Props,
    element_factory,
    get_props_type,
    install_into_registry,
    list_components,
    native_component,
    register_component,
    unregister_component,
)

__all__ = [
    # Core types
    "Element",
    "ViewHandler",
    # Style types
    "Color",
    "Dimension",
    "EdgeInsets",
    "EdgeValue",
    "FlexDirection",
    "JustifyContent",
    "Overflow",
    "Position",
    "Style",
    "StyleProp",
    "TransformSpec",
    "style",
    # SDK helpers (re-exported so users only import from one place)
    "parse_color_int",
    # Native-component SDK
    "ENTRY_POINT_GROUP",
    "Props",
    "element_factory",
    "get_props_type",
    "install_into_registry",
    "list_components",
    "native_component",
    "register_component",
    "unregister_component",
]
