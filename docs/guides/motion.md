# Motion

Motion is how PythonNative animates. Interaction logic that has to keep
up with a finger runs on the platform's UI thread, inside the renderer
core, as a **worklet**: an ordinary, type-checked Python function written
in a subset the core compiles, verifies, and interprets. Python never
sees the per-frame work, so a sheet follows the finger and settles on a
detent while the Python thread is busy rendering, decoding JSON, or
importing a module.

```python
import pythonnative as pn
from pythonnative import gestures

CARD = {"padding": 24, "border_radius": 12, "background_color": "#D1FAE5"}


@pn.component
def DraggableCard() -> pn.Node:
    x = pn.use_shared_value(0.0)
    y = pn.use_shared_value(0.0)

    @pn.worklet
    def drag(event: gestures.GestureEvent) -> None:
        x.value = event.translation_x
        y.value = event.translation_y

    @pn.worklet
    def release(event: gestures.GestureEvent) -> None:
        x.value = pn.with_spring(0, velocity=event.velocity_x)
        y.value = pn.with_spring(0, velocity=event.velocity_y)

    moved = pn.use_animated_style(
        lambda: {"transform": [{"translate_x": x.value}, {"translate_y": y.value}]}
    )
    return pn.View(
        pn.Text("Drag me"),
        style=[CARD, moved],
        gestures=[gestures.Pan(on_change=drag, on_end=release)],
    )
```

`drag`, `release`, and the lambda never run on the Python thread. The
core runs `drag` each time the pan reports a change, which writes `x`
and `y`. The animated style read them, so the core runs it again, and
the platform applies the new transform before the frame is drawn. On
release, assigning `with_spring(...)` starts a spring that the core
advances every display frame.

