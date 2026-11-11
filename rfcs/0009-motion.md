# RFC 0009: Motion

- Status: Implemented
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-11-09
- Implemented in: the `feat/motion` branch (this pull request)
- Supersedes / Superseded by: replaces the `Animated` API (RFC 0002), the
  animation graph format, the core animator, and paint-only animated props
  (RFC 0007), `Animated.event` bindings for scroll and gesture events, and the
  browser preview's cloned "ghost" views for leaving screens and modals.
  Everything else in those RFCs remains implemented.

## Summary

PythonNative renders native widgets, lays out off the UI thread, and runs
animations on the UI thread, but no application logic can run there. A
drag can move a view only by a fixed expression of the finger's
translation. Anything conditional, such as snapping to the nearest detent,
clamping, rubber-banding, or deciding whether a release dismisses, waits a
round trip through the Python thread. Views can't animate in, out, or to
their new position when the tree changes. Screens can't share an element
across a push. So the interactions people expect from a native app (bottom
sheets, swipeable rows, drawers that follow the finger, list items that
slide into place, a photo that flies from a list into a detail screen)
can't be built at native quality.

This RFC adds the layer Reanimated and Gesture Handler give React Native,
in Python's idiom:

- **Worklets.** Ordinary, type-checked Python functions marked with
  `@pn.worklet`, compiled from their syntax tree into a small bytecode that
  the renderer core runs on the UI thread. The same functions still run as
  plain Python in tests.
- **Shared values** that both threads read and write, **animations**
  (`with_timing`, `with_spring`, `with_decay`, and composition) assigned to
  them or awaited from Python, and hooks that derive styles and values from
  them every frame.
- **Event and gesture worklets.** Any continuous event prop or gesture
  callback takes a worklet and runs it on the UI thread.
- **Layout animations.** `entering=`, `exiting=`, and `layout=` on any view,
  with item animations for native lists.
- **Shared-element transitions.** `shared_tag=` pairs views across a stack
  push or pop.
- **Components built on all of it.** `BottomSheet`, `Swipeable`, and a
  rebuilt `DrawerNavigator` that follows the finger.

`Animated` is deleted, not kept alongside. Every renderer runs the same
implementation, because worklets, drivers, and layout animations all live
in the C++ core that iOS, Android, the browser preview, and pytest already
share.

## Motivation

### Interaction logic can't leave the Python thread

The core evaluates an animation graph of arithmetic, `interpolate`, and
`diff_clamp` nodes (`native/core/src/animation.cpp`), and `Animated.event`
copies event fields into graph values. That covers a parallax header and a
view that tracks a finger. It doesn't cover the next step of almost every
gesture-driven component:

```python
# Today: the release decision runs on the Python thread.
def on_end(event: gestures.GestureEvent) -> None:
    target = nearest(SNAP_POINTS, offset.value + event.velocity_y * 0.2)
    pn.Animated.spring(offset, to=target, velocity=event.velocity_y).start()
```

The callback waits behind whatever the application thread is doing:
rendering, a JSON decode, an import. While it waits, the sheet sits still
under a finger that has already let go. React Native had the same problem
with the JavaScript thread, and Reanimated's worklets are how the
ecosystem solved it. The problem is sharper in Python. The 300-component
re-render in `scripts/benchmark-runtime.py` takes 50 to 90 ms on a desktop
CPU, so any interaction that needs Python per frame or per release will
visibly hitch on a phone.

Animated props are also paint-only (`ANIMATABLE_PROPS`: opacity, a fixed
set of transform channels, `background_color`, and `color`). Height, border
radius, shadow, and border color can't animate at all.

### Views appear, disappear, and move without animating

There's no way to animate a view when it mounts or unmounts, or when a
commit moves it. A new list row appears fully formed, a deleted one
vanishes, and its siblings jump. Every host applies a `delete` op
immediately and removes the view in the same mount pass, so there's
nowhere for an exit animation to run.

### Screens can't share an element

There's no shared-element transition. A thumbnail can't grow into the
header image of the screen it opens.

### Defects found on the same paths

The audit behind this RFC found these on the paths it rewrites:

1. **Leaving screens lose their content before they animate out.** The
   reconciler destroys children before parents, and the core writes every
   delete at the start of a transaction (`shadow.cpp`). When a screen is
   popped, its subviews are removed in the same mount pass that tells the
   native stack to pop. iOS keeps only the empty `PNLogicalScreen`, and
   Android removes the fragment's view before the fragment transaction's
   exit animation runs. The browser preview works around this by cloning
   the leaving screen with `cloneNode` (`renderer.js`), whose own comment
   says Python destroys the real views in the same transaction. The clone
   may already be missing its children. This finding comes from reading
   the code, and implementation will confirm it on each platform before
   fixing it.
2. **Static and animated transforms combine differently on each host.**
   iOS composes animated channels after the static `transform`
   (`PNTransform.swift`), Android writes both into the same `View`
   properties so the last write wins (`ViewStyler.kt`), and the browser
   replaces the static transform whenever any channel is animated
   (`renderer.js`).
3. **The graph evaluator compares strings every frame.** Each node's kind
   is a `std::string`, compared against `"add"`, `"multiply"`, and so on
   for every node on every frame.
4. **The drawer doesn't animate.** `DrawerNavigator` mounts its menu only
   while it's open and shows and hides it without a transition or a
   gesture (`navigation/navigators.py`).

## Reference behavior

| Concern | React Native | This RFC |
| --- | --- | --- |
| UI-thread code | Reanimated worklets: functions a Babel plugin marks with `'worklet'`, copied into a second JavaScript runtime on the UI thread | `@pn.worklet` functions compiled from Python's `ast` to bytecode that the C++ core runs. No second interpreter |
| State shared across threads | `useSharedValue`, `.value` | `pn.use_shared_value`, `.value` |
| Animations | `withTiming`, `withSpring`, `withDecay`, `withDelay`, `withSequence`, `withRepeat` | `with_timing`, `with_spring`, `with_decay`, `with_delay`, `with_sequence`, `with_repeat`, plus `await shared.animate(...)` |
| Derived styles and values | `useAnimatedStyle`, `useDerivedValue`, `useAnimatedReaction`, `useFrameCallback` | `use_animated_style`, `use_derived_value`, `use_animated_reaction`, `use_frame_callback` |
| Calling back to the app | `runOnJS(fn)(args)` | `run_on_python(fn, *args)` |
| Gesture callbacks on the UI thread | Gesture Handler 2 callbacks are worklets | Gesture callbacks that are worklets run on the UI thread; others run on the Python thread, as today |
| Scroll events on the UI thread | `useAnimatedScrollHandler` | Any continuous event prop takes a worklet |
| Animated components | `Animated.View`, `Animated.createAnimatedComponent` | None needed: every view takes an animated style |
| Layout animations | `entering`, `exiting`, `layout` props with builder presets (`FadeIn.duration(300).delay(50)`) | The same props with keyword presets (`FadeIn(duration=300, delay=50)`) |
| List item animations | `itemLayoutAnimation` on `Animated.FlatList` | `item_entering`, `item_exiting`, `item_layout` on `FlatList` and `SectionList`, run by the native list |
| Shared elements | `sharedTransitionTag` (experimental) | `shared_tag`, for stack pushes and pops |
| Old animation API | `Animated` stays in React Native core | `Animated` is deleted |

