"""Public extension surface for PythonNative.

The ``pythonnative.sdk`` package collects the *stable* extension
contract that third-party packages rely on: the
[`Style`][pythonnative.sdk.Style] type, the
[`define_component`][pythonnative.sdk.define_component] helper that
declares a custom native component and returns its typed element
factory, [`element_factory`][pythonnative.sdk.element_factory] for
rebuilding that factory elsewhere, and the native module registry
([`native_module`][pythonnative.sdk.native_module],
[`register_python_module`][pythonnative.sdk.register_python_module]).

A custom native component is three things:

1. A typed, frozen [`Props`][pythonnative.sdk.Props] dataclass listing
   the public properties the component accepts.
2. A Swift ``PNComponentManager`` and a Kotlin ``ComponentManager``
   registered under the component's name by the package's native
   plugin (``pn_plugin.json`` next to ``ios/`` and ``android/`` source
   folders; see ``docs/guides/custom-native-components.md``).
3. A ``define_component(name, props)`` call in Python that declares the
   element name, binds its props type, and returns the element factory.

Once defined, the component appears alongside the built-ins: the
reconciler, layout engine, commit validator, contract generator, and
Fast Refresh treat it identically. The browser preview draws it as a
labeled placeholder; headless tests render it into the
[`FakeBackend`][pythonnative.testing.FakeBackend] like any element.

A native module (device API without a view) follows the same split: a
Swift / Kotlin class registered by name in the plugin, a Python facade
that calls ``native_module(name).call(...)``, and optionally a Python
implementation registered with ``register_python_module`` for the
browser preview and tests.

PyPI packages can ship both without users importing them explicitly
by declaring entry points in the ``pythonnative.handlers`` (Python
side) and ``pythonnative.plugins`` (native source) groups; ``pn build``
compiles the native sources into the app.

Example:
    ```python
    from dataclasses import dataclass
    import pythonnative as pn
    from pythonnative.sdk import Props, define_component


    @dataclass(frozen=True)
    class BadgeProps(Props):
        text: str = ""
        color: str = "#FF3B30"
        style: pn.StyleProp = None


    Badge = define_component("Badge", BadgeProps)


    @pn.component
    def App():
        return pn.Column(
            Badge(text="3", color="#0A84FF"),
            pn.Text("Inbox"),
        )
    ```
"""

from ..element import Element
from ..mutations import UNSET, UnsetType
from ..native_modules.registry import (
    NativeModule,
    NativeModuleError,
    PythonModule,
    emit,
    native_module,
    register_python_module,
)
from ..native_views import parse_color_int
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
    define_component,
    element_factory,
    get_props_type,
    list_components,
    unregister_component,
)
from .codegen import generate
from .schema import ComponentSchema, ModuleSchema, NativeField, register_schema

__all__ = [
    "UNSET",
    "UnsetType",
    "ComponentSchema",
    "ModuleSchema",
    "NativeField",
    "register_schema",
    "generate",
    # Core types
    "Element",
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
    "define_component",
    "element_factory",
    "get_props_type",
    "list_components",
    "unregister_component",
    # Native-module SDK
    "NativeModule",
    "NativeModuleError",
    "PythonModule",
    "emit",
    "native_module",
    "register_python_module",
]
