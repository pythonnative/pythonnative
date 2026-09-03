"""Public extension surface for PythonNative.

The ``pythonnative.sdk`` package collects the *stable* extension
contract that third-party packages rely on: the
[`Style`][pythonnative.sdk.Style] type, the
[`@native_component`][pythonnative.sdk.native_component] /
[`register_component`][pythonnative.sdk.register_component]
registration helpers, the
[`element_factory`][pythonnative.sdk.element_factory] helper for
producing strongly-typed element constructors, the
[`ViewHandler`][pythonnative.sdk.ViewHandler] protocol for off-device
stand-ins, and the native module registry
([`native_module`][pythonnative.sdk.native_module],
[`register_python_module`][pythonnative.sdk.register_python_module]).

A custom native component is three things:

1. A typed, frozen [`Props`][pythonnative.sdk.Props] dataclass listing
   the public properties the component accepts.
2. A Swift ``PNComponentManager`` and a Kotlin ``ComponentManager``
   registered under the component's name by the package's native
   plugin (``pn_plugin.json`` next to ``ios/`` and ``android/`` source
   folders; see ``docs/guides/custom-components.md``).
3. A registration call in Python
   ([`register_component`][pythonnative.sdk.register_component], or the
   [`@native_component`][pythonnative.sdk.native_component] decorator
   when you also supply a desktop
   [`ViewHandler`][pythonnative.sdk.ViewHandler] for ``pn preview``)
   that declares the element name and binds its props type.

Once registered, the component appears alongside the built-ins: the
reconciler, layout engine, and Fast Refresh treat it identically.

A native module (device API without a view) follows the same split: a
Swift / Kotlin class registered by name in the plugin, a Python facade
that calls ``native_module(name).call(...)``, and optionally a Python
implementation registered with ``register_python_module`` for desktop
and tests.

PyPI packages can ship both without users importing them explicitly
by declaring entry points in the ``pythonnative.handlers`` (Python
side) and ``pythonnative.plugins`` (native source) groups; ``pn build``
compiles the native sources into the app.

Example:
    ```python
    from dataclasses import dataclass
    import pythonnative as pn
    from pythonnative.sdk import Props, element_factory, register_component


    @dataclass(frozen=True)
    class BadgeProps(Props):
        text: str = ""
        color: str = "#FF3B30"
        style: pn.StyleProp = None


    register_component(name="Badge", props=BadgeProps)
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
from ..native_modules.registry import (
    NativeModule,
    NativeModuleError,
    PythonModule,
    emit,
    native_module,
    register_python_module,
)
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
    get_desktop_handler,
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
    "get_desktop_handler",
    "get_props_type",
    "install_into_registry",
    "list_components",
    "native_component",
    "register_component",
    "unregister_component",
    # Native-module SDK
    "NativeModule",
    "NativeModuleError",
    "PythonModule",
    "emit",
    "native_module",
    "register_python_module",
]
