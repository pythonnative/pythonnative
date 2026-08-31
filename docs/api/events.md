# Events

Tag-based event routing between native views and Python callbacks.
The reconciler strips callable props from view payloads and registers
them in a Python-side registry keyed by `(tag, name)`. Native listeners
dispatch through [`dispatch_event`][pythonnative.events.dispatch_event],
meaning re-renders that only update closure identities don't trigger native
calls across the bridge.

::: pythonnative.events
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See how native views are updated and wired in [Native views](native_views.md).
- Read about mutation ops in [Mutations](mutations.md).
- Learn about touch and gesture handling in [Gestures](gestures.md).
