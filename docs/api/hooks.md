# Hooks

Hook primitives for `@component` functions: state, effects, memoization,
context, and refs. Hooks must be called at the top level of a component
(not inside conditionals or loops) so they can be matched to the same
slot across renders.

::: pythonnative.hooks
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Platform-metric hooks

These hooks subscribe to values published by
`pythonnative.platform_metrics` and re-render the component when they
change. The screen host is the only code that updates the underlying
values; user code consumes them.

- [`use_window_dimensions`][pythonnative.use_window_dimensions] — viewport size.
- [`use_safe_area_insets`][pythonnative.use_safe_area_insets] — top/bottom/left/right insets.
- [`use_keyboard_height`][pythonnative.use_keyboard_height] — software keyboard height.

For most apps the dedicated
[`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] component
is preferable to consuming `use_keyboard_height` directly.

## Next steps

- Compose hooks into a screen: [Components](components.md).
- Run side effects from
  [`use_effect`][pythonnative.use_effect] (after commit) and
  [`use_focus_effect`][pythonnative.use_focus_effect] (after focus).
- Share state across the tree with
  [`create_context`][pythonnative.create_context] and
  [`Provider`][pythonnative.Provider].
- Animate without re-rendering using [`use_ref`][pythonnative.use_ref]
  + `Animated`; see the [Animations guide](../guides/animations.md).
