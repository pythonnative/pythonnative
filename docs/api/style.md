# Style

PythonNative styles are plain Python dicts typed by the
[`Style`][pythonnative.Style] `TypedDict`. An element's `style` prop
may be a single dict, a list of dicts (later entries win on key
collision, and `None` entries are skipped), or `None`.
[`StyleSheet`][pythonnative.StyleSheet] is a namespace base class for
named styles with typed attribute access, and
[`ABSOLUTE_FILL`][pythonnative.style.ABSOLUTE_FILL] is the common
full-parent overlay. Theme tokens and theme-dependent styles live in
[Theme](theme.md).

::: pythonnative.style
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See worked examples in [Styling](../guides/styling.md).
- Use design tokens and dark mode with [Theme](theme.md).
- See the full per-component property catalogue in
  [Component properties](component-properties.md).