Deliberate differences:

- **A compiled subset, not a second runtime.** Reanimated can copy a
  JavaScript function into another runtime because a JavaScript engine is
  cheap to embed twice and the Babel plugin captures closures at build
  time. A second CPython interpreter on the UI thread would bring garbage
  collection pauses onto that thread, couldn't run in the WebAssembly
  browser preview, and would rule out the many C extensions that aren't
  safe in subinterpreters (see "Alternatives considered"). A worklet only
  has to compute numbers, colors, and styles, so a verified bytecode that
  the core interprets is enough, and it runs identically on every target.
- **Keyword arguments instead of builder chains.** `FadeIn(duration=300)`
  is a frozen dataclass that type checkers verify, rather than
  `FadeIn.duration(300)`.
- **Awaitable animations.** `finished = await offset.animate(with_spring(0))`
  carries forward the `await Animated.timing(...)` contract that Python
  code already relies on.
- **One animation system.** React Native keeps `Animated` for
  compatibility. Pre-1.0, PythonNative replaces it.

## Design

### Overview

```python
import pythonnative as pn
from pythonnative import gestures


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

`drag`, `release`, and the lambda never run on the Python thread. The core
runs `drag` when the pan reports a change, which updates `x` and `y`. It
re-runs the animated style because it read them, and the host applies the
new transform before the frame is drawn. On release, assigning
`with_spring` starts a driver that the core advances every display frame.

| Thread | Runs |
| --- | --- |
| Python application thread | Components and hooks; compiling and installing worklets; reading and writing shared values; awaiting animations; `run_on_python` callbacks |
| Platform UI thread, inside the core | Event and gesture worklets, animation drivers, derived values, reactions, frame callbacks, animated styles, layout animations, and shared-element flights |

The core's deadlock rule from RFC 0007 stands: the UI thread never waits
on another thread and never takes the commit lock. Everything in this RFC
that runs on the UI thread lives in the core's mount-side state, next to
the gesture arbiters and list data sources it already owns.

### Worklets

#### What a worklet is

A worklet is a function the core can run on the UI thread. There are two
ways to write one:

- A function decorated with `@pn.worklet`, at module level or inside a
  component.
- An inline `lambda` passed directly to an API that only accepts worklets:
  `use_animated_style`, `use_derived_value`, `use_animated_reaction`,
  `use_frame_callback`, `on_finish=`, and custom layout animations.

APIs that accept either kind of callback (event props and gesture
callbacks) run a decorated worklet on the UI thread and anything else on
the Python thread, as today. The decorator is the visible marker for code
that leaves Python's thread, so an existing `lambda` handler never moves
threads silently.

A worklet is still a Python function. Calling it from Python runs it as
Python, so pure logic can be unit tested directly, and a type checker sees
ordinary annotations.

#### The language

Worklets are written in a subset of Python chosen so the core can verify,
bound, and interpret them without an interpreter's runtime:

| Construct | Supported |
| --- | --- |
| Parameters | Positional parameters, with annotations. An event parameter's annotation (`pn.ScrollEvent`, `gestures.GestureEvent`) types its attribute reads |
| Literals | `int`, `float`, `bool`, `None`, `str`, tuples, lists, and dicts with string keys |
| Names | Parameters, locals, captured closure variables, and module globals |
| Operators | `+ - * / // % **`, unary `-`, `+`, and `not`; comparisons, including chains, `in` and `not in` over sequences, strings, and dicts, and `is` and `is not`; `and`, `or`, and conditional expressions |
| Statements | Assignment, augmented assignment, tuple unpacking, `if`/`elif`/`else`, `for` over `range(...)` or a sequence, `break`, `continue`, `return`, `pass`, and expression statements |
| Comprehensions | List and tuple comprehensions over `range(...)` or a sequence, with `if` filters |
| Calls | Other worklets; `abs`, `min`, `max`, `round`, `int`, `float`, `bool`, and `len`; `math` functions and constants; the motion helpers in this RFC; `run_on_python` |
| Attributes | `.value` on shared values (read and write), `.cancel()` on shared values, and fields of event parameters (read) |
| Subscripts | Indexing tuples, lists, and strings by integer, and dicts by string key (read) |

Everything else is a compile error that names the construct and suggests
an alternative, including `while`, `try`, `with`, `import`, nested `def`
or `class`, `lambda` inside a worklet, `global`, `nonlocal`, `yield`,
`await`, f-strings, star arguments, slices, `del`, item assignment, and
attribute writes other than `.value`.

Semantics follow Python wherever the subset reaches. `//` and `%` floor
toward negative infinity, `round` rounds half to even, `/` is true
division, division by zero raises `ZeroDivisionError`, `and` and `or`
return an operand, truthiness follows Python's rules, and comparing a
number with a string raises `TypeError`. Numbers are IEEE doubles that
carry an integer flag, so `7 // 2` is `3` and `int` results stay integers
up to 2**53.

#### Captures

A worklet's free variables and globals are resolved when it's installed,
after the component renders:

- **Shared values** become references to the core's value. Reads and
  writes go to the UI thread's copy.
- **Other worklets** are linked into the program.
- **`None`, numbers, strings, and tuples of them** become constants.
- **Attribute and subscript chains on any other object** are evaluated
  once, at install, and become constants. `styles.colors.accent` or
  `SNAP_POINTS[2]` reads the theme or table that was current when the
  component rendered.

Anything else (a Python callable, an open file, a live object read
through a method call) is a compile error that points at `run_on_python`
for callables. Installs are cheap: a program is compiled once per code
object, and each render only sends captures that changed.

#### Compilation

`pythonnative.motion.compiler` parses a worklet's source with `ast`,
checks it against the subset, resolves captures, and emits a program: a
constant table, a capture table, and stack-machine instructions with a
source line for each instruction. The core verifies every program when
it's installed (operand indices, jump targets, stack depth, and call
arity) before the program can run on the UI thread.

Source isn't always present, so programs are keyed by code object rather
than by source text:

- **Development, tests, the browser preview, and PythonNative Go** have
  sources. A worklet compiles the first time it's installed, never at
  import, so RFC 0005's rule that importing an app doesn't read source
  still holds.
