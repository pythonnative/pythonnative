# Gestures

Native-backed gesture recognition, attached to any view-like element
via the `gestures=` prop. Descriptors are frozen dataclasses; their
numeric configuration crosses the bridge while callbacks are routed
through the tag-based event channel. See the
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
  drags, and gesture-driven animations.
- [Animated](animated.md) pairs with `Pan` velocity for springs and
  decays.
