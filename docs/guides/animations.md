# Animations

PythonNative ships an `Animated` API modelled on React Native's. It's
designed for the common case where a small set
of style properties (opacity, transform, color) need to interpolate
smoothly over time without re-rendering the component tree on every
frame.

## Mental model

1. Create an [`AnimatedValue`][pythonnative.AnimatedValue] with
   [`use_animated_value`][pythonnative.use_animated_value] (so it
   survives re-renders).
2. Bind the value into the `style` of an `Animated.View`,
   `Animated.Text`, or `Animated.Image`.
3. Drive the value with `Animated.timing`, `Animated.spring`, or
   `Animated.decay`. Each driver returns a handle with `.start()` /
   `.stop()`.

The animated component captures a `ref` to the underlying native view
(via the same [`use_ref`][pythonnative.use_ref] mechanism users have
access to). The animation driver then invokes the platform's native
animation API (`UIView.animate` on iOS, `ViewPropertyAnimator` on
Android) directly on that view, so per-frame updates skip the
reconciler.

## Fade in on mount

```python
import pythonnative as pn


@pn.component
def FadeInBox():
    opacity = pn.use_animated_value(0.0)

    def _fade_in():
        pn.Animated.timing(opacity, to=1.0, duration=400).start()

    pn.use_effect(_fade_in, [])

    return pn.Animated.View(
        pn.Text("Hello!"),
        style={
            "opacity": opacity,
            "background_color": "#0EA5E9",
            "padding": 16,
            "border_radius": 12,
        },
    )
```

`opacity` starts at `0.0` and the timing animation interpolates it to
`1.0` over 400 ms.

## Spring animation on press

```python
@pn.component
def Bouncy():
    scale = pn.use_animated_value(1.0)

    def _press():
        pn.Animated.spring(scale, to=1.2, stiffness=200, damping=8).start()

    return pn.Pressable(
        pn.Animated.View(
            pn.Text("Tap me"),
            style={"scale": scale, "padding": 12, "background_color": "#10B981"},
        ),
        on_press=_press,
    )
```

Available transform shortcuts inside `style`: `scale`, `scale_x`,
`scale_y`, `translate_x`, `translate_y`, `rotate`. Each accepts an
`AnimatedValue` and the runtime maps them to the underlying native
animation property.

## Sequencing and parallel composition

```python
opacity = pn.use_animated_value(0.0)
translate_y = pn.use_animated_value(20.0)

pn.Animated.parallel([
    pn.Animated.timing(opacity, to=1.0, duration=300),
    pn.Animated.spring(translate_y, to=0.0),
]).start()
```

Use `Animated.sequence` for one-after-another execution and
`Animated.delay(ms)` to insert pauses inside a sequence.

## Easing

`Animated.timing` accepts an `easing` argument: `"linear"`,
`"ease_in"`, `"ease_out"`, `"ease_in_out"`, or `"bounce"`.

## Stopping an animation

`start()` returns the handle you started with, and the handle exposes
`.stop()`. A common pattern is to keep the handle in a `use_ref` so
you can cancel a long-running animation when the user interrupts.

## When NOT to use `Animated`

- For simple state transitions where re-rendering the tree is fine,
  plain [`use_state`][pythonnative.use_state] is simpler.
- For physics simulations or per-frame layout (drag-and-drop, charts),
  consider running your own loop with
  [`use_effect`][pythonnative.use_effect] and a setter.
