# Native views

The boundary between PythonNative's element tree and concrete native
widgets. Each commit's diff is expressed as a flat list of
[mutation ops](mutations.md) referencing integer tags, applied through a
single
[`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations]
call on a [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry].
On device that registry is the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend],
which forwards the transaction to Swift and Kotlin component managers
over the [native bridge](bridge.md). The browser preview uses the same
backend with a WebSocket transport to the page. In tests it dispatches
to Python [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
objects (an in-memory fake).

::: pythonnative.native_views
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Mutation ops

The op types themselves are documented in [Mutation ops](mutations.md).

## Event routing

The registry and its dispatch entry point are documented in
[Events](events.md).

## Base classes

::: pythonnative.native_views.base
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## On-device backend

::: pythonnative.native_views.bridge_backend
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

!!! note "Component managers"
    The native implementations live in the templates:
    `PythonNativeKit/Sources/PythonNativeKit/Components` (Swift) and
    `pythonnative/src/main/java/com/pythonnative/runtime/components`
    (Kotlin). Their hooks are described in
    [Native views (concept)](../concepts/native-views.md#component-managers).

## Next steps

- Read the high-level model in
  [Native views (concept)](../concepts/native-views.md).
- Read the wire protocol in [Bridge](bridge.md).
- See how the reconciler drives handlers in [Reconciler](reconciler.md).
- Read the op vocabulary handlers apply in [Mutation ops](mutations.md).
- Read the callback registry handlers dispatch into in [Events](events.md).
- Read the values handlers size themselves against in
  [Platform metrics](platform_metrics.md).