- **Release builds** ship sourceless bytecode (`project/bytecode.py`). Before
  the sources are deleted, staging runs `pythonnative.motion.precompile`
  over the staged tree. It compiles every `@pn.worklet` function and every
  inline `lambda` passed to a worklet-only API (or to an `on_finish`,
  `entering`, `exiting`, or `layout` keyword) into a table,
  `pn_worklets.json`, at the root of each staged tree (the app and its
  packages on iOS, the Python source root on Android). At runtime every
  table on `sys.path` is merged, and a code object is looked up by its
  file, first line, and name; a lambda also by where its body starts,
  which both `ast` and `co_positions()` report, so a lambda on a line with
  other lambdas is still found. File names match by their longest
  bundle-relative suffix, which covers both the bytecode's recorded paths
  and absolute ones. A worklet that fails to compile fails the build with
  a list of every failure.
- **Fast Refresh** drops the cached syntax tree of a reloaded module. The
  reloaded functions are new code objects, so they compile from the new
  source and their components reinstall them on the next render.

The compiler supports the `ast` of every Python version PythonNative
supports for host tests (3.13 and 3.14). Apps embed 3.13.

#### Errors and limits

A compile error raises `pn.motion.WorkletError` with the file, line, and
column, and `pn lint` reports the same errors statically (see "Tooling").
A runtime error on the UI thread (`ZeroDivisionError`, `TypeError`, an
unknown style key) disables that one binding. It reaches Python as a
`WorkletError` with the source line and the worklet's component stack,
through `pn.set_error_handler` with the phase `"worklet"`, and in
development through the error screen and DevTools Problems.

Every run has an instruction budget (50,000 instructions), so a worklet
can't stall a frame indefinitely. Exceeding it is a runtime error.

#### Calling Python

```python
@pn.worklet
def release(event: gestures.GestureEvent) -> None:
    if event.translation_x > DISMISS_DISTANCE:
        x.value = pn.with_timing(WIDTH, duration=180)
        pn.run_on_python(on_dismiss, item_id)
```

`run_on_python(callback, *args)` queues `callback(*args)` on the Python
thread. Arguments must be constants or values a worklet can produce. The
callback must be captured, so it's a constant reference resolved at
install. Calls made in one frame are delivered in order.

### Shared values

```python
offset = pn.use_shared_value(0.0)   # SharedValue[float]
open_ = pn.use_shared_value(False)  # SharedValue[bool]
tint = pn.use_shared_value("#2563EB")  # colors animate too
```

`SharedValue[T]` holds an `int`, `float`, `bool`, or `str` (colors). Its
identity is stable for the component's lifetime, like `use_ref`, and the
core releases it on unmount.

- **In a worklet**, `shared.value` reads and writes the UI thread's copy
  directly. Writing an animation (`shared.value = pn.with_spring(1)`) starts
  it, and writing a plain value cancels any running animation.
- **In Python**, reading `shared.value` returns the latest value the UI
  thread published, which it does after each frame and each event without
  ever waiting for the reader. A write is queued behind pending mounts,
  like a view command, and a read that follows a write from Python returns
  the written value until the UI thread has applied it.
- **Awaiting.** `finished = await shared.animate(animation)` starts an
  animation and returns `True` when it ran to completion or `False` when it
  was interrupted or canceled. Canceling the awaiting task cancels the
  animation. `shared.cancel()` stops a running animation where it is.

Reading `.value` during render is allowed but isn't reactive: it doesn't
schedule a re-render when the value changes. `pn lint` warns about it.

### Animations

```python
pn.with_timing(to, *, duration=300, easing=pn.Easing.ease_in_out, reduce_motion="system", on_finish=None)
pn.with_spring(to, *, damping=10, stiffness=100, mass=1, velocity=0, overshoot_clamping=False,
               rest_displacement=0.01, rest_speed=2, duration=None, damping_ratio=None,
               reduce_motion="system", on_finish=None)
pn.with_decay(*, velocity, deceleration=0.998, clamp=None, rubber_band_factor=0.6,
              reduce_motion="system", on_finish=None)
pn.with_delay(delay_ms, animation, *, reduce_motion="system")
pn.with_sequence(*animations)
pn.with_repeat(animation, *, times=None, reverse=False, reduce_motion="system",
               on_finish=None)  # None repeats forever; times < 1 raises
```

These are frozen dataclasses. They're built in Python and sent with a
`shared.animate(...)` call, or built inside a worklet. They animate numbers,
and `with_timing` and `with_spring` also animate colors. The spring
follows React Native's model, so `duration` with `damping_ratio` gives a
critically tuned spring that settles on time. `with_decay(clamp=(lo, hi))`
rubber-bands past its bounds when `rubber_band_factor` is nonzero.
`on_finish` is a worklet that receives `finished: bool` on the UI thread.

`reduce_motion` is `"system"` (follow the accessibility setting), `"always"`,
or `"never"`. A reduced animation jumps to its final value and still
reports completion. A reduced delay is skipped, and a reduced repeat lands
where its last run would end. A sequence and a delay leave their
animations to their own settings, while a repeat that isn't reduced runs
every iteration in full.

`pn.Easing` keeps its named curves, `Easing.bezier`, and sampled Python
callables, and moves to `pythonnative.motion`.

Helpers that worklets and Python share:

- `pn.interpolate(x, input_range, output_range, extrapolate="extend")`, where
  `extrapolate` is `"extend"`, `"clamp"`, `"identity"`, or a
  `(left, right)` pair.
- `pn.interpolate_color(x, input_range, colors)`.
- `pn.clamp(x, lower, upper)`.
- `pn.snap_point(value, velocity, points)`: the point a release lands
  nearest, projected with the velocity.

### Hooks

```python
pn.use_shared_value(initial: T) -> SharedValue[T]
pn.use_derived_value(worklet: Callable[[], T]) -> SharedValue[T]           # read-only
pn.use_animated_style(worklet: Callable[[], pn.Style]) -> pn.AnimatedStyle
pn.use_animated_reaction(prepare: Callable[[], T], react: Callable[[T, T | None], None]) -> None
pn.use_frame_callback(worklet: Callable[[pn.FrameInfo], None], *, active: bool = True) -> None
```

None of them takes a dependency list. Captures are compared on every
render, which is what Reanimated's Babel plugin approximates in
JavaScript.

- **`use_derived_value`** re-runs its worklet whenever a shared value it
  read changes, and publishes the result as a read-only shared value.
- **`use_animated_style`** returns an `AnimatedStyle` that goes in any
  built-in component's `style=` list, after the static styles it
  overrides. The core runs the worklet once when the view mounts, before
  its first frame is drawn, and again whenever a shared value it read
  changes.
- **`use_animated_reaction`** runs `react(current, previous)` when the
  result of `prepare` changes, typically to call `run_on_python`.
- **`use_frame_callback`** runs every display frame while `active` is true,
  with `FrameInfo(timestamp_ms, delta_ms)`.

