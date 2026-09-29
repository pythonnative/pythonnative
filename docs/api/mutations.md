# Mutation ops

Five record types describe every change to the native view tree:
create, update, insert, destroy, and set frame. The
[`Reconciler`][pythonnative.reconciler.Reconciler] emits them; the
view backend from [`get_backend`][pythonnative.native_views.get_backend]
applies them in one `apply_mutations` call per commit.

::: pythonnative.mutations
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See where the callables stripped from these payloads go in
  [Events](events.md).
- See how each op is applied to a concrete widget in
  [Native views](native_views.md).
- Read what component managers size themselves against in
  [Platform metrics](platform_metrics.md).
- Read the diffing pass that produces these lists in
  [Reconciliation](../concepts/reconciliation.md).
