# Testing

`pythonnative.testing` renders components without a device or
simulator. [`render`][pythonnative.testing.render] mounts an element
into an in-memory [`FakeBackend`][pythonnative.testing.FakeBackend]
and returns a [`RenderResult`][pythonnative.testing.RenderResult] with
Testing Library-style queries and event helpers;
[`render_hook`][pythonnative.testing.render_hook] does the same for a
bare hook.

::: pythonnative.testing
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Read the [Testing guide](../guides/testing.md) for patterns.
- Test navigation flows against a
  [`FakeHost`][pythonnative.testing.FakeHost].
