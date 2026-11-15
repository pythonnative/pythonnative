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

PyPI packages ship both with a ``pn_plugin.json`` beside the native sources.
``pn build`` finds it in the wheels resolved for each device, without importing
them, and compiles the sources into the app; see the Native plugins guide. A
``pythonnative.handlers`` entry point registers a package's Python side for apps
that don't import it. [`plugin_module`][pythonnative.sdk.plugin.plugin_module]
and [`plugin_component`][pythonnative.sdk.plugin.plugin_component] declare a plugin's Python side.

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

from typing import TYPE_CHECKING, Any

from ..element import Element
from ..mutations import UNSET, UnsetType
from ..native_modules.registry import (
    NativeModule,
    NativeModuleError,
    PythonModule,
    emit,
    event_stream,
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
from .schema import ComponentSchema, ModuleSchema, NativeField, register_schema

if TYPE_CHECKING:
    from .plugin import PluginNotEnabledError, plugin_component, plugin_module

# Only capability facades declare plugins, so ``sdk.plugin`` loads on first use.
_LAZY = frozenset({"PluginNotEnabledError", "plugin_component", "plugin_module"})


def __getattr__(name: str) -> Any:
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import plugin

    value = getattr(plugin, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY)


__all__ = [
    "UNSET",
    "UnsetType",
    "ComponentSchema",
    "ModuleSchema",
    "NativeField",
    "register_schema",
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
    # Native-plugin SDK
    "PluginNotEnabledError",
    "plugin_component",
    "plugin_module",
    # Native-module SDK
    "event_stream",
    "NativeModule",
    "NativeModuleError",
    "PythonModule",
    "emit",
    "native_module",
    "register_python_module",
]
