# Mutations

Batched mutation protocol between the reconciler and native backends.
During the commit phase, the reconciler produces an ordered list of
mutation operations (`CreateOp`, `InsertOp`, `UpdateOp`, `SetFrameOp`,
`DestroyOp`) referencing integer tags. The entire transaction is applied
in a single batch via [`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations],
minimizing bridge crossings.

::: pythonnative.mutations
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Read how the virtual view tree is diffed in [Reconciler](reconciler.md).
- See how mutation operations map to platform widgets in [Native views](native_views.md).
- Read the high-level reconciliation model in [Reconciliation](../concepts/reconciliation.md).
