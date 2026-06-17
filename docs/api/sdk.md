# SDK

`pythonnative.sdk` is the public extension API for adding new native
widgets to PythonNative. It re-exports the
[`Element`][pythonnative.element.Element] descriptor, the
[`ViewHandler`][pythonnative.native_views.base.ViewHandler] protocol,
and the typed style primitives so plugin authors only need a single
import path. The reference here documents the symbols that are
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
| [`ViewHandler`][pythonnative.native_views.base.ViewHandler] | [Native views](native_views.md) |
| [`Style`][pythonnative.style.Style], [`StyleProp`][pythonnative.style.StyleProp], [`Color`][pythonnative.style.Color], [`Dimension`][pythonnative.style.Dimension], [`EdgeInsets`][pythonnative.style.EdgeInsets], [`EdgeValue`][pythonnative.style.EdgeValue], `FlexDirection`, `JustifyContent`, `Overflow`, `Position`, [`TransformSpec`][pythonnative.style.TransformSpec], [`style`][pythonnative.style.style] | [Style](style.md) |
| `parse_color_int` | `pythonnative.native_views.base` |

## Custom-component primitives

::: pythonnative.sdk
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      members:
        - ENTRY_POINT_GROUP
        - Props
        - native_component
        - register_component
        - unregister_component
        - element_factory
        - install_into_registry
        - list_components
        - get_props_type

## Entry-point discovery

Third-party packages can register handlers automatically by exposing
an entry point in the `pythonnative.handlers` group (the value of
[`ENTRY_POINT_GROUP`][pythonnative.sdk.ENTRY_POINT_GROUP]). The first
call to [`get_registry()`][pythonnative.native_views.get_registry]
loads every registered entry point exactly once. A misbehaving plugin
raises an exception that is caught and logged; it never breaks
PythonNative startup.

```toml
# In your plugin's pyproject.toml
[project.entry-points."pythonnative.handlers"]
my_widget = "my_pkg:register"
```

The function pointed at by the entry point should perform whatever
imports are needed to call
[`@native_component`][pythonnative.sdk.native_component] or
[`register_component`][pythonnative.sdk.register_component].

## Next steps

- [Custom native components guide](../guides/custom-native-components.md)
  walks through a complete `Badge` widget across iOS and Android.
- [Native views (concept)](../concepts/native-views.md) describes the
  reconciler boundary the SDK plugs into.
- [Native views API](native_views.md) documents the runtime registry
  the SDK installs handlers onto.
