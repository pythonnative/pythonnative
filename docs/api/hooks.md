# Hooks

Hook primitives for `@component` functions: state, effects, memoization,
context, and refs. Hooks must be called at the top level of a component
(not inside conditionals or loops) so they can be matched to the same
slot across renders.

The hooks are typed for editors: dependency lists are any
[`Deps`][pythonnative.Deps] sequence (a list or a tuple),
[`use_reducer`][pythonnative.use_reducer] is generic over the state and
action types so `dispatch` only accepts the actions the reducer handles,
`use_ref(0)` is a `Ref[int]` while `use_ref()` is a `Ref[Any]`, and
[`Context.Provider`][pythonnative.hooks.Context.Provider] takes its
children positionally with a keyword-only `value=`, like every other
container.

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

## Refs and handles

[`use_ref`][pythonnative.use_ref] returns a [`Ref`][pythonnative.Ref].
Passed as `ref=` to a built-in element, it receives a typed imperative
handle after commit ([`TextInputHandle`][pythonnative.TextInputHandle],
[`ScrollViewHandle`][pythonnative.ScrollViewHandle],
[`WebViewHandle`][pythonnative.WebViewHandle], or a plain
[`ViewHandle`][pythonnative.ViewHandle] with `tag` and `frame`); see
[Handles](handles.md). Composite components publish their own
controller with
[`use_imperative_handle`][pythonnative.use_imperative_handle].

## Platform-metric hooks

These hooks subscribe to values published by
`pythonnative.platform_metrics` and re-render the component when they
change. The screen host is the only code that updates the underlying
values; user code consumes them.

- [`use_window_dimensions`][pythonnative.use_window_dimensions]: viewport size,
  including `scale` and `font_scale`.
- [`use_safe_area_insets`][pythonnative.use_safe_area_insets]: top/bottom/left/right insets.
- [`use_keyboard_height`][pythonnative.use_keyboard_height]: software keyboard height,
  fed by the [`Keyboard`][pythonnative.Keyboard] module on both platforms.
- [`use_color_scheme`][pythonnative.use_color_scheme]: the effective
  [`ColorScheme`][pythonnative.hooks.ColorScheme].

For most apps the dedicated
[`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] component
is preferable to consuming `use_keyboard_height` directly. Device
modules ship their own reactive hooks:
[`use_screen_reader_enabled`][pythonnative.use_screen_reader_enabled],
[`use_reduce_motion`][pythonnative.use_reduce_motion],
[`use_locales`][pythonnative.use_locales],
[`use_app_state`][pythonnative.use_app_state], and
[`use_net_info`][pythonnative.use_net_info]; see
[Native modules](native_modules.md).

## Batching and transitions

State setters never render inline. Every setter call made during one
callback, effect, or task step is coalesced into a single flush
scheduled on the application loop, on every host including headless
tests (automatic batching). A flush that keeps re-scheduling itself
more than fifty times raises `RuntimeError("Too many re-renders")`
from the offending component and routes it through the nearest
[`ErrorBoundary`][pythonnative.ErrorBoundary] (or the RedBox in dev
mode). [`batch_updates`][pythonnative.scheduler.batch_updates] remains
the explicit way to coalesce setter calls that span an `await`, and
each reconciler owns a
[`TransitionQueue`][pythonnative.scheduler.TransitionQueue] that
defers renders started inside
[`use_transition`][pythonnative.use_transition].

::: pythonnative.scheduler
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Compose hooks into a screen: [Components](components.md).
- Run side effects from
  [`use_effect`][pythonnative.use_effect] (after commit) and
  [`use_focus_effect`][pythonnative.use_focus_effect] (after focus).
- Share state across the tree with
  [`create_context`][pythonnative.create_context] and
  [`Context.Provider`][pythonnative.hooks.Context.Provider].
- Animate without re-rendering using [`use_ref`][pythonnative.use_ref]
  + `Animated`; see the [Animations guide](../guides/animations.md).
