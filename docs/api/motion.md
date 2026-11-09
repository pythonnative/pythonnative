# Motion

Worklets, shared values, animations, layout animations, and
shared-element transitions (RFC 0009). Interaction logic runs on the
UI thread inside the renderer core as **worklets**, Python functions in
a subset the core compiles, verifies, and interprets, so motion keeps
up with the finger while the Python thread is busy. The
[Motion guide](../guides/motion.md) explains the model and walks
through every piece.

The everyday names are exported from `pythonnative` itself:
[`worklet`][pythonnative.worklet],
[`SharedValue`][pythonnative.SharedValue],
[`AnimatedStyle`][pythonnative.AnimatedStyle],
[`FrameInfo`][pythonnative.FrameInfo], the hooks, the `with_*`
animations, [`Easing`](#easing), [`Spring`][pythonnative.Spring], and
the helpers. The layout animation presets,
[`Keyframes`][pythonnative.motion.Keyframes],
[`SharedTransition`][pythonnative.motion.SharedTransition],
[`LayoutAnimationConfig`][pythonnative.motion.LayoutAnimationConfig],
and [`WorkletError`][pythonnative.motion.WorkletError] live in
`pythonnative.motion`:

```python
import pythonnative as pn
from pythonnative.motion import FadeIn, FadeOut, LinearTransition, SharedTransition
```

The components built on Motion,
[`BottomSheet`][pythonnative.BottomSheet] and
[`Swipeable`][pythonnative.Swipeable], are documented with the other
[components](components.md#components-built-on-motion).

[](){ #pythonnative.motion }

## Worklets

::: pythonnative.motion.worklets.worklet
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.worklets.is_worklet
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.compiler.WorkletError
    options:
      heading_level: 3
      show_root_full_path: false

## Shared values

::: pythonnative.motion.shared.SharedValue
    options:
      heading_level: 3
      show_root_full_path: false

## Hooks

::: pythonnative.motion.hooks
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - use_shared_value
        - use_derived_value
        - use_animated_style
        - use_animated_reaction
        - use_frame_callback
        - FrameInfo

[`AnimatedStyle`][pythonnative.AnimatedStyle], what
`use_animated_style` returns, is documented with the other
[style types](style.md).

## Animations

::: pythonnative.motion.animations
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - with_timing
        - with_spring
        - with_decay
        - with_delay
        - with_sequence
        - with_repeat
        - Spring
        - Animation
        - ReduceMotion

### Easing

[](){ #pythonnative.motion.animations.Easing }
[](){ #pythonnative.motion.Easing }
[](){ #pythonnative.Easing }

`Easing` holds the curves `with_timing` and the layout animation
presets accept. Each is an [`EasingSpec`][pythonnative.motion.EasingSpec],
which crosses to the core as data and evaluates the same way in Python.
A curve's name as a string (`"ease_out"`) works wherever a curve does.

| Curve | Shape |
| --- | --- |
| `Easing.linear` | `t` |
| `Easing.ease`, `Easing.ease_in` | `bezier(0.42, 0, 1, 1)` |
| `Easing.ease_out` | `bezier(0, 0, 0.58, 1)` |
| `Easing.ease_in_out` | `bezier(0.42, 0, 0.58, 1)`, the default |
| `Easing.quad` | `t * t` |
| `Easing.cubic` | `t * t * t` |
| `Easing.bounce` | Penner's bounce-out |
| `Easing.bezier(x1, y1, x2, y2)` | A CSS cubic Bézier; `y` values may overshoot |
| `Easing.custom(fn)` | A `progress -> eased` Python function, sampled at 64 points the core interpolates |

```python
offset.value = pn.with_timing(1, easing=pn.Easing.bezier(0.2, 0.8, 0.2, 1.0))
```

::: pythonnative.motion.animations.EasingSpec
    options:
      heading_level: 4
      show_root_full_path: false

## Helpers

These are plain functions in Python and intrinsics in the core, so a
worklet computes the same result in both places.

::: pythonnative.motion.animations.interpolate
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.animations.interpolate_color
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.animations.clamp
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.animations.snap_point
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.animations.run_on_python
    options:
      heading_level: 3
      show_root_full_path: false

::: pythonnative.motion.animations.Extrapolate
    options:
      heading_level: 3
      show_root_full_path: false

## Layout animations

::: pythonnative.motion.layout
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false

## Shared-element transitions

::: pythonnative.motion.transitions
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false

## Release precompilation

[](){ #pythonnative.motion.worklets }

Release builds ship without source, so `pn build` compiles every worklet
while staging. These modules are for tooling and contributors; apps
don't call them.

::: pythonnative.motion.precompile
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false

### The compiler

::: pythonnative.motion.compiler
    options:
      heading_level: 4
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - compile_function
        - compile_node

::: pythonnative.motion.program.Program
    options:
      heading_level: 4
      show_root_full_path: false

## See also

- The [Motion guide](../guides/motion.md) covers the threading model,
  the worklet language, animatable properties, testing, and migrating
  from `Animated`.
- [Gestures](gestures.md) lists the recognizers whose callbacks take
  worklets.
- The [collapsing header example](../examples/collapsing-header.md)
  drives a header from an `on_scroll` worklet.