On each frame the core runs, in order: animation drivers, derived values,
reactions, frame callbacks, and then animated styles. A shared value that
changes partway through is seen by everything after it in the same
frame, and each binding runs at most once per frame.

### Animatable properties

An animated style can write paint properties and layout properties. Keys
that only make sense statically (`display`, `position`, `direction`, and
`overflow`) and text keys (font family, size, and weight, and the text
transforms) aren't animatable, and an animated style that returns one
raises a `ValueError` naming it. There are two kinds:

- **Paint properties** (`opacity`, `transform`, `z_index`,
  `background_color`, `color`, `tint_color`, `placeholder_color`,
  `border_color` and its sides, `border_radius` and its corners,
  `shadow_color`, `shadow_offset`, `shadow_opacity`, `shadow_radius`,
  `elevation`, and `text_shadow_*`) are applied by the host on the UI
  thread, in the same frame.
- **Layout properties** (every key Yoga reads, such as `width`, `height`,
  `min_*`, `max_*`, `margin*`, `padding*`, `top`, `left`, `right`,
  `bottom`, `flex_grow`, `flex_shrink`, `flex_basis`, `gap`,
  `border_width`, and `aspect_ratio`; enumerated keys like `align_items`
  jump rather than interpolate) are posted to the core's layout worker, which updates Yoga and queues the changed frames
  through the normal mount queue. They land one frame behind and cost a
  layout pass each frame. The guide recommends transforms for anything
  that tracks a finger, as Reanimated's does.

**Precedence is the same everywhere:** a key written by an animated style
replaces the same key from the static style, including the whole
`transform` list. When a re-render removes the animated style, or its
worklet stops returning a key, the host restores the static value. This
replaces iOS's per-channel composition, Android's last-write-wins, and the
browser's replacement rule with one rule.

Views with an animated style, `entering`, `exiting`, `layout`,
`shared_tag`, gestures, or worklet event props are never flattened.

### Event and gesture worklets

Any `on_*` event prop the host reports takes a worklet, such as
`on_scroll` (on `ScrollView`, `FlatList`, and `SectionList`),
`on_content_size_change`, and the press-state events of `Pressable`. The core runs it synchronously
when the host reports the event, and the event isn't sent to Python. A
prop holds either a worklet or a Python callback, not both. `on_layout` is
the exception: the core computes layout on the commit side and reports it
to Python, so it stays a Python callback.

```python
scroll_y = pn.use_shared_value(0.0)

@pn.worklet
def track(event: pn.ScrollEvent) -> None:
    scroll_y.value = event.y

header = pn.use_animated_style(lambda: {
    "transform": [{"translate_y": -pn.clamp(scroll_y.value, 0, 120)}],
    "opacity": pn.interpolate(scroll_y.value, (0, 120), (1, 0), extrapolate="clamp"),
})
return pn.Column(pn.View(title, style=[HEADER, header]), pn.ScrollView(*rows, on_scroll=track))
```

Gesture callbacks (`on_begin`, `on_change`, `on_end`, `on_tap`, and the
rest) take worklets the same way, and a recognizer can mix them, for
example a worklet `on_change` with a Python `on_end`. The core runs gesture
worklets where it already feeds animated event bindings: in `MountState`,
for both the core's gesture engine (Android, the browser preview, and
tests) and iOS's UIKit recognizers, which already report through
`pn_core_event`. `GestureEvent` fields keep their names.

### Layout animations

```python
from pythonnative.motion import FadeIn, FadeOut, LinearTransition, SlideIn

pn.View(
    *chips,
    entering=SlideIn(edge="bottom", duration=250),
    exiting=FadeOut(duration=150),
    layout=LinearTransition(spring=pn.Spring(damping=18)),
)
```

Every view-like component gains three props:

- **`entering`** runs when the view is created. Inside a subtree created
  in the same commit, only the outermost entering animation runs. Views
  created in the same commit as their list row aren't animated, so
  scrolling a recycled cell into view never triggers them.
- **`exiting`** runs when the view is removed. Only the outermost removed
  view's exit animation runs, and its subtree goes with it.
- **`layout`** animates the view from its old frame to its new one when a
  commit moves or resizes it (never on its first layout). Its children
  take their new frames immediately. A new frame during an animation
  retargets from where the view is.

Presets are frozen dataclasses with `duration`, `delay`, `easing` or
`spring`, and `reduce_motion`:

- Entering: `FadeIn`, `SlideIn(edge=...)`, `ZoomIn`.
- Exiting: `FadeOut`, `SlideOut(edge=...)`, `ZoomOut`.
- Layout: `LinearTransition`, `FadingTransition`.
- `Keyframes({0.0: {...}, 0.6: {...}, 1.0: {...}}, duration=400)`, with
  progress from 0 to 1 and an optional easing per keyframe.
- A custom worklet that receives the target frame and window size and
  returns `{"initial": {...}, "animate": {...}}`, a starting style and an
  animation per key.

`pythonnative.motion.LayoutAnimationConfig(*children, skip_entering=...,
skip_exiting=...)` turns these off for its subtree. It renders a `View`
(which takes `style`) carrying `skip_entering` and `skip_exiting` props.
`skip_entering` skips the entering animations of views created in the same
commit as the config, such as a list's first rows on a screen's first
render; views added later still animate. `skip_exiting` removes views
inside it at once instead of animating them out.

An animation's first display frame is its start: the first frame after the
runtime was idle advances drivers by zero, so a view draws its entering
animation's initial values before anything moves.

**How exits work.** When a commit removes nodes, the core computes the
outermost removed node that has `exiting`, writes a new `exit` mount op
for it instead of `delete`, and drops the deletes of its descendants. The
host leaves the view where it is and stops routing touches to it. It also
leaves exiting views out of the child indices that later `insert` ops use.
The core runs the exit animation and, when it finishes, puts a `remove`
record in the frame's writes. The host then destroys the subtree. The
component itself unmounts immediately, as in React Native: its effects are
cleaned up, its refs are cleared, and its events stop. View tags come from
a monotonic counter (`reconciler/vnode.py`), so a held view's tag is never
reused.

**Native lists.** Rows of `FlatList` and `SectionList` belong to the native
list, so list-level props animate them: `item_entering`, `item_exiting`,
and `item_layout`. Each takes one of the presets above (not keyframes or
custom worklets) and applies only to dataset changes, never to recycling or
scrolling. Hosts implement them with their list's own machinery:

- iOS: `initialLayoutAttributesForAppearingItem`,
  `finalLayoutAttributesForDisappearingItem`, and `performBatchUpdates`
  inside a timed or spring `UIView` animation.
- Android: a `RecyclerView.ItemAnimator` driven by the preset.
- Browser preview: FLIP on row elements.

### Screen transitions and shared elements

