# SDK

`pythonnative.sdk` is the public extension API for adding new native
widgets and device modules to PythonNative. It re-exports the
[`Element`][pythonnative.element.Element] descriptor, the typed style
primitives, and the native module registry so plugin authors only need
a single import path. The reference here documents the symbols that are
*unique* to the SDK module; the re-exports are documented on their
canonical pages and linked below.

The full walkthrough lives in
[Custom native components](../guides/custom-native-components.md);
this page is the symbol-level reference.

## Re-exports

The following names are re-exported from `pythonnative.sdk` for
convenience and are documented on their canonical pages:

| Symbol | Defined in |
|---|---|
| [`Element`][pythonnative.element.Element] | [Element](element.md) |
| [`UNSET`][pythonnative.mutations.UNSET], [`UnsetType`][pythonnative.mutations.UnsetType] | [Mutation ops](mutations.md) |
| [`Style`][pythonnative.style.Style], [`StyleProp`][pythonnative.style.StyleProp], [`Color`][pythonnative.style.Color], [`Dimension`][pythonnative.style.Dimension], [`EdgeInsets`][pythonnative.style.EdgeInsets], [`EdgeValue`][pythonnative.style.EdgeValue], `FlexDirection`, `JustifyContent`, `Overflow`, `Position`, [`TransformSpec`][pythonnative.style.TransformSpec], [`style`][pythonnative.style.style] | [Style](style.md) |
| [`NativeModule`][pythonnative.native_modules.registry.NativeModule], [`NativeModuleError`][pythonnative.native_modules.registry.NativeModuleError], [`PythonModule`][pythonnative.native_modules.registry.PythonModule], [`native_module`][pythonnative.native_modules.registry.native_module], [`register_python_module`][pythonnative.native_modules.registry.register_python_module], [`emit`][pythonnative.native_modules.registry.emit] | [Native modules](native_modules.md) |
| [`parse_color_int`][pythonnative.native_views.parse_color_int] | [Native views](native_views.md) |

## Custom-component primitives

::: pythonnative.sdk
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      members:
        - ENTRY_POINT_GROUP
        - Props
        - define_component
        - element_factory
        - unregister_component
        - list_components
        - get_props_type

## Contract schemas

`define_component` registers the props dataclass as a
[`ComponentSchema`][pythonnative.sdk.schema.ComponentSchema]; native
modules declare a [`ModuleSchema`][pythonnative.sdk.schema.ModuleSchema]
from a `Protocol`. Field-level options such as layout invalidation and
platform support are declared with
[`NativeField`][pythonnative.sdk.schema.NativeField]. `pn codegen`
compiles the registered schemas into Swift and Kotlin; see
[Generated native contracts](../guides/native-contracts.md).

::: pythonnative.sdk.schema
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      members:
        - ComponentSchema
        - ModuleSchema
        - NativeField
        - register_schema

## Entry-point discovery

Third-party packages can define components automatically by exposing
an entry point in the `pythonnative.handlers` group (the value of
[`ENTRY_POINT_GROUP`][pythonnative.sdk.ENTRY_POINT_GROUP]). The view
backend loads every registered entry point exactly once, before the
first native commit is validated. A misbehaving plugin raises an
exception that is caught and logged; it never breaks PythonNative
startup.

```toml
# In your plugin's pyproject.toml
[project.entry-points."pythonnative.handlers"]
my_widget = "my_pkg:register"
```

The module pointed at by the entry point should perform whatever
imports are needed to run its
[`define_component`][pythonnative.sdk.define_component] calls.

## Next steps

- [Custom native components guide](../guides/custom-native-components.md)
  walks through a complete `Badge` widget across iOS and Android.
- [Native views (concept)](../concepts/native-views.md) describes the
  reconciler boundary the SDK plugs into.
- [Native views API](native_views.md) documents the runtime backend
  that commits custom elements alongside the built-ins.
