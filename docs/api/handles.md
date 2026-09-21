# Handles

Typed imperative handles published on `ref.current` when a
[`Ref`][pythonnative.Ref] from [`use_ref`][pythonnative.use_ref] is
passed to a built-in element. The reconciler picks the handle class by
element type after commit and clears `ref.current` back to `None` on
unmount. Methods that act on the view are plain calls; methods that need
an answer from the native view are `async`. Composite components
(`FlatList`, `SectionList`) publish a
[`ListController`][pythonnative.ListController] instead, through
[`use_imperative_handle`][pythonnative.use_imperative_handle].

```python
import pythonnative as pn


@pn.component
def Search():
    field = pn.use_ref()

    def focus_field():
        if field.current is not None:
            field.current.focus()

    pn.use_effect(focus_field, [])
    return pn.TextInput(placeholder="Search", ref=field)
```

::: pythonnative.handles
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Read the usage patterns in
  [Refs and handles](../concepts/hooks.md#refs-and-handles).
- Scroll a list imperatively with
  [`ListController`][pythonnative.ListController]; see the
  [Lists guide](../guides/lists.md#imperative-scrolling).
- Call a custom component's own commands through
  [`ViewHandle.command`][pythonnative.handles.ViewHandle.command]; see
  [Custom native components](../guides/custom-native-components.md#commands).
