# Gestures

Native-backed gesture recognition, attached to any view-like element
via the `gestures=` prop. Descriptors are frozen dataclasses; their
numeric configuration crosses the bridge while callbacks are routed
through the tag-based event channel. Every descriptor accepts
`enabled=False` to keep it in the list without recognizing;
[`Pan`][pythonnative.gestures.Pan] adds React Native Gesture Handler's
activation criteria (`active_offset_x`, `fail_offset_y`,
`max_pointers`, `min_velocity`), and
[`GestureEvent`][pythonnative.gestures.GestureEvent] reports the pointer
in both the view's (`x`, `y`) and the window's (`absolute_x`,
`absolute_y`) coordinate space. Swipe and fling directions are typed
as [`SwipeDirection`][pythonnative.SwipeDirection]. See the
[Gestures guide](../guides/gestures.md) for usage patterns.

::: pythonnative.gestures
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]
      show_if_no_docstring: true

## See also

- The [Gestures guide](../guides/gestures.md) walks through taps,
  drags, activation offsets, and gesture-driven animations.
- [Animated](animated.md) pairs with `Pan` velocity for springs and
  decays.
