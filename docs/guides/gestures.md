# Gestures

`pythonnative.gestures` attaches native gesture recognition to any
view-like element through the `gestures=` prop. Seven recognizers ship
out of the box: [`Tap`][pythonnative.gestures.Tap],
[`LongPress`][pythonnative.gestures.LongPress],
[`Pan`][pythonnative.gestures.Pan],
[`Swipe`][pythonnative.gestures.Swipe],
[`Fling`][pythonnative.gestures.Fling],
[`Pinch`][pythonnative.gestures.Pinch], and
[`Rotation`][pythonnative.gestures.Rotation], plus three composition
combinators: [`Simultaneous`][pythonnative.gestures.Simultaneous],
[`Race`][pythonnative.gestures.Race], and
[`Exclusive`][pythonnative.gestures.Exclusive].

```python
import pythonnative as pn
from pythonnative import gestures


@pn.component
def TapCard():
    count, set_count = pn.use_state(0)
    return pn.View(
        pn.Text(f"Tapped {count} times"),
        style={"padding": 24, "background_color": "#EEF2FF", "border_radius": 12},
        gestures=[gestures.Tap(on_tap=lambda e: set_count(count + 1))],
    )
```

Every callback receives a
[`GestureEvent`][pythonnative.gestures.GestureEvent] snapshot with
position (`x`, `y` in the view; `absolute_x`, `absolute_y` in the
window), translation, velocity, scale, rotation, and `direction`
populated as appropriate for the gesture kind.

## How recognition works

Gesture descriptors are frozen dataclasses: numeric configuration plus
your callbacks. The reconciler serializes the configuration into plain
dicts for the native handler (prop diffing never compares closures)
and routes the callbacks through the same tag-based event channel as
`on_press` et al.

Recognition itself is native:

- **iOS** attaches real `UIGestureRecognizer` instances.
- **Android** processes `MotionEvent` streams with Kotlin recognizers
  and an arbiter in the native rendering library.
- **The browser preview** streams the page's pointer events into the
  Python [`GestureArbiter`][pythonnative.gestures.GestureArbiter],
  which also supports headless recognition tests.

Gestures listed side by side in the `gestures=` list recognize
*simultaneously*. Use the composition combinators below when you need
them to compete instead.

## Composition: Race, Exclusive, Simultaneous

Real interactions rarely involve one recognizer at a time. Three
combinators, nestable to any depth, control how recognizers relate:

- `Race(a, b, ...)`: the first gesture to activate wins and the
  others are cancelled. Use it when gestures are alternatives, like
  "either long-press to preview or drag to reorder."
- `Exclusive(a, b, ...)`: earlier entries take priority; a later
  entry only fires once every earlier one has *failed*. The canonical
  case is single tap vs. double tap.
- `Simultaneous(a, b, ...)`: the wrapped gestures recognize together,
  like pinch-to-zoom plus rotate on a photo.

```python
from pythonnative import gestures

pn.View(
    photo,
    gestures=[
        gestures.Exclusive(
            gestures.Tap(n_taps=2, on_tap=zoom_in),
            gestures.Tap(on_tap=show_toolbar),   # waits for the double tap to fail
        ),
        gestures.Simultaneous(
            gestures.Pinch(on_change=on_pinch),
            gestures.Rotation(on_change=on_rotate),
        ),
    ],
)
```

With `Exclusive`, a single tap reports only after the double-tap
window closes, and a double tap suppresses the single-tap callback
entirely; you get exactly one of the two. On iOS this maps to
`requireGestureRecognizerToFail`; Android's Kotlin arbiter and the
browser's Python arbiter implement the corresponding priority rules.

## Fling

[`Fling`][pythonnative.gestures.Fling] recognizes a quick directional
flick, optionally with multiple pointers, and reports the resolved
`direction` on release:

```python
gestures.Fling(direction="down", n_pointers=2, on_fling=dismiss)
gestures.Fling(on_fling=lambda e: print(e.direction, e.velocity_x))
```

It differs from `Swipe` in intent: `Swipe` is a single-pointer
directional gesture with a velocity threshold; `Fling` mirrors React
Native Gesture Handler's fling semantics (including the multi-pointer
requirement) and is what you want for "two-finger swipe down to
close."

## Drag with spring-back

The classic pattern: pan moves the view, release springs it home.

```python
import pythonnative as pn
from pythonnative import gestures


@pn.component
def Draggable():
    tx = pn.use_animated_value(0.0)
    ty = pn.use_animated_value(0.0)

    def on_pan(event):
        tx.set_value(event.translation_x)
        ty.set_value(event.translation_y)

    def on_end(event):
        pn.Animated.spring(tx, to=0.0).start()
        pn.Animated.spring(ty, to=0.0).start()

    return pn.Animated.View(
        pn.Text("Drag me"),
        style={
            "transform": [{"translate_x": tx}, {"translate_y": ty}],
            "padding": 24,
            "background_color": "#D1FAE5",
            "border_radius": 12,
        },
        gestures=[gestures.Pan(on_change=on_pan, on_end=on_end)],
    )
```

