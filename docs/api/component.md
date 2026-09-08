# Component

The [`@component`][pythonnative.component.component] decorator turns a plain
function into a [`Component`][pythonnative.Component]: calling it
returns an [`Element`][pythonnative.Element] instead of running the
body, and the reconciler runs the body (with hooks) when the element
mounts or its props change. Positional arguments are children; keyword
arguments are props. [`memo`][pythonnative.memo] skips re-rendering
when props are unchanged.

::: pythonnative.component
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Learn the model in [Components](../concepts/components.md).
- Add state and effects with [Hooks](hooks.md).
