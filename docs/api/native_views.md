# Native views

The boundary between PythonNative's element tree and concrete native
widgets. Each commit's diff is expressed as a flat list of
[mutation ops](mutations.md) referencing integer tags, applied through a
single `apply_mutations` call on the process-wide view backend returned
by [`get_backend`][pythonnative.native_views.get_backend]. On device
that backend is the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend],
which builds the wire transaction once, validates it once, serializes it
once, and hands it to the Swift and Kotlin component managers over the
[native bridge](bridge.md). The browser preview uses the same backend
with a WebSocket transport to the page. Headless tests install a
[`FakeBackend`][pythonnative.testing.FakeBackend] with
[`set_backend`][pythonnative.native_views.set_backend]; there is no
Python view-handler layer, and `get_backend` raises off device when no
backend was installed.

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
- See how the reconciler drives the backend in [Reconciler](reconciler.md).
- Read the op vocabulary managers apply in [Mutation ops](mutations.md).
- Read the callback registry managers dispatch into in [Events](events.md).
- Read the values managers size themselves against in
  [Platform metrics](platform_metrics.md).
- Declare your own element type with
  [`define_component`][pythonnative.sdk.define_component] in the [SDK](sdk.md).
