# Component

The [`@component`][pythonnative.component.component] decorator turns a plain
function into a [`Component`][pythonnative.Component]: calling it
returns an [`Element`][pythonnative.Element] instead of running the
body, and the reconciler runs the body (with hooks) when the element
mounts or its props change. The component's signature is its prop
list, so type checkers verify every call. Positional `*children`
receive child nodes; keyword arguments are props. Key a component's
element with [`Element.with_key`][pythonnative.element.Element.with_key]
(`Row(item).with_key(item.id)`), since `key=` isn't a prop.
[`memo`][pythonnative.memo] skips re-rendering when props are
unchanged. In development builds, props are also checked against the
function's annotations; see
[`prop_checks`](#development-prop-checks).

::: pythonnative.component
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Development prop checks

::: pythonnative.prop_checks
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: false

## Next steps

- Learn the model in [Components](../concepts/components.md).
- Add state and effects with [Hooks](hooks.md).
