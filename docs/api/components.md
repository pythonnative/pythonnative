# Components

Element factory functions for the built-in PythonNative widgets. These
return immutable [`Element`][pythonnative.Element] descriptors; nothing
is mounted to a native view tree until the
[`Reconciler`][pythonnative.reconciler.Reconciler] processes them.

Containers take their children positionally as `*children: pn.Node`,
and every other argument is a keyword argument on the factory, which
makes it part of the generated native contract for iOS, Android, and
the browser preview. Keywords shared by many components are declared
once as [shared props](#shared-props) instead of in every factory. Platform notes (an Android-only ripple, an iOS-only keyboard
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

## Shared props

Every built-in view accepts the
[`AccessibilityProps`][pythonnative.AccessibilityProps] keywords, and
`View`, `Column`, `Row`, and `Pressable` also accept the
[`ViewProps`][pythonnative.ViewProps] layout and gesture keywords.
Factories declare them as `**props: Unpack[...]`, so a type checker
validates each keyword as if it were spelled out in the signature.
Built-in props are validated at run time only in development builds.

::: pythonnative.components.props
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## List data and records

`ListData` publishes explicit keyed edits to `FlatList`. `Section` gives each
section a stable identity, and `ViewableItem` describes a visible item. See the
[list guide](../guides/lists.md) for ownership, batching, and performance details.

::: pythonnative.list_data
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members: [ListData, Section, ViewableItem]
      members_order: source
      filters: ["!^_"]

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
- Group named styles with [`StyleSheet`][pythonnative.StyleSheet].
- Build navigation with [`NavigationContainer`][pythonnative.NavigationContainer].
