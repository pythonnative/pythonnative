# Native views

The bridge between PythonNative's element tree and concrete native
widgets. Each commit's diff is expressed as a flat list of mutation
ops referencing integer tags, applied through a single
[`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations]
call. Every element type maps to a
[`ViewHandler`][pythonnative.native_views.base.ViewHandler]
implementation in the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry];
the platform-specific handlers are registered lazily so importing
`pythonnative` on the desktop never pulls in Chaquopy or rubicon-objc.

::: pythonnative.native_views
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Mutation ops

::: pythonnative.mutations
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Event routing

::: pythonnative.events
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Base classes

::: pythonnative.native_views.base
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

!!! note "Platform handlers"
    The Android and iOS handler implementations live in
    `pythonnative.native_views.android` and
    `pythonnative.native_views.ios` respectively. They are imported
    only at runtime on the corresponding platform; we don't render
    their API tables here because they're internal to the runtime and
    require platform-only dependencies (Chaquopy / rubicon-objc) to
    be importable for `mkdocstrings` to introspect them.

## Next steps

- Read the high-level model in
  [Native views (concept)](../concepts/native-views.md).
- See how the reconciler drives handlers in [Reconciler](reconciler.md).