**Leaving screens and modal content become exits.** A destroyed `Screen`
inside a `ScreenStack`, and a destroyed `Modal`, are written as `exit` ops
owned by the host rather than by an animation. The host keeps the view
through its native transition and calls `pn_core_exit_finished` when the
transition ends. This fixes defect 1 on every host and deletes the
browser's cloned ghosts. A host may report an exit before the core has
registered it (an unanimated pop finishes while the platform applies the
transaction); the core remembers that and removes the subtree as soon as
the exit arrives.

**Shared elements.** Views with the same `shared_tag` on the outgoing and
incoming screens of one stack fly between them during a push or pop:

```python
# The journal row
pn.Image(photo, shared_tag=f"photo-{entry.id}", style=styles.thumbnail)

# The entry screen
pn.Image(photo, shared_tag=f"photo-{entry.id}", style=styles.hero,
         shared_transition=SharedTransition(spring=pn.Spring(damping_ratio=0.9, duration=450)))
```

The core decides what flies and how; each platform animates the flight
natively, which is what keeps it in step with the platform's own screen
transition (including an interactive back swipe on iOS). The commit side
records which `Screen` every view with a `shared_tag` belongs to, walking
up through list rows. When a host starts a push or pop between two
screens, it calls `pn_core_shared_elements(core, surface, from_screen,
to_screen)`, which pairs mounted (and exiting) views by tag and returns,
per pair, the source and target tags, the `shared_transition` (from the
target, else the source), and both views' committed paint properties
(corner radii, background color, opacity, and shadow). The host measures
both views in window coordinates with its own geometry, which accounts for
scrolling, hides the source, lifts the target into a transition overlay at
the source's rect, and animates it to its own rect while blending the
listed properties (`border_radius`, `background_color`, and `opacity` by
default). At the end it puts the target back at its original index and
frame and shows the source again. Frames the core sends while a view is
flying are applied when it lands.

`shared_transition=` customizes timing (`duration` and `easing`, or
`spring`) and which properties blend. The default matches the platform's
push. When a push or pop has shared elements, the host times the screens'
own transition the same way:

- **iOS** returns a `PNSharedElementTransition`
  (`UIViewControllerAnimatedTransitioning`) from
  `navigationController(_:animationControllerFor:from:to:)`. It recreates
  the stack's slide (and the fade and slide-from-bottom variants) and flies
  elements in the transition context's container view. An edge pan that
  starts only when pairs exist drives a pop through a
  `UIPercentDrivenInteractiveTransition`; canceling flies elements back.
  iOS 26's full-width back swipe can only drive UIKit's own animation, so
  it's turned off while the top screen shares elements with the one below,
  and the edge pan pops it alone. Elsewhere that swipe waits for any `Pan`
  that horizontal travel can begin, as it does for a scroll view.
- **Android** gives both fragments' animations the flight's duration and
  curve, and flies elements in the stack container's `ViewGroupOverlay`.
  Transitions aren't interactive (see "Non-goals").
- **The browser preview** gives its CSS screen transition the same timing
  and flies elements with the Web Animations API in `#pn-overlays`.

Shared elements cover push and pop within one stack, including card-style
groups. Tabs, `Modal`, and modal presentation groups aren't covered.

### Components built on Motion

These are written in Python with worklets and the public API alone. That
makes them the acceptance test that the API is enough.

```python
sheet = pn.use_ref()
pn.BottomSheet(
    FilterPanel(),
    snap_points=(240, "50%", "90%"),
    index=0,                # initial detent; -1 starts closed
    on_change=set_detent,   # Python callback with the settled index
    backdrop=True,
    ref=sheet,              # sheet.current.snap_to(2), .close()
)
```

- **`BottomSheet`** presents in a `Portal` with a handle and an optional
  backdrop. It follows the finger and settles on the detent that
  `snap_point` projects from the release velocity, rubber-banding past the
  top detent and closing below the lowest when `close_on_drag_down` is set.
  Its handle is `BottomSheetHandle` (`snap_to`, `expand`, `collapse`,
  `close`). With `handle=True` (the default) the sheet drags by its grab
  handle, so content inside scrolls normally; without a handle the whole
  sheet drags. Handing a drag over between a scrolled `ScrollView` and the
  sheet isn't part of this RFC. `on_change` and `on_close` run once the
  sheet's spring settles, after a drag as after a `snap_to`.
- **`Swipeable`** reveals `left_actions` and `right_actions` behind a row,
  with `threshold`, `friction`, `overshoot`, `on_open(side)`, and
  `on_close`. Both run once the row settles somewhere new, so a drag that
  springs back where it started reports nothing. Its handle is
  `SwipeableHandle` (`open_left`, `open_right`, `close`). It uses a `Pan`
  with horizontal activation and vertical failure offsets, so it works
  inside a vertical list.
- **`DrawerNavigator`** keeps its menu mounted, slides it with a spring,
  fades a backdrop, and opens with a swipe from the edge
  (`swipe_edge_width`, `swipe_enabled`, `drawer_type="front"` or `"slide"`).
  Dragging the menu or the backdrop closes it.

The reference app, Field Notes, uses all three ideas: journal rows slide
left to reveal Delete (`Swipeable`), rows animate in, out, and into place
(`item_entering`, `item_exiting`, `item_layout`), a row's photo flies into
the entry screen (`shared_tag`), and a journal with more tags than its chip
row shows offers them all in a `BottomSheet`.

### The core

`native/core/src/animation.{h,cpp}` is replaced by three pairs of files,
flat in `native/core/src/` beside the rest of the core so every build
(setuptools, CMake, Swift Package Manager, and Emscripten) picks them up
unchanged:

| File | Responsibility |
| --- | --- |
| `motion_vm.{h,cpp}` | The worklet value (number with an integer flag, bool, none, string, sequence, map, shared value, closure, intrinsic, Python callback), program decoding and verification, the interpreter with its budget and source lines, Python's arithmetic and comparison rules, the intrinsics, and colors |
| `motion_anim.{h,cpp}` | Timing, spring, and decay, plus delay, sequence, and repeat, for numbers and colors, with easing curves and completion callbacks |
| `motion_runtime.{h,cpp}` | Shared values, bindings (derived values, reactions, frame callbacks, animated styles, handlers), dependency tracking, the frame order, the published snapshot Python reads, animated style writes and restores, entering, exiting, and layout animations, exits, the writes buffer, and `pn_core_worklet_eval` |

The commit side (`shadow.cpp`) plans exits (grouping removed views under
the outermost removed view), writes `exit` ops, records entering and moved
frames as motion records in the transaction, records which `Screen` each
`shared_tag` view belongs to, applies animated layout props as overrides
on the Yoga node, and never flattens a view with a motion prop. Mount state
(`mount.cpp`) runs worklet handlers for events and gestures, holds exiting
views' props, and pairs shared elements. The runtime starts the recorded
animations when the UI thread finishes the transaction; hosts apply writes
right after each transaction and each event, so entering views draw their
initial state on their first frame.

