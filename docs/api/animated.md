# Animated

PythonNative's `Animated` API mirrors React Native's. Build performant
animations declaratively by binding [`AnimatedValue`][pythonnative.AnimatedValue]
instances to the `style` of an `Animated.View`, `Animated.Text`, or
`Animated.Image`. The reconciler holds a `ref` to the underlying
native view. Connected values, derived expressions, and style bindings
form a graph the renderer core evaluates on the UI thread, so animations
bypass Python reconciliation on each frame. Unattached values and values
with Python listeners have the core report each frame's value to Python,
and a callable easing function is sampled into a curve the core
interpolates.

A few types frame the surface:

- [`Easing`][pythonnative.animated.Easing] is a namespace of
  serializable [`EasingSpec`][pythonnative.animated.EasingSpec] curves
  (`Easing.ease_out`, `Easing.bezier(...)`) accepted by
  `Animated.timing(easing=...)`; a misspelled easing name raises
  `ValueError` instead of falling back.
- `await handle` and `handle.start(callback)` deliver an
  [`AnimationResult`][pythonnative.animated.AnimationResult] whose
  `finished` flag tells a stopped or superseded animation from one that
  ran to completion.
- [`ANIMATABLE_PROPS`][pythonnative.animated.ANIMATABLE_PROPS] lists
  the style keys an animated node may drive; binding a layout key such
  as `width` raises `ValueError` at element construction.
- `Animated.decay` uses React Native's model on every platform:
  velocity in points per millisecond decays as
  `v0 * deceleration ** t`, with `deceleration` defaulting to `0.998`.

::: pythonnative.animated
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]
      show_if_no_docstring: true

## See also

- The [Animations guide](../guides/animations.md) walks through
  fade-ins, springs, sequences, easing, decay, and gesture-driven
  animations.
- [`use_ref`][pythonnative.use_ref] explains the `ref` semantics that
  back `Animated.View`.
