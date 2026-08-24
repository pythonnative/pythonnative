# Suspense

Primitives behind PythonNative's async rendering model: the
[`Suspend`][pythonnative.suspense.Suspend] signal, the
[`CoroDriver`][pythonnative.suspense.CoroDriver] that steps `async def`
component bodies synchronously, cached async values
([`Resource`][pythonnative.Resource] /
[`start_resource`][pythonnative.start_resource]), and code splitting
with [`lazy`][pythonnative.lazy].

The user-facing pieces are the [`Suspense`][pythonnative.Suspense]
boundary component (documented with the other
[components](components.md)) and the
[`use_resource`][pythonnative.use_resource] hook (documented with the
other [hooks](hooks.md)); this page covers the underlying machinery.

::: pythonnative.suspense
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Walk through async components, `Suspense`, and `use_resource`
  end-to-end: [Async + data guide](../guides/async.md).
- See how suspension threads through the render pass:
  [Architecture](../concepts/architecture.md).