Shared values are global in the core rather than per surface, because a
value owned by one component can drive views in a portal or another
screen. Python allocates their ids. Messages about a shared value or
binding go to the surface whose request created it.

### C ABI and wire contract (protocol 8)

`PN_CORE_PROTOCOL_VERSION` and Python's `PROTOCOL_VERSION` go from 7 to 8.

Removed: `pn_core_animate`.

Added:

```c
/* Queue a motion request behind pending mounts: `program`, `shared`, `set`,
 * `animate`, `cancel`, `bind`, `release`, or `batch`. */
PN_CORE_API char *pn_core_motion(pn_core *core, int64_t surface, const char *request);
/* The latest published value of a shared value, as JSON. Never blocks the UI thread. */
PN_CORE_API char *pn_core_shared_read(pn_core *core, int64_t id);
/* Run one worklet outside the runtime (tests and tooling). */
PN_CORE_API char *pn_core_worklet_eval(const char *request);
/* A platform-owned exit finished; the core sends its `remove` write. */
PN_CORE_API void pn_core_exit_finished(pn_core *core, int64_t surface, int64_t tag);
/* Views sharing a `shared_tag` between two screens, as JSON pairs. */
PN_CORE_API char *pn_core_shared_elements(pn_core *core, int64_t surface, int64_t from_screen, int64_t to_screen);
```

Requests are JSON. Closures, shared values, intrinsics, and Python
callbacks travel as single-key marker objects (`{"__closure__": {"program",
"captures"}}`, `{"__shared__": id}`, `{"__intrinsic__": "with_spring"}`,
`{"__python__": id}`), and animation descriptors as maps marked
`"__animation__": true`. Python batches the requests a render makes and
sends them just before that render's commit.

Mount transactions gain op `8 exit`: `i64 tag, u8 owner` (0 when the core
animates the view out, 1 when the platform does).

The writes buffer from `pn_core_take_writes` gains a kind byte per record:

| Kind | Payload | Meaning |
| --- | --- | --- |
| 0 `prop` | `i64 tag, str prop, value` | A paint property; `null` resets it (the core sends the committed value explicitly when there is one) |
| 1 `frame` | `i64 tag, f64 x, f64 y, f64 width, f64 height` | A layout animation frame, in the mounted parent's coordinates |
| 2 `remove` | `u32 count, i64 tags...` | An exit finished: destroy each view, children first |

Component props: every component contract gains `entering`, `exiting`,
`layout`, `shared_tag`, `shared_transition`, `skip_entering`, and
`skip_exiting`. `VirtualList` gains `item_entering`, `item_exiting`, and
`item_layout`. Python encodes presets (and custom worklets, as `{"type":
"custom", "worklet": closure}`) before they reach the core. Animated styles
and worklet handlers reach the core as one internal prop, `_pn_motion`,
which carries `{"style": [binding ids], "events": {"on_scroll": binding
id, ...}}`. Handler bindings are shared by every view whose closure is the
same, and Python counts each view's references so a binding is released
when the last view using it goes. Gesture specs gain `"worklets"`, keyed by
gesture state (`began`, `changed`, `ended`, `cancelled`), and `"python":
false` when no Python callback is left, in place of `animated_events`.

Messages to Python, with the kind `motion`, are `finished` (an awaited
animation settled), `call` (`run_on_python`), and `error` (a worklet
failed, with its name, file, line, exception type, and message).

### Native hosts

All three hosts make the same changes:

- **Writes.** Decode the three write kinds. A `prop` write merges the value
  into the view's props and runs the manager's normal update for that key
  (a `null` like a removed key), with fast paths for opacity and transform.
  The old per-channel animated transforms are gone, so a `transform` write
  replaces the static transform. `frame` writes use the transform-safe
  frame path; `remove` writes destroy views like `delete` ops and skip tags
  already gone.
- **Exits.** Apply `exit` ops by keeping the view in place with touches off,
  and map later `insert` indices past exiting siblings. Platform-owned
  exits start the native pop or dismissal without destroying anything and
  report `pn_core_exit_finished` after `mount_finished` when the transition
  ends.
- **Flights.** Pair with `pn_core_shared_elements` and fly natively, as
  described above.
- **Lists.** Animate dataset changes with `item_entering`, `item_exiting`,
  and `item_layout`.

Per host:

- **iOS (`PythonNativeKit`).** `PNAnimator` becomes `PNMotionApplier`.
  `PNViewState.animatedTransform` and the channel composition in
  `PNTransform` are deleted. Two manager hooks start platform-owned exits:
  `exitChild` on the stack and `exitView` on the modal (with a two-second
  fallback in case UIKit drops the completion), and
  `PNScreenManager.detachesOnDestroy` is deleted. `PNSharedElementTransition`
  flies elements. `PNVirtualListManager` runs structural patches through
  `performBatchUpdates` inside one timed or spring animation, using a key
  diff (with moves found by a longest-increasing-subsequence pass) and a
  layout whose appearing and disappearing attributes apply the presets.
- **Android (`pythonnative` module).** `PNAnimator` becomes
  `PNMotionApplier`, reached through `ComponentManager.setMotionProperty`.
  `ViewStyler` resets every transform channel before applying a list, so a
  written transform replaces the static one. `ScreenStackManager.exitChild`
  removes the fragment with its pop animation and reports the exit when the
  fragment's view is destroyed; `ModalManager.beginExit` dismisses the
  dialog. `SharedElementFlight` flies elements, `MotionTiming` maps timing
  and springs to interpolators, and `PNItemAnimator` runs the list presets.
  Rows a dataset change removes are drawn into a snapshot before their views
  go, so `item_exiting` has something to animate.
- **Browser preview.** `applyAnimated` becomes `applyWrites`; the
  `animTransform` composition, the screen-pop and modal ghosts, and their CSS
  are deleted. Exiting views get `pointer-events: none` and `inert`. Rows
  animate with FLIP, and deleted rows keep their elements until
  `item_exiting` ends. The page core is the same C++ compiled to
  WebAssembly, so it runs the same VM.

### Python

New package `src/pythonnative/motion/`:

| Module | Contents |
| --- | --- |
| `__init__.py` | Public API |
| `compiler.py` | `ast` to program; the subset checks; capture resolution |
| `program.py` | Instruction set, encoding, and source maps |
| `shared.py` | `SharedValue`, reads, pending writes, and awaiting |
| `animations.py` | `with_*`, `Easing`, `Spring`, and the helpers |
| `hooks.py` | The hooks above and `AnimatedStyle` |
| `layout.py` | Entering, exiting, and layout presets; `Keyframes`; `LayoutAnimationConfig` |
| `transitions.py` | `SharedTransition` |
| `worklets.py` | The `@worklet` marker, the program cache, the release table, intrinsics, and capture encoding |
| `runtime.py` | What each transport's core already has, request batching, handler reference counts, and `motion` messages |
| `precompile.py` | Release staging and the `pn_worklets.json` table |

