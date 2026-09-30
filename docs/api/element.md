# Element

Immutable descriptor for a single node in PythonNative's virtual view
tree. `Element` instances are produced by the
[component factories](components.md) and consumed by the
[`Reconciler`][pythonnative.reconciler.Reconciler].

You almost never construct an `Element` by hand; the factory functions
exist precisely so app code stays in plain Python.

[`Node`][pythonnative.element.Node] is the type of anything that can
appear in a tree: an element, `None` or a `bool` for "nothing", or a
(possibly nested) iterable of nodes. Built-in containers take
`*children: pn.Node`, and components return `pn.Node`.
[`Element.with_key`][pythonnative.element.Element.with_key] returns a keyed
copy, the typed way to key a user component.

::: pythonnative.element
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See how trees of elements get mounted in
  [Reconciliation](../concepts/reconciliation.md).
- Browse the built-in element types in [Components](components.md).