Motion is PythonNative's counterpart of React Native's Reanimated and
Gesture Handler. It replaced the `Animated` API; if you're upgrading,
see [Migrating from `Animated`](#migrating-from-animated). The design is
recorded in RFC 0009 (`rfcs/0009-motion.md` in the repository).

## The mental model

Two threads take part in every animation:

| Thread | Runs |
| --- | --- |
| Python application thread | Components and hooks; compiling and installing worklets; reading and writing shared values; awaiting animations; `run_on_python` callbacks |
| Platform UI thread, inside the core | Event and gesture worklets, animation drivers, derived values, reactions, frame callbacks, animated styles, and layout animations |

Python describes the motion: which shared values exist, which worklets
read and write them, and which styles they drive. It sends that
description to the core behind the commit that renders it, the same
way it sends view commands. From then on the core does the work. The
UI thread never waits on Python, and it never takes the core's commit
lock (see [The native bridge](../concepts/bridge.md#threads-and-the-deadlock-rule)).

On every display frame, the core runs, in order:

1. animation drivers (`with_timing`, `with_spring`, and the rest),
2. derived values,
3. reactions,
4. frame callbacks, and then
5. animated styles.

A shared value that changes partway through a frame is seen by
everything after it in the same frame, and each binding runs at most
once per frame. Events and gestures run their worklets as soon as the
platform reports them, and the bindings that depend on what they wrote
run before the next frame is drawn.

The core is the same C++ library on iOS, Android, the browser preview,
and the host build that pytest loads, so a worklet computes the same
result, frame for frame, everywhere it runs.

## Worklets

A worklet is a function the core can run on the UI thread. There are
two ways to write one:

- A function decorated with [`@pn.worklet`][pythonnative.worklet], at
  module level or inside a component.
- An inline `lambda` passed directly to an API that only accepts
  worklets: [`use_animated_style`][pythonnative.use_animated_style],
  [`use_derived_value`][pythonnative.use_derived_value],
  [`use_animated_reaction`][pythonnative.use_animated_reaction],
  [`use_frame_callback`][pythonnative.use_frame_callback], an
  animation's `on_finish=`, and a custom layout animation passed to
  `entering=`, `exiting=`, or `layout=`.

Event props and gesture callbacks accept either kind of callback. They
run a decorated worklet on the UI thread and anything else, including a
plain `lambda`, on the Python thread. The decorator is the visible
marker for code that leaves Python's thread, so an existing handler
never moves threads silently.

A worklet is still a Python function. Calling it from Python runs it as
Python, so you can unit test its logic directly, and your type checker
sees ordinary annotations:

```python
@pn.worklet
def rubber_band(offset: float, limit: float) -> float:
    if offset <= limit:
        return offset
    return limit + (offset - limit) * 0.35


assert rubber_band(150, 100) == 117.5
```

A worklet compiles the first time it's installed, not when its module is
imported. Programs are cached by code object, so a worklet defined
inside a component compiles once, however many times the component
renders, and each render only sends the captured values that changed.

### The language

Worklets are written in a subset of Python small enough for the core to
verify, bound, and interpret without an interpreter:

| Construct | Supported |
| --- | --- |
| Parameters | Positional parameters without defaults. Annotations are for your type checker; the core reads event fields by name |
| Literals | `int`, `float`, `bool`, `None`, `str`, tuples, lists, and dicts with string keys |
| Names | Parameters, locals, captured closure variables, module globals, and builtins |
| Operators | `+ - * / // % **`; unary `-`, `+`, and `not`; comparisons, including chains, `in`, and `is`; `and`, `or`, and conditional expressions |
| Statements | Assignment, augmented assignment, tuple unpacking, `if`/`elif`/`else`, `for` over `range(...)` or a sequence, `break`, `continue`, `return`, `pass`, and expression statements |
| Comprehensions | List and tuple comprehensions with one `for` clause over `range(...)` or a sequence, with `if` filters |
| Calls | Other worklets; `abs`, `min`, `max`, `round`, `int`, `float`, `bool`, and `len`; `math` functions and constants; the motion helpers below; `run_on_python` |
| Attributes | `.value` on shared values (read and write), `.cancel()` on a shared value, and fields of event parameters (read) |
| Subscripts | Indexing tuples, lists, strings, and dicts (read) |

Semantics follow Python wherever the subset reaches. `//` and `%` floor
toward negative infinity, `round` rounds half to even, `/` is true
division, dividing by zero raises `ZeroDivisionError`, `and` and `or`
return an operand, truthiness follows Python's rules, and comparing a
number with a string raises `TypeError`. Numbers are IEEE doubles that
carry an integer flag, so `7 // 2` is `3`.

Everything else is a compile error that names the construct and
suggests an alternative: `while`, `try`, `with`, `import`, `match`,
nested `def` or `class`, a `lambda` inside a worklet, `global`,
`nonlocal`, `raise`, `assert`, `yield`, `await`, f-strings, sets,
slices, `:=`, star arguments, `del`, item assignment, method calls, and
attribute writes other than `.value`.

### Captures

A worklet's free variables and globals are resolved when it's
installed, after the component renders:

- **Shared values** become references to the core's value. Reads and
  writes go to the UI thread's copy.
- **Other worklets** are linked into the program, so a worklet can call
  a helper worklet.
- **Supported builtins and helpers** (`min`, `math.sqrt`,
  `pn.with_spring`, `pn.interpolate`) become intrinsics the core
  implements natively.
- **`None`, numbers, strings, and tuples, lists, and dicts of them**
  become constants, as do [`Easing`](#easing) curves and
  [`Spring`][pythonnative.Spring] parameters.
- **Attribute and subscript chains on any other object** are evaluated
  once, at install, and become constants. `theme.colors.primary` or
  `SNAP_POINTS[2]` reads the value that was current when the component
  rendered.

Anything else, such as a plain Python function or an arbitrary object,
can't cross to the UI thread. Captured values are re-read on every
render, so a worklet defined in a component always sees that render's
props and state.

### Errors

A construct outside the subset raises
[`WorkletError`][pythonnative.motion.WorkletError] with the file,
line, and column when the worklet is installed. Installing happens in
the render or commit that uses the worklet, so the error reaches the
nearest [error boundary](error-boundaries.md) like any render error:

```python
@pn.worklet
def settle(event: gestures.GestureEvent) -> None:
    while offset.value > 0:
        offset.value -= 1


@pn.worklet
def label(event: gestures.GestureEvent) -> str:
    return event.state.upper()
```

```text
WorkletError: app/screen.py:9:5: `while` loops can't run on the UI thread; use `for i in range(n)`
WorkletError: app/screen.py:15:12: method calls like `.upper()` aren't supported in worklets
```

[`pn lint`](linting.md#pn201-worklets-must-compile) reports the same
compile errors statically, as `PN201`, so you see them before you run
the app.

A few errors can only be found at install, when the worklet's captures
are resolved:

```python
def log(y: float) -> None:
    print(y)


@pn.worklet
def track(event: pn.ScrollEvent) -> None:
    log(event.y)
```

```text
WorkletError: worklet track can't call log on the UI thread; mark it @pn.worklet, or call it with run_on_python()
```

Mark the helper `@pn.worklet` if it only computes values, or call it
with [`run_on_python`](#calling-python-from-a-worklet) if it needs
Python.

A worklet that fails while it runs on the UI thread (`ZeroDivisionError`,
`TypeError`, a style key it can't animate) disables that one binding;
the rest of the app keeps animating. The failure reaches Python as a
`WorkletError` whose `error_type` names the Python exception it raised.
It goes to [`pn.set_error_handler`][pythonnative.set_error_handler] with
the phase `"worklet"`, and without a handler it's logged once. Every run
also has a budget of 50,000 instructions, so a runaway loop can't stall
a frame; exceeding it is a runtime error too.

## Shared values

A [`SharedValue`][pythonnative.SharedValue] holds an `int`, a `float`, a
`bool`, or a `str` (a color) that both threads can read and write.
[`use_shared_value`][pythonnative.use_shared_value] creates one whose
identity is stable for the component's lifetime, like `use_ref`, and
the core releases it when the component unmounts:

```python
offset = pn.use_shared_value(0.0)       # SharedValue[float]
expanded = pn.use_shared_value(False)   # SharedValue[bool]
tint = pn.use_shared_value("#2563EB")   # colors animate too
```

### From a worklet

In a worklet, `offset.value` reads and writes the UI thread's copy
directly. Writing an animation starts it, and writing a plain value
cancels any animation that's running:

```python
@pn.worklet
def release(event: gestures.GestureEvent) -> None:
    if event.velocity_y > 800:
        offset.value = pn.with_timing(CLOSED, duration=180)
    else:
        offset.value = pn.with_spring(OPEN, velocity=event.velocity_y)
```

### From Python

Python works with the same value from event handlers, effects, and
tasks:

- **Reading** `offset.value` returns the latest value the UI thread
  published. It publishes after each frame and each event, without ever
  waiting for a reader. A read that follows a write from Python returns
  the written value until the UI thread has applied it.
- **Writing** `offset.value = 0.0` queues the write behind pending
  mounts, like a view command. Writing an animation
  (`offset.value = pn.with_spring(1)`) starts it.
- **Awaiting** `await offset.animate(animation)` starts an animation and
  returns `True` once it ran to completion, or `False` when something
  interrupted it. Canceling the awaiting task cancels the animation.
- **Canceling** `offset.cancel()` stops a running animation where it is.

```python
@pn.component
def Toast(message: str) -> pn.Node:
    opacity = pn.use_shared_value(0.0)

    async def show() -> None:
        await opacity.animate(pn.with_timing(1, duration=200))
        await asyncio.sleep(2)
        if await opacity.animate(pn.with_timing(0, duration=300)):
            dismiss()

    pn.use_effect(show, [message])
    faded = pn.use_animated_style(lambda: {"opacity": opacity.value})
    return pn.View(pn.Text(message), style=[styles.toast, faded])
```

To run animations in parallel and wait for all of them, gather the
awaits:

```python
await asyncio.gather(
    x.animate(pn.with_spring(0)),
    scale.animate(pn.with_timing(1, duration=250)),
)
```

Reading `.value` during render is allowed, but it isn't reactive: a
render that reads it doesn't run again when the value changes. Read
shared values in worklets, such as an animated style, instead. `pn lint`
reports a read during render as
[`PN203`](linting.md#pn203-shared-values-arent-read-during-render).

## Animations

Six functions build animations. Each returns a frozen descriptor that
you assign to a shared value, in a worklet or in Python, or pass to
`await shared.animate(...)`. Inside a worklet the same calls build the
same descriptors in the core.

```python
pn.with_timing(1.0, duration=300, easing=pn.Easing.ease_out)
pn.with_spring(0.0, velocity=event.velocity_y, damping=20, stiffness=200)
pn.with_decay(velocity=event.velocity_x, clamp=(-200, 0))
pn.with_delay(150, pn.with_timing(1.0))
pn.with_sequence(pn.with_timing(1.2, duration=120), pn.with_spring(1.0))
pn.with_repeat(pn.with_timing(360, duration=1000, easing=pn.Easing.linear), times=None)
```

| Function | What it does |
| --- | --- |
| [`with_timing(to, *, duration=300, easing=None)`][pythonnative.with_timing] | Moves to `to` over `duration` milliseconds along `easing` (ease-in-out by default) |
| [`with_spring(to, *, ...)`][pythonnative.with_spring] | Springs to `to`, starting at `velocity` units per second |
| [`with_decay(*, velocity, deceleration=0.998, clamp=None, rubber_band_factor=0.6)`][pythonnative.with_decay] | Coasts from the current value at `velocity` until it stops; with `clamp=(lower, upper)`, it rubber-bands back from a bound it crosses, or stops at it when `rubber_band_factor` is 0 |
| [`with_delay(delay_ms, animation, *, reduce_motion="system")`][pythonnative.with_delay] | Starts `animation` after a delay |
| [`with_sequence(*animations)`][pythonnative.with_sequence] | Runs animations one after another, each from where the last ended |
| [`with_repeat(animation, *, times=None, reverse=False, reduce_motion="system")`][pythonnative.with_repeat] | Repeats `times` times, or forever when `times` is `None`; with `reverse`, every other run heads back |

`with_timing` and `with_spring` animate numbers and colors; the other
drivers animate numbers. Velocities are in units per second, so a
gesture's `velocity_x` and `velocity_y` carry over directly. A spring
that's still moving when another animation replaces it hands over its
velocity, so retargeting a fling feels continuous.

Every driver takes `on_finish`, a worklet that receives
`finished: bool` on the UI thread (`False` when the animation was
interrupted). To get back to Python from there, call
[`run_on_python`](#calling-python-from-a-worklet).

### Springs

[`with_spring`][pythonnative.with_spring] follows React Native's spring
model. Tune it in one of two ways:

- By feel: `duration` (milliseconds) with `damping_ratio`. The spring
  settles in about that time; `damping_ratio=1` doesn't overshoot, and
  lower values bounce.
- By physics: `damping`, `stiffness`, and `mass` (10, 100, and 1 by
  default).

`overshoot_clamping=True` stops the spring at its target instead of
letting it bounce past, and `rest_displacement` and `rest_speed` set
when it counts as settled. [`pn.Spring`][pythonnative.Spring] holds the
same parameters as a value, for the layout animations and shared-element
transitions that accept `spring=`:

```python
SNAPPY = pn.Spring(duration=350, damping_ratio=0.85)
```

### Easing

[`pn.Easing`][pythonnative.Easing] holds the curves `with_timing`
accepts. They're data, so they cross to the core and evaluate the same
way there and in Python:

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
| `Easing.custom(fn)` | Any `progress -> eased` Python function, sampled at 64 points that the core interpolates |

A name such as `"ease_out"` works wherever a curve does, and a
misspelled name raises `ValueError`.

### Reduce motion

Every animation except `with_sequence`, and every layout animation,
takes `reduce_motion`: `"system"` (the default) follows the platform's
accessibility setting, `"always"` always reduces, and `"never"` ignores
the setting. On Android, turning system animations off counts as reduce
motion. A reduced animation jumps to its final value and still reports
completion, so code that awaits it, or waits for its `on_finish`, keeps
working. A reduced `with_delay` skips its delay, and a reduced
`with_repeat` lands where its last run would end (an endless one stays
put). A sequence and a delay leave their animations to their own
settings, while a repeat that isn't reduced runs every iteration in
full. To branch on
the setting in a render, read
[`use_reduce_motion`][pythonnative.use_reduce_motion].

### Helpers

Four helpers are plain functions in Python and intrinsics in the core,
so a worklet computes the same result in both places:

- [`interpolate(x, input_range, output_range, extrapolate="extend")`][pythonnative.interpolate]
  maps `x` piecewise linearly. Outside the input range, `"extend"`
  continues the nearest segment, `"clamp"` holds the end value, and
  `"identity"` returns `x`; pass a `(left, right)` pair to choose each
  side separately.
- [`interpolate_color(x, input_range, colors)`][pythonnative.interpolate_color]
  blends between colors, clamped at the ends.
- [`clamp(x, lower, upper)`][pythonnative.clamp] limits `x` to a range.
- [`snap_point(value, velocity, points)`][pythonnative.snap_point]
  returns the point a release lands nearest, projected a fifth of a
  second ahead with its velocity, so a flick carries past the nearest
  point the way a sheet or carousel settles.

## Hooks

Five hooks connect a component to the core. None of them takes a
dependency list: their worklets' captures are compared on every render,
and only the ones that changed are sent.

```python
pn.use_shared_value(initial)                       # SharedValue[T]
pn.use_derived_value(worklet)                      # read-only SharedValue[T]
pn.use_animated_style(worklet)                     # AnimatedStyle
pn.use_animated_reaction(prepare, react)           # None
pn.use_frame_callback(worklet, active=True)        # None
```

[`use_derived_value`][pythonnative.use_derived_value] re-runs its worklet
whenever a shared value it read changes, and publishes the result as a
read-only shared value that other worklets, and Python, can read:

```python
progress = pn.use_derived_value(lambda: pn.clamp(offset.value / SHEET_HEIGHT, 0, 1))
```

[`use_animated_style`][pythonnative.use_animated_style] returns an
[`AnimatedStyle`][pythonnative.AnimatedStyle] that goes in any built-in
component's `style` list, after the static styles it overrides. The core
runs the worklet once when the view mounts, before its first frame is
drawn, and again whenever a shared value it read changes:

```python
header = pn.use_animated_style(lambda: {
    "opacity": pn.interpolate(progress.value, (0, 1), (1, 0.6)),
    "transform": [{"scale": pn.interpolate(progress.value, (0, 1), (1, 0.9))}],
})
return pn.View(title, style=[styles.header, header])
```

One animated style can drive several views.

[`use_animated_reaction`][pythonnative.use_animated_reaction] runs
`react(current, previous)` on the UI thread whenever the result of
`prepare` changes. It's the way to respond to a crossing, typically by
calling back into Python:

```python
pn.use_animated_reaction(
    lambda: offset.value > DISMISS_DISTANCE,
    lambda past, _before: pn.run_on_python(set_armed, past),
)
```

[`use_frame_callback`][pythonnative.use_frame_callback] runs a worklet
every display frame while `active` is true. It receives a
[`FrameInfo`][pythonnative.FrameInfo] with `timestamp_ms` and
`delta_ms`:

```python
@pn.worklet
def spin(frame: pn.FrameInfo) -> None:
    angle.value = (angle.value + frame.delta_ms * 0.36) % 360


pn.use_frame_callback(spin, active=playing)
```

## Animatable properties

An animated style can write two kinds of style keys:

- **Paint properties** are applied by the platform on the UI thread, in
  the same frame: `opacity`, `transform`, `background_color`, `color`,
  `border_color` and its sides, `border_radius` and its corners,
  `shadow_color`, `shadow_offset`, `shadow_opacity`, `shadow_radius`,
  `elevation`, `tint_color`, `placeholder_color`, `text_shadow_color`,
  `text_shadow_offset`, `text_shadow_radius`, and `z_index`.
- **Layout properties** are every key the layout engine reads except
  `display`, `position`, `direction`, and `overflow`: `width`, `height`,
  the `min_*` and `max_*` sizes, `margin*`, `padding*`, `top`, `left`,
  `right`, `bottom`, `flex_grow`, `flex_shrink`, `flex_basis`, `gap`,
  `border_width`, `aspect_ratio`, and the rest. The core posts them to
  its layout worker, which updates Yoga and sends the changed frames
  through the normal mount queue.

Any other key, such as `font_size` or `font_family`, is a runtime error
that disables the binding.

**Prefer transforms.** A layout property lands a frame behind the
worklet that wrote it and costs a layout pass every frame, and every
sibling it pushes moves too. A paint property lands in the same frame
and costs nothing beyond drawing. For anything that tracks a finger or
runs every frame, animate `transform` (`translate_x`, `translate_y`,
`scale`, `rotate`) and `opacity`. Keep layout properties for changes
that should reflow their neighbors, like an accordion opening, and
consider a [`layout=` animation](#layout-animations) for those, which
animates the frame instead of the style.

**Precedence is the same on every platform.** A key written by an
animated style replaces the same key from the static style, including
the whole `transform` list, so an animated `transform` must include any
static entries you want to keep. When a re-render removes the animated
style, or its worklet stops returning a key, the platform restores the
static value:

```python
lifted = pn.use_animated_style(lambda: {"transform": [{"scale": 1.05}]} if pressed.value else {})
pn.View(style=[{"transform": [{"rotate": 10}]}, lifted])  # rotate 10, or scale 1.05 while pressed
```

Views with an animated style, `entering`, `exiting`, `layout`,
`shared_tag`, gestures, or worklet event props are never flattened away
(see [View flattening](../concepts/layout.md#view-flattening)).

## Event worklets

Any `on_*` event prop takes a worklet. The core runs it synchronously
when the platform reports the event, and the event isn't sent to
Python. That's most useful for continuous events: `on_scroll`,
`on_layout`, `on_content_size_change`, and a `Pressable`'s press-state
events. A prop holds either a worklet or a Python callback, not both.

```python
scroll_y = pn.use_shared_value(0.0)


@pn.worklet
def track(event: pn.ScrollEvent) -> None:
    scroll_y.value = event.y


header = pn.use_animated_style(lambda: {
    "transform": [{"translate_y": -pn.clamp(scroll_y.value, 0, 120)}],
    "opacity": pn.interpolate(scroll_y.value, (0, 120), (1, 0), extrapolate="clamp"),
})
return pn.Column(
    pn.View(title, style=[styles.header, header]),
    pn.ScrollView(*rows, on_scroll=track),
)
```

The event parameter has the same fields as the typed payload a Python
handler receives ([`ScrollEvent`][pythonnative.ScrollEvent],
[`LayoutEvent`][pythonnative.LayoutEvent], and so on). The
[collapsing header example](../examples/collapsing-header.md) builds a
complete scroll-driven header this way.

## Gesture worklets

Gesture callbacks (`on_begin`, `on_change`, `on_end`, `on_tap`, and the
rest) take worklets the same way. A recognizer can mix them, for
example a worklet `on_change` that moves a view with a Python `on_end`
that saves where it landed:

```python
gestures.Pan(on_change=drag, on_end=lambda event: save_position(event.translation_x))
```

The worklet receives a
[`GestureEvent`][pythonnative.gestures.GestureEvent] with the same field
names a Python callback sees. Gesture worklets run on every platform: on
Android, in the browser preview, and in tests the core's own gesture
engine calls them, and on iOS UIKit's recognizers report through the
core, which runs them before anything reaches Python. The
[Gestures guide](gestures.md#drag-with-spring-back) has more patterns.

## Calling Python from a worklet

[`run_on_python(callback, *args)`][pythonnative.run_on_python] queues
`callback(*args)` on the Python thread:

```python
@pn.worklet
def release(event: gestures.GestureEvent) -> None:
    if event.translation_x < -DISMISS_DISTANCE:
        x.value = pn.with_timing(-WIDTH, duration=180)
        pn.run_on_python(on_dismiss, item_id)
    else:
        x.value = pn.with_spring(0, velocity=event.velocity_x)
```

The callback must be a name the worklet captures, such as a prop, a
state setter, or a function defined in the component; the core holds a
reference to it, not the function itself. Arguments must be values a
worklet can produce: numbers, strings, booleans, `None`, and tuples,
lists, and dicts of them. Calls made in one frame are delivered in
order. Called from Python (in a test, say), `run_on_python` calls the
callback directly.

Calls aren't coalesced, so a worklet that calls Python every frame
floods the Python thread. Call it when something happens, such as a
release or a threshold crossing, not on every change.

## Layout animations

Every built-in view takes three layout animation props, declared once
in [`MotionProps`][pythonnative.MotionProps]:

```python
from pythonnative.motion import FadeIn, FadeOut, LinearTransition

pn.View(
    pn.Text(entry.title),
    entering=FadeIn(duration=200),
    exiting=FadeOut(duration=150),
    layout=LinearTransition(spring=pn.Spring(damping_ratio=0.8, duration=350)),
).with_key(entry.id)
```

- **`entering`** runs when the view is created. Inside a subtree
  created in the same commit, only the outermost entering animation
  runs.
- **`exiting`** runs when the view is removed. Only the outermost
  removed view's exit animation runs, and its whole subtree goes with
  it.
- **`layout`** animates the view from its old frame to its new one
  when a commit moves or resizes it, never on its first layout. Its
  children take their new frames immediately. A new frame during the
  animation retargets from where the view is.

The presets live in [`pythonnative.motion`][pythonnative.motion]. Each
is a frozen dataclass with `duration` (300 milliseconds by default),
`delay`, `easing` or `spring`, and `reduce_motion`:

| Use | Presets |
| --- | --- |
| `entering` | [`FadeIn`][pythonnative.motion.FadeIn], [`SlideIn(edge=...)`][pythonnative.motion.SlideIn], [`ZoomIn`][pythonnative.motion.ZoomIn] |
| `exiting` | [`FadeOut`][pythonnative.motion.FadeOut], [`SlideOut(edge=...)`][pythonnative.motion.SlideOut], [`ZoomOut`][pythonnative.motion.ZoomOut] |
| `layout` | [`LinearTransition`][pythonnative.motion.LinearTransition] (move and resize), [`FadingTransition`][pythonnative.motion.FadingTransition] (fade out at the old frame, then in at the new one) |

`SlideIn` and `SlideOut` move past the window's `"left"`, `"right"`
(the default), `"top"`, or `"bottom"` edge.

### Keyframes

[`Keyframes`][pythonnative.motion.Keyframes] animates through styles at
points of progress from 0 to 1. Numbers and colors blend, and
`transform` lists blend entry by entry when their shapes match. Keys go
back to the view's own style when it finishes. `easings` sets the curve
leading into a keyframe:

```python
from pythonnative.motion import Keyframes

POP = Keyframes(
    {
        0.0: {"opacity": 0, "transform": [{"scale": 0.8}]},
        0.6: {"opacity": 1, "transform": [{"scale": 1.05}]},
        1.0: {"transform": [{"scale": 1.0}]},
    },
    duration=400,
    easings={1.0: pn.Easing.ease_out},
)

pn.View(badge, entering=POP)
```

### Custom layout animations

For anything else, pass a worklet (a decorated function or an inline
lambda). It receives [`LayoutValues`][pythonnative.motion.LayoutValues]
(where the view ends, where it is, and the window's size) and returns
`{"initial": {...}, "animate": {...}}`: a starting style, and an
animation or value per key. Frame keys are `x`, `y`, `width`, and
`height`. Transform channels (`translate_x`, `translate_y`, `scale`,
`rotate`, and the rest) are keys of their own, composed after the
view's own `transform`:

```python
from pythonnative.motion import LayoutValues


@pn.worklet
def drop_in(values: LayoutValues) -> dict:
    return {
        "initial": {"opacity": 0, "translate_y": -values.target_height},
        "animate": {
            "opacity": pn.with_timing(1, duration=200),
            "translate_y": pn.with_spring(0, damping_ratio=0.7, duration=400),
        },
    }


pn.View(card, entering=drop_in)
```

### Turning them off for a subtree

[`LayoutAnimationConfig`][pythonnative.motion.LayoutAnimationConfig]
wraps children in a `View` that turns layout animations off inside it.
`skip_entering=True` skips the entering animations of views mounted
along with it, such as a screen's first rows, so a screen doesn't
animate every row in when it opens. `skip_exiting=True` removes views
inside it at once:

```python
from pythonnative.motion import LayoutAnimationConfig

LayoutAnimationConfig(*rows, skip_entering=True, style={"flex": 1})
```

### How exits work

The component that renders an exiting view unmounts at once, as in
React Native: its effects are cleaned up, its refs are cleared, and its
events stop. Only the native view stays behind. When a commit removes
views, the core finds the outermost removed view that has `exiting` and
sends the platform an `exit` operation for it instead of a `delete`.
The platform leaves the view where it is, stops routing touches to it,
and leaves it out of the child indices later insertions use. The core
runs the exit animation and, when it finishes, tells the platform to
destroy the subtree.

So an exiting row keeps its last frame while it fades, and a new row
inserted beside it lands in the right slot. Layout no longer counts the
exiting view, so its neighbors take their new places right away,
animating there if they have a `layout` animation. View tags are never
reused, so a view that's still animating out can't be confused with a
new one.

Leaving stack screens and the content of a closing `Modal` use the same
mechanism, owned by the platform instead of an animation: the platform
keeps the screen through its native transition and then releases it.
That's why a popped screen keeps its content while it slides away.

### List items

Rows of a [`FlatList`][pythonnative.FlatList] or
[`SectionList`][pythonnative.SectionList] belong to the native list,
which recycles them as you scroll, so list-level props animate them
instead of the row's own `entering` and `exiting`:

```python
from pythonnative.motion import FadeIn, FadeOut, LinearTransition

pn.FlatList(
    data=entries,
    render_item=lambda entry, index: EntryRow(entry),
    key_extractor=lambda entry, index: entry.id,
    item_entering=FadeIn(duration=200),
    item_exiting=FadeOut(duration=150),
    item_layout=LinearTransition(),
)
```

`item_entering`, `item_exiting`, and `item_layout` take one of the
presets (not `Keyframes` or a custom worklet, which raise `TypeError`).
They run only when the data changes: rows that appear because you
scrolled, or that the list recycled, never animate. Each platform runs
them with its list's own machinery: UIKit's collection view layout
attributes and batch updates on iOS, a `RecyclerView.ItemAnimator` on
Android, and FLIP animations on row elements in the browser preview.

Views created along with a list row don't run their own `entering`
animations, so scrolling a recycled cell into view never triggers one.

## Shared-element transitions

Give a view on the screen you push from and a view on the screen you
push to the same `shared_tag`. During the push, and the pop back, the
element flies between them while the screens slide:

```python
from pythonnative.motion import SharedTransition

# The journal row
pn.Image(photo, shared_tag=f"photo-{entry.id}", style=styles.thumbnail)

# The entry screen
pn.Image(
    photo,
    shared_tag=f"photo-{entry.id}",
    style=styles.hero,
    shared_transition=SharedTransition(spring=pn.Spring(damping_ratio=0.9, duration=450)),
)
```

When a stack starts a push or a pop, the platform asks the core for the
views the two screens share. For each pair it hides the source, lifts
the destination view into an overlay at the source's place on screen,
and moves and resizes it to where it belongs, blending `border_radius`,
`background_color`, and `opacity` from the source's style to its own.
At the end the destination returns to its screen and the source shows
again. The destination is the real view, so a loaded image or live
text is what the flight lands on, with no cross-fade.

[`SharedTransition`][pythonnative.motion.SharedTransition] customizes
the flight: `duration` and `easing` for a timed flight, or `spring`, and
`props` for which paint properties blend. Set it on the destination (or
the source). Without one, the flight matches the platform's push.

- **iOS** recreates the stack's slide in a custom transition, and the
  back swipe drives the flight interactively; a canceled swipe flies
  the element back.
- **Android** times the fragment transition to match and flies elements
  in the stack container's overlay. Transitions aren't interactive.
- **The browser preview** aligns its screen transition with the same
  timing and flies elements in the overlay layer.

Shared elements cover pushes and pops within one stack, including
card-style groups. Tabs, `Modal`, modal presentations, and the drawer
aren't covered.

## Components built on Motion

These components are written in Python with worklets and the public
Motion API alone, so their source in `components/bottom_sheet.py`,
`components/swipeable.py`, and `navigation/navigators.py` is a good
reference for your own.

### BottomSheet

[`BottomSheet`][pythonnative.BottomSheet] rises from the bottom of the
window and snaps to detents. It presents in a
[`Portal`][pythonnative.Portal] above the screen, with a grab handle and
an optional dimmed backdrop:

```python
@pn.component
def Inbox() -> pn.Node:
    sheet = pn.use_ref()
    detent, set_detent = pn.use_state(0)
    return pn.View(
        MessageList(),
        pn.Button("Filters", on_press=lambda: sheet.current.expand()),
        pn.BottomSheet(
            FilterPanel(),
            snap_points=(240, "50%", "90%"),
            index=0,                          # -1 starts closed
            on_change=set_detent,
            on_close=lambda: set_detent(-1),
            ref=sheet,
        ),
        style={"flex": 1},
    )
```

Dragging the handle follows the finger. On release, the sheet settles
on the detent that [`snap_point`][pythonnative.snap_point] projects from
the release velocity, rubber-banding past the highest detent and
closing below the lowest one when `close_on_drag_down` is set (the
default). Snap points are heights in points or percentages of the
window, ordered by the height they come to on the current window, with
indexes counting from the lowest. Whenever the sheet settles, after a
drag, a change to `index`, a call on the
[`BottomSheetHandle`][pythonnative.BottomSheetHandle] in `ref`
(`snap_to(index)`, `expand()`, `collapse()`, and `close()`), or a tap on
the backdrop, `on_change` receives the detent's index, or `on_close` runs
if the sheet closed. Tapping the backdrop closes the sheet, or collapses
it when `close_on_drag_down` is off.

With `handle=False`, the whole sheet is the drag target. Content that
scrolls should leave the handle on, since dragging the sheet from inside
a scrolled `ScrollView` isn't supported.

### Swipeable

[`Swipeable`][pythonnative.Swipeable] slides a row aside to reveal
actions behind it:

```python
pn.Swipeable(
    EntryRow(entry),
    right_actions=pn.Pressable(pn.Icon("trash-2"), on_press=lambda: delete(entry.id)),
    right_width=88,
    on_open=lambda side: pn.Haptics.selection(),
)
```

Its pan activates only on horizontal movement and fails on vertical
movement, so a `Swipeable` row works inside a vertical list. On
release, the row opens when it's past `threshold` (half the actions'
width by default), counting where the release velocity would carry it,
and springs closed otherwise. `friction` above 1 makes the row lag
behind the finger, and `overshoot` lets it travel past the actions while
dragging. `on_open` receives `"left"` or `"right"`, and the
[`SwipeableHandle`][pythonnative.SwipeableHandle] in `ref` has
`open_left()`, `open_right()`, and `close()`.

### The drawer

[`DrawerNavigator`][pythonnative.DrawerNavigator] keeps its menu
mounted and follows the finger: swipe from the left edge to pull it
open, and drag it, or tap the dimmed screen, to close it. A spring
settles it either way.

```python
Drawer = pn.DrawerNavigator(
    pn.Screen(FeedScreen, title="Feed"),
    pn.Screen(SettingsScreen, title="Settings"),
    drawer_width=280,
    drawer_type="slide",   # "front" (the default) slides over the screen
    swipe_edge_width=32,   # how far from the edge a swipe can start
    swipe_enabled=True,
)
```

See [Navigation](navigation.md#drawer) for the drawer's navigation
handle.

## Testing

Tests render into the host build of the renderer core, so worklets run
in the same VM they run in on a device, and the
[virtual clock](testing.md#virtual-time) drives the core's frame clock.
Animations, layout animations, and exits advance with
`clock.advance(...)` and finish without sleeping. Three helpers on
[`RenderResult`][pythonnative.testing.RenderResult] read what the
platform would show:

- `drag(target, dx=0, dy=0, *, duration=0.25, steps=10, release=True)`
  sends a pointer stream through the core's gesture engine: down at the
  view's center, `steps` even moves over `duration` seconds (which sets
  the release velocity), and up unless `release` is `False`. Worklet
  callbacks run in the core and Python callbacks run in the test.
  UIKit's recognizers aren't simulated.
- `presented_style(target)` returns the view's style as the platform
  shows it: committed props with motion's writes on top.
- `presented_frame(target)` returns its frame, including layout
  animations.

`fire(target, "on_scroll", {...})` delivers an event to a worklet
handler through the core, just as it delivers one to a Python handler.

```python
import pythonnative as pn
from pythonnative.testing import FakeClock, render


def test_sheet_snaps_open(pn_clock: FakeClock) -> None:
    changes: list[int] = []
    tree = render(pn.View(pn.BottomSheet(pn.Text("filters"), snap_points=(200, 400), on_change=changes.append)))
    handle = tree.get_by_role("adjustable")
    surface = handle.parent

    tree.drag(handle, dy=-150, duration=0.3)
    pn_clock.advance(2.0)
    tree.settle()

    assert changes == [1]
    assert tree.presented_style(surface)["transform"] == [{"translate_y": 0}]


@pn.component
def Feed() -> pn.Node:
    scroll_y = pn.use_shared_value(0.0)

    @pn.worklet
    def track(event: pn.ScrollEvent) -> None:
        scroll_y.value = event.y

    fade = pn.use_animated_style(
        lambda: {"opacity": pn.interpolate(scroll_y.value, (0, 120), (1, 0), "clamp")}
    )
    return pn.Column(
        pn.View(style=[{"height": 40}, fade], test_id="header"),
        pn.ScrollView(pn.View(style={"height": 1000}), on_scroll=track),
    )


def test_header_fades_as_the_list_scrolls(pn_clock: FakeClock) -> None:
    tree = render(Feed())
    scroll = next(view for view in tree.views() if view.type_name == "ScrollView")
    tree.fire(scroll, "on_scroll", {"x": 0, "y": 60})
    assert tree.presented_style(tree.get_by_test_id("header"))["opacity"] == 0.5
```

An exiting view leaves the component tree at once, so a query no longer
finds it, while its native view stays in `tree.backend.native.views`
until the exit animation finishes. Pure worklet logic needs no render at
all: call the worklet as a function.

## Release builds

Release builds ship sourceless bytecode, so a worklet can't be compiled
from its source on the device. Before staging drops the sources,
`pn build` (and `pn run --release`) compiles every `@pn.worklet` function, and every
inline lambda passed to a worklet-only API or to `on_finish=`,
`entering=`, `exiting=`, or `layout=`, into a table named
`pn_worklets.json` beside the app. At run time each worklet is found in
the table by its file, line, and name, and a lambda by where its body
starts, so several lambdas on one line are told apart. A worklet that
doesn't compile fails the build with every error listed:

```text
Some worklets can't run on the UI thread:
  app/screens/journal.py:42:9: `while` loops can't run on the UI thread; use `for i in range(n)`
```

That's why the worklet-only APIs require the decorator or an inline
lambda. A plain function would compile from its source in development
but wouldn't be in the release table, so they raise `TypeError` for one
in every build, and `pn lint` reports it as
[`PN202`](linting.md#pn202-worklet-only-apis-need-a-marked-worklet).

## Migrating from `Animated`

`Animated` was removed, with no compatibility layer: `pn.Animated`
raises `AttributeError`. Each old pattern has a direct replacement:

| `Animated` | Motion |
| --- | --- |
| `v = pn.use_animated_value(0.0)` | `v = pn.use_shared_value(0.0)` |
| `pn.Animated.View(style={"opacity": v})` | `pn.View(style=[base, pn.use_animated_style(lambda: {"opacity": v.value})])` |
| `pn.Animated.Text`, `pn.Animated.Image` | `pn.Text`, `pn.Image`, or any built-in component, with an animated style |
| `v.set_value(1.0)`, `float(v)`, `v.value` | `v.value = 1.0`, `v.value` |
| `pn.Animated.timing(v, to=1, duration=300).start()` | `v.value = pn.with_timing(1, duration=300)` |
| `result = await pn.Animated.timing(...)`, `result.finished` | `finished = await v.animate(pn.with_timing(...))` |
| `pn.Animated.spring(v, to=0, initial_velocity=vy)` | `pn.with_spring(0, velocity=vy)` |
| `pn.Animated.decay(v, velocity=event.velocity_x / 1000)` | `pn.with_decay(velocity=event.velocity_x)` (units per second, not per millisecond) |
| `pn.Animated.sequence([a, b])` | `pn.with_sequence(a, b)` |
| `pn.Animated.parallel([a, b])` | `await asyncio.gather(x.animate(a), y.animate(b))`, or assign each value |
| `pn.Animated.stagger(50, [...])` | `pn.with_delay(i * 50, animation)` for each value |
| `pn.Animated.delay(200)` in a sequence | `pn.with_delay(200, animation)` |
| `pn.Animated.loop(animation, iterations=3)` | `pn.with_repeat(animation, times=3)` (`times=None` repeats forever) |
| `handle.stop()`, `v.stop_animation()` | `v.cancel()` |
| `v.interpolate([0, 1], [0, 100])` | `pn.interpolate(v.value, (0, 1), (0, 100))` in a worklet |
| `a + b`, `1.0 - v / height` | Plain arithmetic in `use_animated_style` or `use_derived_value` |
| `pn.Animated.diff_clamp(v, 0, 64)` | A scroll worklet that keeps its own clamped total (see the [collapsing header](../examples/collapsing-header.md)) |
| `on_scroll=pn.Animated.event(y=scroll_y)` | `on_scroll=track`, where `@pn.worklet def track(event): scroll_y.value = event.y` |
| `v.add_listener(...)` | `pn.use_animated_reaction(...)` with `pn.run_on_python(...)` |
| `easing=lambda t: ...` | `easing=pn.Easing.custom(lambda t: ...)` |
| Gesture callbacks that call `set_value` | `@pn.worklet` gesture callbacks that write `.value` |
| `ANIMATABLE_PROPS` (paint-only) | Paint and layout properties; see [Animatable properties](#animatable-properties) |

`pn.Easing` and its curves are unchanged. `EasingSpec`, the type of a
curve, is no longer exported from `pythonnative`; import it from
`pythonnative.motion`.

## Next steps

- Scroll-driven motion end to end:
  [Collapsing header and bottom sheet](../examples/collapsing-header.md).
- Drags, flings, and composition: [Gestures](gestures.md).
- API reference: [Motion](../api/motion.md).
