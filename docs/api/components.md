# Components

Element factory functions for the built-in PythonNative widgets. These
return immutable [`Element`][pythonnative.Element] descriptors; nothing
is mounted to a native view tree until the
[`Reconciler`][pythonnative.reconciler.Reconciler] processes them.

Every argument is a keyword argument on the factory, which makes it
part of the generated native contract for iOS, Android, and the browser
preview. Platform notes (an Android-only ripple, an iOS-only keyboard
appearance) are recorded on the argument itself. Event callbacks
receive the [typed payloads](#typed-event-payloads) below rather than
dicts, and a `ref=` argument receives a typed
[handle](handles.md) after commit.

For the visual and layout properties accepted by each component's
`style` argument, see the
[Component Property Reference](component-properties.md).

::: pythonnative.components
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters:
        - "!^_"
        - "!^(ContentSizeEvent|ImageLoadEvent|KeyPressEvent|LayoutEvent|ScrollEvent|SelectionEvent|WebNavigationEvent)$"

## Typed event payloads

Frozen dataclasses delivered to `on_layout`, `on_scroll` (and the drag
and momentum callbacks), `on_selection_change`, `on_key_press`,
`on_content_size_change`, `on_load`, and the `WebView` navigation
callbacks. Field names match the wire payload, which is what lets
[`Animated.event`][pythonnative.animated.Animated] bind by name
(`Animated.event(y=scroll_y)`).

::: pythonnative.components.events
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Wire interactions with [Hooks](hooks.md).
- Drive a mounted view through its [handle](handles.md).
- Compose styles with [`StyleSheet`][pythonnative.StyleSheet].
- Build navigation with [`NavigationContainer`][pythonnative.NavigationContainer].
