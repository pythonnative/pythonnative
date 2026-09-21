# Events

Event callbacks live in a process-wide registry keyed by a view's
integer tag and the event name. The
[`Reconciler`][pythonnative.reconciler.Reconciler] writes to it during a
commit; platform handlers read from it when a native widget fires.

::: pythonnative.events
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- The dataclasses those callbacks receive (`LayoutEvent`,
  `ScrollEvent`, `KeyPressEvent`, ...) are documented under
  [Typed event payloads](components.md#typed-event-payloads).
- See what carries the remaining, non-callable props in
  [Mutation ops](mutations.md).
- See how component managers wire a platform listener once, at
  creation, in [Native views](native_views.md).
- Read the other Python-side store the native layer reads on demand in
  [Platform metrics](platform_metrics.md).
- Follow a full commit end to end in
  [Reconciliation](../concepts/reconciliation.md).