New components: `components/bottom_sheet.py` and `components/swipeable.py`.
`navigation/navigators.py` rebuilds the drawer. The reconciler resolves
`AnimatedStyle` entries and worklet handlers into `_pn_motion`, and the
bridge backend replaces its animation hooks with `motion` requests.

### Tooling

- **`pn lint`** gains:
  - `PN201`: a worklet doesn't compile, reported with the compiler's
    message.
  - `PN202`: an API that only accepts worklets receives a name that isn't
    a decorated worklet, which would work in development and fail in a
    release build.
  - `PN203`: `.value` is read during render.

  `use_shared_value` joins the stable hooks for `PN103`.
- **Release builds** (`pn build`, `pn run --release`) run `precompile`
  during staging and fail on any worklet error.
- **DevTools.** Worklet errors reach Problems through the error handler,
  with the worklet's file and line. Motion-specific panels are follow-up
  work (see "Non-goals").
- **Testing library.**
  - `RenderResult.drag(target, dx=0, dy=0, *, duration=0.25, steps=10)`
    sends a pointer stream through `pn_core_pointer`. UIKit recognizers
    aren't simulated, as today.
  - `RenderResult.presented_style(target)` returns the style as the host
    would show it, motion writes included.
  - The virtual clock drives the host core's frame clock, so layout
    animations, exits, and flights run in pytest.

### Exports

`pythonnative` adds:

- `worklet`, `SharedValue`, `AnimatedStyle`, and `FrameInfo`.
- The hooks: `use_shared_value`, `use_derived_value`, `use_animated_style`,
  `use_animated_reaction`, and `use_frame_callback`.
- The animations: `with_timing`, `with_spring`, `with_decay`, `with_delay`,
  `with_sequence`, `with_repeat`, `Easing`, and `Spring`.
- The helpers: `interpolate`, `interpolate_color`, `clamp`, `snap_point`,
  and `run_on_python`.
- The components: `BottomSheet`, `BottomSheetHandle`, `Swipeable`, and
  `SwipeableHandle`.

Presets, `Keyframes`, `SharedTransition`, `LayoutAnimationConfig`, and
`WorkletError` live in `pythonnative.motion` and aren't re-exported, which
keeps the top-level namespace to what most screens use.

## Removals

- **Python:**
  - `src/pythonnative/animated.py` and `animation_graph.py`.
  - The exports `Animated`, `AnimatedValue`, `AnimationResult`, and
    `use_animated_value`, along with `Animated.View`, `Animated.Text`,
    `Animated.Image`, `Animated.event`, `Animated.diff_clamp`, and the
    `sequence`, `parallel`, `stagger`, `delay`, and `loop` composites.
    Parallel animations are `asyncio.gather` over `shared.animate(...)`
    calls.
- **Reconciler and bridge:**
  - `AnimatedEvent` handling in `components/_base.py` and
    `reconciler/core.py`.
  - The `_pn_animated_events` prop and the `animated_events` gesture
    spec.
  - The backend's `set_animated_property`, `install_animation_graph`,
    `start_animation`, `cancel_animation`, and `release_view_backend`;
    the transport's `animate`; and `native_animation_message`.
- **Core:**
  - `animation.{h,cpp}`, `pn_core_animate`, `Transaction::animations` (it
    becomes motion records), and the animation graph format.
  - The rule that animated props are paint-only.
- **Hosts:**
  - `PNAnimator.swift` on iOS and `PNAnimator.kt` on Android, the
    animation-graph drivers.
  - iOS per-channel animated transform composition
    (`PNViewState.animatedTransform`).
  - `PNScreenManager.detachesOnDestroy`.
  - The browser's `cloneNode` ghosts for screen pops and modals.
- **Tests:**
  - `tests/test_animated.py`, `tests/test_animated_easing.py`, and
    `tests/test_animated_graph.py`. The driver and easing cases move to
    the new suite.
  - The nine E2E animation screens and flows under `animations/`. The
    new Motion category replaces them; the suite file keeps the name
    `suites/animations.yaml`.
- **Docs:**
  - `docs/guides/animations.md` becomes `docs/guides/motion.md`.
  - `docs/api/animated.md` becomes `docs/api/motion.md`.
  - `docs/examples/collapsing-header.md` is rewritten.
  - Every other page that mentions `Animated` is updated.

No shims are kept: `import pythonnative as pn; pn.Animated` raises
`AttributeError`, and the release notes show each old pattern next to its
replacement.

## Alternatives considered

- **A Python subinterpreter on the UI thread.** PEP 684 gives each
  subinterpreter its own GIL, so real Python could run there. But garbage
  collection and allocation would pause the UI thread unpredictably, the
  browser preview's WebAssembly core couldn't run it, many C extensions
  refuse to load in subinterpreters, and every host would need to start
  and manage a second interpreter. The compiled subset gives the same
  authoring model with none of that.
- **Translating CPython bytecode instead of `ast`.** It would avoid the
  release precompile step, but bytecode changes between minor versions
  (host tests run 3.13 and 3.14) and loses structure the compiler needs
  for clear errors.
- **Growing the expression graph.** Adding conditional and clamp nodes to
  `Animated` would keep the API, but writing control flow as operator
  graphs is unreadable, and it still couldn't express a release decision
  or a frame callback.
- **Keeping `Animated` alongside Motion.** Two systems would mean two sets
  of bindings in every host and two answers in the docs, for no users who
  need compatibility yet.
- **Platform shared-element APIs.** UIKit's zoom transition needs iOS 18
  and covers one style. Android's Fragment shared-element transitions behave
  differently from it, and the browser has neither. One core-driven flight
  behaves the same everywhere.
- **Snapshots for flights.** Snapshotting the source is simpler, but the
  destination's real content (a loaded image, live text) is what the
  screen ends on. Lifting the destination view avoids a cross-fade at the
  end.
- **Keeping exiting components alive in Python.** The reconciler could hold
  unmounted components until their exit animation ends, but their effects,
  keys, and subscriptions would outlive the tree that owns them. Holding
  only the native view matches React Native.
- **Builder chains for presets.** `FadeIn.duration(300).delay(50)` reads
  naturally in JavaScript. Keyword arguments on frozen dataclasses are
  what Python type checkers and editors understand.

## Non-goals

- Running arbitrary Python, or any library, on the UI thread.
- `use_animated_props` for non-style props, and `measure()` or
  `scroll_to()` inside worklets. Each needs per-component work and can
  follow.
- Keyboard and sensor shared values (`useAnimatedKeyboard`,
  `useAnimatedSensor`).
- Keyframes and custom worklets for native list items.
- Shared elements across tabs, `Modal`, modal presentation groups, or the
  drawer; interactive transitions on Android; and Android's predictive
  back preview.
