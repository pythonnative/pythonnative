# Animations

PythonNative ships an `Animated` API modelled on React Native's. It's
designed for the common case where a small set of style properties
(opacity, transform, color) need to interpolate smoothly over time
without re-rendering the component tree on every frame.

## Mental model

1. Create an [`AnimatedValue`][pythonnative.AnimatedValue] with
   [`use_animated_value`][pythonnative.use_animated_value] (so it
   survives re-renders).
2. Bind the value into the `style` of an `Animated.View`,
   `Animated.Text`, or `Animated.Image`.
3. Drive the value with `Animated.timing`, `Animated.spring`, or
   `Animated.decay`. Each driver returns a handle with two faces:
   - `handle.start(callback=None)` is fire-and-forget (returns `self`);
     the optional callback receives an
     [`AnimationResult`][pythonnative.AnimationResult].
   - `await handle` runs the animation, suspends until it settles, and
     returns the same `AnimationResult`. Cancelling the awaiting task
     stops the animation.

   `AnimationResult.finished` is `True` when the animation ran to
   completion and `False` when it was stopped, superseded by another
   animation on the same value, or interrupted by the platform.
   Composites (`sequence`, `parallel`, `stagger`, `loop`) are finished
   only if every child finished.

The animated component attaches the value to its native view's
animation bindings after mount. From there, the **native driver**
takes over whenever it can.

## The native driver

When an animated node is bound to mounted views, PythonNative serializes
its connected values, arithmetic, interpolation, and style bindings into
an animation graph. Starting or awaiting a timing, spring, or decay driver
sends its specification to the renderer.

On mobile, Swift and Kotlin evaluate the graph and apply its bindings on
the UI thread. Derived values, color interpolation, and native scroll and
gesture inputs can update without Python work on every frame. The browser
implements graph evaluation in JavaScript. Completion is delivered back to
Python to settle the value and resolve an awaiting task.

The Python-ticked fallback (a ~60 Hz loop) is used automatically
when:

- the value isn't attached to any mounted view (pure data animation),
- a Python listener is registered via `add_listener` (listeners want
  per-frame values, and only the ticker provides those),
- a callable `easing` is supplied (custom curves can't cross the
  bridge), or
- the platform declines the animation.

Either way the API and the observable end state are identical, so you
never have to opt in or out manually.

## Fade in on mount

```python
import pythonnative as pn


@pn.component
def FadeInBox():
    opacity = pn.use_animated_value(0.0)

    async def _fade_in():
        await pn.Animated.timing(opacity, to=1.0, duration=400)

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
`1.0` over 400 ms. Passing an `async def` to `use_effect` means the
in-flight animation is automatically cancelled if the component
unmounts before the 400 ms is up.

If you don't need to react to completion, the synchronous form is fine
too:

```python
def _press():
    pn.Animated.timing(opacity, to=1.0, duration=400).start()
```

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
`scale_y`, `translate_x`, `translate_y`, `rotate`, `rotate_x`, and
`rotate_y`. Each accepts an `AnimatedValue` and the runtime maps them
to the underlying native animation property; iOS keeps each animated
channel separately and composes them with the static `transform` prop,
so binding `translate_x` and `translate_y` together works.

The full set of style keys an animated node may drive is
[`ANIMATABLE_PROPS`][pythonnative.ANIMATABLE_PROPS]: `opacity`,
`background_color`, `color`, and the eight transform channels above.
These are the properties every renderer can animate on its UI thread
without a layout pass. Binding a node to any other key (`width`,
`margin`, `padding`, `top`, `skew_x`, ...) raises `ValueError` naming
the animatable set when the element is constructed, so an animation
never silently degrades to a re-render per frame.

## Sequencing and parallel composition

```python
async def _intro():
    opacity = pn.use_animated_value(0.0)
    translate_y = pn.use_animated_value(20.0)

    await pn.Animated.parallel([
        pn.Animated.timing(opacity, to=1.0, duration=300),
        pn.Animated.spring(translate_y, to=0.0),
    ])
    await pn.Animated.delay(80)
    await pn.Animated.timing(opacity, to=0.5, duration=200)
```

`Animated.parallel` returns when **all** animations finish.
`Animated.sequence` runs animations one-after-another. Both are also
awaitable.

`Animated.stagger` is `parallel` with an offset: each animation starts
`delay` milliseconds after the previous one, which is the classic
"cards cascade in" effect:

```python
await pn.Animated.stagger(120, [
    pn.Animated.timing(card_a, to=1.0, duration=200),
    pn.Animated.timing(card_b, to=1.0, duration=200),
    pn.Animated.timing(card_c, to=1.0, duration=200),
])
```

`Animated.loop` repeats any animation (including a `sequence` or
`parallel`). By default it loops forever until you `.stop()` it; pass
`iterations` for a fixed count:

```python
pulse = pn.Animated.loop(
    pn.Animated.sequence([
        pn.Animated.timing(scale, to=1.15, duration=300),
        pn.Animated.timing(scale, to=1.0, duration=300),
    ]),
).start()
# Later, e.g. when loading finishes:
pulse.stop()
```

## Interpolation

Every animated node has an `interpolate` method that maps an input
range onto an output range. Drive one value and derive as many styled
properties from it as you like; the derived nodes update whenever the
driver moves:

```python
progress = pn.use_animated_value(0.0)

shift = progress.interpolate([0, 1], [0, 120])
color = progress.interpolate([0, 1], ["#6366F1", "#10B981"])
angle = progress.interpolate([0, 1], ["0deg", "90deg"])