`Pan` activates once the pointer travels `min_distance` points (10 by
default, unless another activation criterion is set), reports
`on_change` with translation measured from the activation point, and
`on_end` with release velocity, ready to feed into
[`Animated.decay`][pythonnative.Animated] for a fling.

### Activation offsets

Inside a scrolling list a plain `Pan` fights the scroll view. `Pan`
adds React Native Gesture Handler's activation criteria, applied the
same way on iOS, Android, and in the browser preview:

```python
# A horizontal swipe-to-dismiss row inside a vertical list.
gestures.Pan(
    active_offset_x=(-20, 20),   # activate once the finger moves 20 pt left or right
    fail_offset_y=(-15, 15),     # give up if it moves 15 pt up or down first
    max_pointers=1,
    on_change=drag,
)
```

Before activation, with `dx` and `dy` the travel from where the finger
touched down: crossing `fail_offset_x` or `fail_offset_y` fails the
pan for the rest of the interaction; otherwise the pan activates as
soon as `dx` crosses `active_offset_x`, `dy` crosses `active_offset_y`,
the straight-line travel reaches `min_distance`, or the pointer speed
reaches `min_velocity` (points per second). Each offset is a single
number (`20` means `dx > 20`, `-20` means `dx < -20`) or a
`(negative_bound, positive_bound)` pair. The default 10-point
`min_distance` applies only when no offset or velocity criterion is
given; pass it explicitly to combine it with them. `min_pointers` and
`max_pointers` bound how many fingers may take part: too many fingers
fail a pending pan and cancel an active one.

## Callback slots

Continuous gestures (`Pan`, `Pinch`, `Rotation`) expose three slots:

| Slot | Fires |
|---|---|
| `on_begin` | Once, when the gesture activates. |
| `on_change` | Every movement while active. |
| `on_end` | On release (also on cancellation). |

Discrete gestures add a dedicated shortcut: `Tap(on_tap=...)`,
`LongPress(on_long_press=...)` (fires at activation time, like
`UILongPressGestureRecognizer`), and `Swipe(on_swipe=...)` /
`Fling(on_fling=...)` (fire on release with the resolved `direction`).
`direction` is a [`SwipeDirection`][pythonnative.SwipeDirection]
(`"left"`, `"right"`, `"up"`, or `"down"`) or `None` for other gesture
kinds; `Swipe(direction=None)` and `Fling(direction=None)` accept any
direction.

## Configuration

```python
gestures.Tap(n_taps=2)                      # double-tap
gestures.LongPress(min_duration_ms=350)     # quicker activation
gestures.Pan(min_distance=4, min_pointers=2)
gestures.Swipe(direction="left", min_velocity=200)
gestures.Pan(on_change=drag, enabled=can_drag)   # keep the slot, stop recognizing
```

Every descriptor accepts `enabled=False`. A disabled gesture stays in
the list, so sibling indices and composition nodes are unchanged, but
it never recognizes and is skipped by `Race` and `Exclusive`
arbitration, so a later `Exclusive` member doesn't wait for it. Toggle
`enabled` from state instead of rebuilding the `gestures=` list.

`GestureEvent.state` is a
[`GestureState`][pythonnative.gestures.GestureState] enum member
(`BEGAN`, `CHANGED`, `ENDED`, `CANCELLED`), which matters mostly when
you share one handler across slots:

```python
from pythonnative.gestures import GestureState


def on_pan(event):
    match event.state:
        case GestureState.BEGAN:
            grab()
        case GestureState.CHANGED:
            move(event.translation_x, event.translation_y)
        case GestureState.ENDED | GestureState.CANCELLED:
            release()
```

It is a `str` enum, so `event.state == "ended"` also works.

## Gestures vs. `Pressable`

[`Pressable`][pythonnative.Pressable] (and `on_press`) remains the
right tool for plain buttons: it adds pressed-state feedback and
accessibility semantics. Reach for `gestures=` when you need motion
(drags, flicks, pinches) or multi-tap/long-press recognition on an
arbitrary view.

## Testing

The arbiter that powers Android and desktop recognition is pure
Python, so gesture logic is unit-testable with scripted pointer
streams; see `tests/test_gestures.py` for ready-made patterns.

## Next steps

- Pair gestures with the [Animated API](animations.md) for
  physics-driven UI.
- API reference: [Gestures](../api/gestures.md).