- Retargeting a flight in progress. A flight reads both frames when it
  starts; if either view relays out mid-flight, it lands on the
  destination's final frame without bending its path.
- Motion panels in DevTools (live shared values and running bindings).
  The inspector shows presented styles; the panels can follow.
- Precompiling worklets in third-party packages for Android release
  builds. iOS release builds precompile every staged module; Android
  precompiles the app's own sources, and a package's worklets compile at
  run time if its sources ship.
- The rest of Gesture Handler 2: manual activation, native gesture
  wrappers, hover, and force touch. iOS gestures keep UIKit recognizers.
- Native sheet detents (`UISheetPresentationController`), material top
  tabs, and a pager component. `BottomSheet` is drawn by PythonNative, as
  Gorhom's sheet is in React Native.
- Dragging a `BottomSheet` from inside a scrolled `ScrollView`.
- Reducing Python's render cost, a native reconciler, and replacing
  Chaquopy. That's the next RFC.

## Testing and rollout

What landed with this RFC, and what's still to run:

- **Compiler** (`tests/test_motion_compiler.py`): every rejected construct
  with its file, line, column, and message; capture resolution, including
  folded attribute chains and unfolded `.value`; precompile keys for
  several lambdas on one line; release tables that replace sources; and a
  precompile that reports every broken worklet at once.
- **VM conformance** (`tests/test_motion_vm.py`): a differential suite
  that runs each case in CPython and in the host core's VM and requires
  identical results or the same exception type. It covers arithmetic,
  negative floor division and modulo, half-to-even rounding, chained
  comparisons, short-circuit operands, truthiness, integer flags, loops
  and comprehensions, `math`, the motion helpers, animation descriptors
  built in a worklet, the instruction budget, and a few hundred generated
  expressions.
- **Program verifier:** malformed programs (jumps out of range, stack
  underflow, inconsistent stack depths, bad constants, locals, captures,
  and operators, and unknown opcodes) are rejected without running.
- **Runtime and layout animations** (`tests/test_motion.py` and
  `tests/test_core.py`): shared values read, written, and awaited from
  Python; interrupted awaits; derived values, reactions, and frame
  callbacks; scroll and gesture worklets; style precedence and restore;
  layout props through the layout worker; error reporting; release on
  unmount; presets, keyframes, and custom layout worklets; entering skip
  rules; exits that hold a subtree, host-owned screen exits (including a
  report that arrives before its record), and parents removed without
  exiting; shared-element pairing; reduce motion; and `run_on_python`
  calls in flight across a re-render.
- **Components:** `BottomSheet` snapping by position and velocity and
  following a window that changes size, `Swipeable` thresholds, the
  drawer's edge swipe, and the handles of both, all with
  `RenderResult.drag` in pytest.
- **Hosts:** XCTest (`PNMotionTests`, plus updates to the mount, gesture,
  manager, and parity tests; 100 pass) and Robolectric
  (`MotionRobolectricTest` and the mount decoder test; 96 pass) cover
  write decoding, `exit` handling, insert indices that skip exiting
  views, transform precedence, and portals mounted in the same commit as
  their screen. `tests/browser/motion.mjs` and the Motion cases in
  `tests/browser/renderer.mjs` cover the preview against the WebAssembly
  core, rebuilt with Emscripten 4.0.10.
- **End to end:** a Motion category of 14 screens in the E2E suite, with
  Maestro flows for each: the three drivers, easing, interpolation,
  composition, frame callbacks, the collapsing header, a drag that keeps
  tracking while Python is deliberately busy, layout animations, list
  item animations, a shared-element push and pop, a bottom sheet, and a
  swipeable row. No flow covers the interactive shared-element pop on
  iOS: XCTest's synthesized touches don't start screen-edge recognizers
  on the iOS 18 simulator CI uses. The drawer keeps its navigation flow.
  `tests/test_e2e_suite_renders.py` renders every screen headlessly, and
  `scripts/check-e2e-coverage.py` tracks the new sources. The flows run
  in CI on an Android emulator and an iOS simulator. The release build
  was also checked by hand on the iOS simulator (precompiled worklets
  load, the swipeable row and card drag track while Python sleeps for 10
  seconds, the shared element flies on push and pop, chips animate in
  and out, and the sheet opens).
- **Performance:** `scripts/benchmark-runtime.py` adds
  `motion_frame_200_styles_us`, recorded in
  `rfcs/benchmarks/0009-motion.json` with a same-machine comparison
  against `main`. An instruction-count budget in CI and dropped-frame
  counts from the drag-under-load screen weren't added.
- **Reference app:** Field Notes adopts swipe-to-delete on journal rows,
  item animations for new and deleted entries, a shared photo from a
  journal row to the entry screen, and a `BottomSheet` listing every tag
  when there are more than fit in the filter row.
- **Docs:** the Motion guide, the API page, the rewritten
  collapsing-header example, and a migration table from `Animated`.
  `mkdocs build --strict` passes.
- **Rollout:** protocol 8 needs a matching PythonNative Go, which the
  release already builds with an exact version match.

## Open questions

- **Lifting or snapshotting a destination that's still loading.** If the
  destination image hasn't loaded when a flight starts, lifting it flies
  an empty view. One option is to snapshot the source until the
  destination reports its intrinsic size.
- **Layout-prop latency.** Layout properties land a frame behind because
  Yoga runs on the layout worker. If that's visible in practice, a narrow
  UI-thread relayout for an animated subtree is possible, but it would
  have to keep the deadlock rule.
- **Program encoding.** Programs travel as JSON inside `pn_core_motion`
  requests like other requests do. A binary encoding can come later if
  install time shows up in traces.
- **The `run_on_python` rate.** Calls aren't coalesced. A worklet that
  calls Python every frame floods the event mailbox, so `pn lint` may need
  to warn about it.
- **Frame cost.** A frame driving 200 animated styles takes about 1.6 ms
  on an Intel Mac host build, about 8 microseconds per style. Most of it
  is allocation in the VM's value type and in diffing and encoding style
  maps. That's within budget for typical screens, and a flatter value
  representation can come later if device traces show it.

## Results

Measured on an Intel Mac host; see `rfcs/benchmarks/0009-motion.json`.

| Measure | `main` | This RFC |
| --- | --- | --- |
| `import pythonnative` (`-X importtime`, median) | 269 ms | 237 ms |
| Re-render 300 components (median) | 69.8 ms | 70.3 ms |
| Core commit of 300 views (median) | 8.3 ms | 8.0 ms |
| One motion frame, 200 animated styles (median) | Not applicable | 1.6 ms |

Import got faster because Motion loads lazily and the eager `Animated`
modules are gone. Rendering and commit costs are unchanged within noise.
On the iOS simulator, a release build kept a worklet drag, a swipeable
row, and a shared-element flight running smoothly while the Python thread
slept for 10 seconds, which `Animated` couldn't do for anything decided at
release.
