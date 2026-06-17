# Gestures

`pythonnative.gestures` attaches native gesture recognition to any
view-like element through the `gestures=` prop. Six recognizers ship
out of the box: [`Tap`][pythonnative.gestures.Tap],
[`LongPress`][pythonnative.gestures.LongPress],
[`Pan`][pythonnative.gestures.Pan],
[`Swipe`][pythonnative.gestures.Swipe],
[`Pinch`][pythonnative.gestures.Pinch], and
[`Rotation`][pythonnative.gestures.Rotation].

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
position, translation, velocity, scale, and rotation populated as
appropriate for the gesture kind.

## How recognition works

Gesture descriptors are frozen dataclasses: numeric configuration plus
your callbacks. The reconciler serializes the configuration into plain
dicts for the native handler (prop diffing never compares closures)
and routes the callbacks through the same tag-based event channel as
`on_press` et al.

Recognition itself is native:

- **iOS** attaches real `UIGestureRecognizer` instances.
- **Android** feeds raw `MotionEvent` streams into a pure-Python
  [`GestureArbiter`][pythonnative.gestures.GestureArbiter].
- **Desktop preview** feeds Tk pointer events into the same arbiter,
  so gesture code is testable on a laptop.

All gestures attached to one view recognize *simultaneously*.

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
default), reports `on_change` with translation measured from the
activation point, and `on_end` with release velocity, ready to feed
into [`Animated.decay`][pythonnative.Animated] for a fling.

## Callback slots

Continuous gestures (`Pan`, `Pinch`, `Rotation`) expose three slots:

| Slot | Fires |
|---|---|
| `on_begin` | Once, when the gesture activates. |
| `on_change` | Every movement while active. |
| `on_end` | On release (also on cancellation). |

Discrete gestures add a dedicated shortcut: `Tap(on_tap=...)`,
`LongPress(on_long_press=...)` (fires at activation time, like
`UILongPressGestureRecognizer`), and `Swipe(on_swipe=...)` (fires on
release with the resolved `direction`).

## Configuration

```python
gestures.Tap(n_taps=2)                      # double-tap
gestures.LongPress(min_duration_ms=350)     # quicker activation
gestures.Pan(min_distance=4, min_pointers=2)
gestures.Swipe(direction="left", min_velocity=200)
```

`GestureEvent.state` is one of
[`GestureState`][pythonnative.gestures.GestureState] (`"began"`,
`"changed"`, `"ended"`, `"cancelled"`), which matters mostly when you
share one handler across slots.

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
