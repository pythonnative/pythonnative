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

## Async hooks

For coroutines and data-driven UI, PythonNative ships dedicated
async-aware hooks layered on top of `use_state` / `use_effect`:

- [`use_effect`][pythonnative.use_effect] accepts `async def`
  callbacks directly; the coroutine runs as a task and is cancelled
  on re-run / unmount.
- [`use_resource`][pythonnative.use_resource]: starts a fetch during
  render and caches it; reading a pending
  [`Resource`][pythonnative.Resource] suspends the render (pair with
  [`Suspense`][pythonnative.Suspense]).
- [`use_transition`][pythonnative.use_transition] /
  [`use_deferred_value`][pythonnative.use_deferred_value]: mark
  expensive updates as low priority so urgent updates render first.
- [`use_query`][pythonnative.use_query]: subscribes to an async
  fetcher and re-renders on data / error / refetch.
- [`use_mutation`][pythonnative.use_mutation]: wraps an async
  mutator with loading / error state and a trigger.
- [`use_persisted_state`][pythonnative.use_persisted_state]:
  `use_state` backed by
  [`AsyncStorage`][pythonnative.AsyncStorage].

See the [Async + data guide](../guides/async.md) for a complete
walkthrough.

## Platform-metric hooks

These hooks subscribe to values published by
`pythonnative.platform_metrics` and re-render the component when they
change. The screen host is the only code that updates the underlying
values; user code consumes them.

- [`use_window_dimensions`][pythonnative.use_window_dimensions]: viewport size.
- [`use_safe_area_insets`][pythonnative.use_safe_area_insets]: top/bottom/left/right insets.
- [`use_keyboard_height`][pythonnative.use_keyboard_height]: software keyboard height.

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