pn.Animated.View(
    style={
        "background_color": color,
        "transform": [{"translate_x": shift}, {"rotate": angle}],
    },
)
```

Input ranges can have any number of monotonically increasing
breakpoints, and output ranges accept numbers, color strings, or
angle strings (`"deg"` or `"rad"`). The `extrapolate` argument
controls what happens outside the input range: `"extend"` (default)
continues the edge segment linearly, `"clamp"` pins to the edge
output, and `"identity"` passes the input through unchanged.
`extrapolate_left` and `extrapolate_right` set the two sides
independently. Interpolations chain: `node.interpolate(...)` returns
another node you can interpolate again.

## Derived values with operators

Animated nodes support Python arithmetic, so simple math doesn't need
an interpolation:

```python
opacity = progress * 0.5 + 0.5      # 0.5 .. 1.0
inverse = 1.0 - progress
centered = (progress - 0.5) * 2.0
```

`+`, `-`, `*`, `/`, `%`, and unary `-` all work, between nodes and
plain numbers or between two nodes. The result is a read-only node:
bind it into styles like any `AnimatedValue`, but drive the underlying
source value.

Derived nodes are part of the serialized animation graph. Arithmetic and
interpolation can therefore run in the renderer alongside their source
driver. A backend without graph support uses the Python ticker for
derived bindings.

## Scroll-driven animation with `Animated.event`

`Animated.event` builds an event handler that writes fields from the
event payload straight into `AnimatedValue`s. The classic use is
binding a scroll offset:

```python
scroll_y = pn.use_animated_value(0.0)

pn.ScrollView(
    content,
    on_scroll=pn.Animated.event(y=scroll_y),
)
```

Each keyword names a payload field (`x` and `y` for scroll events) and
the value it feeds. Pass a positional callable as the first argument
if you also want a plain Python listener to run per event.

`Animated.diff_clamp` pairs naturally with scroll offsets: it tracks
the *change* in its input and clamps the running total, which is
exactly the collapsing-header behavior (hide after N points of
downward travel, reappear on any upward travel):

```python
clamped = pn.Animated.diff_clamp(scroll_y, 0, HEADER_HEIGHT)
header_shift = clamped.interpolate([0, HEADER_HEIGHT], [0, -HEADER_HEIGHT])

pn.Animated.View(
    header_content,
    style={
        "position": "absolute",
        "top": 0, "left": 0, "right": 0,
        "height": HEADER_HEIGHT,
        "z_index": 2,
        "transform": [{"translate_y": header_shift}],
    },
)
```

The e2e-suite app ships this exact pattern as the "Collapsing header"
demo under Animations.

## Easing

`Animated.timing(easing=...)` takes a curve from the
[`Easing`][pythonnative.Easing] namespace, which mirrors React
Native's: `Easing.linear`, `Easing.ease`, `Easing.ease_in`,
`Easing.ease_out`, `Easing.ease_in_out` (the default), `Easing.quad`,
`Easing.cubic`, `Easing.bounce`, and `Easing.bezier(x1, y1, x2, y2)`
for a CSS-style cubic bezier:

```python
pn.Animated.timing(opacity, to=1.0, easing=pn.Easing.ease_out)
pn.Animated.timing(x, to=200, easing=pn.Easing.bezier(0.2, 0.8, 0.2, 1.0))
pn.Animated.timing(y, to=0, easing="bounce")   # the names also work as strings
```

Each curve is a serializable [`EasingSpec`][pythonnative.EasingSpec],
so it crosses the bridge as data and the native drivers run it on the
UI thread; bezier control points travel as numbers, not as a string.
A misspelled easing name raises `ValueError` instead of falling back
silently. `Easing.ease` follows React Native (the same curve as
`ease_in`), not CSS `ease`. A plain callable `progress -> eased` is
still accepted for custom curves, at the cost of ticking in Python.

## Decay (fling)

`Animated.decay` decelerates a value from an initial velocity, the
standard ending for a pan gesture. It uses React Native's model on
every platform: with `t` in milliseconds, the velocity decays as
`v0 * deceleration ** t`, and the value comes to rest at
`start + v0 / (1 - deceleration)`. `velocity` is in points per
millisecond; gesture events report points per second, so divide by
1000. `deceleration` defaults to `0.998`; `0.99` stops quickly, and a
value outside `(0, 1)` raises `ValueError`:

```python
def on_pan_end(event):
    pn.Animated.decay(tx, velocity=event.velocity_x / 1000.0).start()

pn.Animated.decay(offset, velocity=2.0, deceleration=0.99).start()
```

See the [Gestures guide](gestures.md) for the full drag-and-release
pattern.

## Stopping an animation

`start()` returns the handle you started with, and the handle exposes
`.stop()`. A common pattern is to keep the handle in a `use_ref` so
you can cancel a long-running animation when the user interrupts. A
stopped animation resolves with `AnimationResult(finished=False)`;
a `sequence` whose step is stopped stops too, with `finished=False`.
If you're awaiting the animation instead, cancelling the awaiting task
stops the animation:

```python
async def _enter():
    await pn.Animated.timing(opacity, to=1.0, duration=2000)

task = pn.run_async(_enter())
# Sometime later:
task.cancel()  # animation snaps to wherever it was; opacity stops here.
```

## When NOT to use `Animated`

- For simple state transitions where re-rendering the tree is fine,
  plain [`use_state`][pythonnative.use_state] is simpler.
- For physics simulations or per-frame layout (drag-and-drop, charts),
  consider running your own loop with
  [`use_effect`][pythonnative.use_effect] and a setter.
