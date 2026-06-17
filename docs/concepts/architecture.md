# Architecture

PythonNative combines **direct native bindings** with a **declarative
reconciler**, giving you React-like ergonomics while calling native
platform APIs synchronously from Python.

## High-level model

1. **Declarative element tree.** Your `@pn.component` function returns
   a tree of [`Element`][pythonnative.Element] descriptors (similar to
   React elements / virtual DOM nodes).
2. **Function components and hooks.** All UI is built with
   `@pn.component` functions using
   [`use_state`][pythonnative.use_state],
   [`use_reducer`][pythonnative.use_reducer],
   [`use_effect`][pythonnative.use_effect],
   [`use_navigation`][pythonnative.use_navigation], and friends. The
   API is inspired by React hooks but designed for Python.
3. **Reconciler.** On first render, the
   [`Reconciler`][pythonnative.reconciler.Reconciler] walks the tree
   and creates real native views via the platform backend. On
   subsequent renders it diffs against the previous tree and emits the
   minimal list of mutation ops (create / update / insert / remove /
   destroy / set-frame), applied as **one batched transaction** per
   commit through
   [`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations].
   State-driven renders are
   **local**: a setter marks only its own component subtree dirty, and
   [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
   re-runs just those components instead of the whole app from the
   root (the full tree is only rebuilt on mount, navigation, and hot
   reload). Sibling and ancestor components whose state did not change
   are left untouched.
4. **Post-render effects.** Effects queued via
   [`use_effect`][pythonnative.use_effect] are flushed **after** the
   reconciler commits native mutations, matching React semantics.
   This guarantees that effect callbacks interact with the committed
   native tree.
5. **State batching.** Multiple state updates triggered during a
   render pass (e.g., from effects) are automatically batched into a
   single re-render. Explicit batching is available via
   [`batch_updates`][pythonnative.batch_updates].
6. **Key-based reconciliation.** Children can be assigned stable
   `key` values to preserve identity across re-renders, which is
   critical for lists and dynamic content.
7. **Error boundaries.**
   [`ErrorBoundary`][pythonnative.ErrorBoundary] catches render
   errors in child subtrees and displays fallback UI, preventing a
   single component failure from crashing the entire page.
8. **Direct bindings.** Under the hood, native views are created and
   updated through direct platform calls:
   - **iOS**: rubicon-objc exposes Objective-C/Swift classes
     (`UILabel`, `UIButton`, `UIStackView`, etc.).
   - **Android**: Chaquopy exposes Java classes
     (`android.widget.TextView`, `android.widget.Button`, etc.) via
     the JNI bridge.
9. **Thin native bootstrap.** The host app remains native (Android
   `Activity` or iOS `UIViewController`). It calls
   [`create_screen`][pythonnative.create_screen] internally to bootstrap
   your Python component, and the reconciler drives the UI from
   there.
10. **`App` entry point.** The user's app module (`app/main.py`)
    defines a top-level component named `App`. Native templates
    import that module by path (`"app.main"`) and look up its `App`
    attribute, so users never write a separate registration step.
    Components with other names can still be loaded by passing an
    explicit dotted path like `"app.main.RootScreen"` to the
    template.

## How it works

```text
@pn.component fn   --->   Element tree   --->   Reconciler   --->   Native views
        ^                                            |
        |                                            v
   set_state()   <---------   schedule re-render   batched   --->   diff + patch
                                                                          |
                                                                          v
                                                                     flush effects
```

The reconciler uses **key-based diffing**: children are matched by
key first and by position only as a fallback. When a child with the
same key and type is found, its props are updated in place on the
native view. When the type changes, the old native view is destroyed
and a new one is created.

### Render lifecycle

1. **Schedule phase**: a `use_state` / `use_reducer` setter that
   actually changes a value marks its owning component dirty (adding
   the component's node to the reconciler's dirty set) and asks the
   screen host to schedule a flush. Several setters coalesce into one
   flush.
2. **Render phase**: only the dirty components execute, shallowest
   first so a dirty ancestor's re-render subsumes any dirty descendant.
   Each dirty component re-runs its body against its preserved hook
   state, with the context stack of every enclosing `Provider` restored
   so [`use_context`][pythonnative.use_context] still resolves. Hooks
   record state reads, queue effects, and register memos. No native
   mutations happen yet.
3. **Commit phase**: the reconciler turns the diff for each
   re-rendered subtree into mutation ops referencing view tags, and
   flushes them all in a single `apply_mutations` transaction. Event
   callbacks are routed to the Python-side
   [`EventRegistry`][pythonnative.events.EventRegistry] instead of
   crossing the bridge, so callback-identity churn costs nothing.
4. **Layout phase**: a layout pass recomputes frames and emits
   `SetFrameOp`s only for frames that changed. Leaves whose
   `Element` is unchanged reuse a cached intrinsic measurement, so
   untouched subtrees skip native `measure_intrinsic` calls.
5. **Effect phase**: pending effects are flushed in depth-first order
   (children before parents). Cleanup functions from the previous
   render run before new effect callbacks.
6. **Drain phase**: if effects set state, another flush is
   automatically triggered and the cycle repeats (up to a safety
   limit to prevent infinite loops).

See [Lifecycle](lifecycle.md) for a detailed walkthrough.

## Component model

PythonNative uses a single component model: **function components**
decorated with `@pn.component`.

```python
@pn.component
def Counter(initial: int = 0):
    count, set_count = pn.use_state(initial)
    return pn.Column(
        pn.Text(f"Count: {count}", style={"font_size": 18}),
        pn.Button("+", on_click=lambda: set_count(count + 1)),
        style={"spacing": 4},
    )
```

Each component is a Python function that:

- Accepts props as keyword arguments.
- Uses hooks for state ([`use_state`][pythonnative.use_state],
  [`use_reducer`][pythonnative.use_reducer]), side effects
  ([`use_effect`][pythonnative.use_effect]), navigation
  ([`use_navigation`][pythonnative.use_navigation]), and more.
- Returns an [`Element`][pythonnative.Element] tree describing the
  UI.
- Has its own hook state per call site (each instance gets its own
  slot table).

The entry point [`create_screen`][pythonnative.create_screen] is called
internally by the bundled native templates to bootstrap your root
component. App code does not call it directly.

## Styling

- **`style` prop**: pass a dict (or a list of dicts) to any
  component. For example, `style={"font_size": 24, "color": "#333"}`.
- **StyleSheet**: create reusable named style dictionaries with
  [`StyleSheet.create`][pythonnative.style.StyleSheet.create] and
  compose them with
  [`StyleSheet.compose`][pythonnative.style.StyleSheet.compose].
- **Theming**: use [`ThemeContext`][pythonnative.style.ThemeContext]
  with [`Provider`][pythonnative.Provider] and
  [`use_context`][pythonnative.use_context] to propagate theme
  values through the tree.

## Layout

PythonNative ships its own **pure-Python flexbox engine** (a small,
React-Native-compatible re-implementation of Yoga's algorithm). All
layout decisions are made in Python and then pushed to native views as
absolute frames via `set_frame`. This means the *exact same* layout
rules apply on Android and iOS; there's no platform drift between
`LinearLayout` and `UIStackView`.

The engine is implemented in `pythonnative.layout` and runs as a
dedicated **layout pass** after every commit:

```text
render -> commit (create / update native views)
      -> flush effects
      -> build LayoutNode tree from VNodes
      -> calculate_layout(viewport_w, viewport_h)
      -> backend.set_frame(view, x, y, w, h) for every node
```

[`View`][pythonnative.View] is the **universal flex container** (like
React Native's `View`). It defaults to `flex_direction: "column"`.
[`Column`][pythonnative.Column] and [`Row`][pythonnative.Row] are
convenience wrappers that fix the direction.

### Flex container properties (inside `style`)

- `flex_direction`: `"column"` (default), `"row"`, `"column_reverse"`,
  `"row_reverse"`.
- `justify_content`: main-axis distribution: `"flex_start"`,
  `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`,
  `"space_evenly"`.
- `align_items`: cross-axis alignment: `"stretch"`, `"flex_start"`,
  `"center"`, `"flex_end"`.
- `overflow`: `"visible"` (default), `"hidden"`.
- `spacing`: gap between children (dp / pt).
- `padding`: inner spacing.

### Child layout properties

- `flex`: shorthand for `flex_grow: N, flex_shrink: 1, flex_basis: 0`.
- `flex_grow`, `flex_shrink`, `flex_basis`: individual flex properties.
- `align_self`: override the parent's `align_items` for this child.
- `width`, `height`: fixed dimensions (numbers or `"%"` strings).
- `min_width`, `min_height`, `max_width`, `max_height`: size
  constraints.
- `aspect_ratio`: derive the unknown axis from the known one.
- `margin`: outer spacing.
- `position`: `"relative"` (default) or `"absolute"`. Absolute children
  are removed from the flex flow and positioned via `top` / `right` /
  `bottom` / `left`.

Under the hood:

- **Layout**: `pythonnative.layout.calculate_layout` computes a frame
  `(x, y, w, h)` for every node.
- **Android**: every container is a `FrameLayout`; computed frames are
  applied through `MarginLayoutParams` and `View.setX/setY/setLayoutParams`.
- **iOS**: every container is a plain `UIView` with
  `translatesAutoresizingMaskIntoConstraints = NO`; computed frames are
  applied through `view.frame = CGRect(...)`.
- **Intrinsic content size**: leaf widgets (`Text`, `Button`, `Image`,
  `TextInput`, …) implement `measure_intrinsic` so the engine can ask
  them how big they want to be when no explicit size is set.

See the [Layout engine](layout.md) concept page for a full walkthrough.

## Native view handlers

Platform-specific rendering logic lives in the
`pythonnative.native_views` package, organized into dedicated
submodules:

- `native_views.base`: shared
  [`ViewHandler`][pythonnative.native_views.base.ViewHandler] protocol
  and common utilities (color parsing, padding resolution, container
  visual keys).
- `native_views.android`: Android handlers using Chaquopy's Java
  bridge (`jclass`, `dynamic_proxy`).
- `native_views.ios`: iOS handlers using rubicon-objc
  (`ObjCClass`, `objc_method`).

Every handler implements two layout-facing methods:

- `set_frame(view, x, y, width, height)`: apply an absolute frame
  computed by the layout engine.
- `measure_intrinsic(view, max_width, max_height)`: return the
  natural content size for leaf widgets (used as a hint by the layout
  engine).

`Column`, `Row`, and `View` share a single flex-container handler on
each platform. Containers are simple `FrameLayout` (Android) /
`UIView` (iOS) instances; all flex math lives in
`pythonnative.layout`, so the handlers themselves contain no layout
logic.

Each handler class maps an element type name (e.g., `"Text"`,
`"Button"`) to platform-native widget creation, property updates, and
child management. The
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
owns the tag-to-view table, applies each commit's mutation list, and
lazily imports only the relevant platform module at runtime, so the
package can be imported on any platform for testing.

Native events flow back through a single channel: handlers wire their
platform listeners once at view creation and call
[`dispatch_event`][pythonnative.events.dispatch_event] with the view's
tag; the [`EventRegistry`][pythonnative.events.EventRegistry] resolves
the current Python callback. Gestures
([`pythonnative.gestures`](../api/gestures.md)) and natively-driven
animations (the `Animated` API) ride the same tag infrastructure.

## Comparisons

!!! note "Versus React Native"
    React Native uses JSX plus a JavaScript bridge (or JSI in newer
    versions) plus Yoga layout. PythonNative uses Python plus direct
    native calls plus a Python-implemented Yoga-style flex engine; no
    JS bridge, no serialization overhead, and the same layout rules on
    both platforms.

!!! note "Versus NativeScript"
    NativeScript shares the philosophy of direct, synchronous native
    access, but PythonNative adds a declarative reconciler layer and
    React-like hooks that NativeScript does not have by default.

See [Mental model](mental-model.md) for a wider comparison table.

## iOS flow (rubicon-objc)

- The iOS template (Swift plus PythonKit) boots Python and calls
  [`create_screen`][pythonnative.create_screen] internally with the
  current `UIViewController` pointer.
- The reconciler creates UIKit views and attaches them to the
  controller's view.
- State changes trigger re-renders; the reconciler patches UIKit
  views in place.

## Android flow (Chaquopy)

- The Android template (Kotlin plus Chaquopy) initializes Python in
  `MainActivity` and passes the `Activity` to Python.
- `ScreenFragment` calls [`create_screen`][pythonnative.create_screen]
  internally, which renders the root component and attaches views to
  the fragment container.
- State changes trigger re-render; the reconciler patches Android
  views in place.

## Hot reload (Fast Refresh)

During development, `pn run --hot-reload` watches `app/` for file
changes and pushes updated Python files to the running app, enabling
near-instant UI updates without full rebuilds.

PythonNative uses a **Fast Refresh** strategy:

1. Reload the changed module(s) on the device.
2. For every active screen host, walk the VNode tree and collect every
   component function defined in a reloaded module.
3. Match each one to its replacement by `__module__` +
   `__qualname__` and rewrite `Element.type` in place.
4. Trigger one reconcile pass. Because the VNode and its `HookState`
   are reused, component state (`use_state`, `use_reducer`, refs) is
   preserved across the edit.

If Fast Refresh can't produce a clean swap, the host falls back to a
**full remount** of its root component. See
[Hot reload guide](../guides/hot-reload.md).

## Native API modules

PythonNative provides cross-platform modules for common device APIs:

- [`Camera`][pythonnative.native_modules.camera.Camera]: photo
  capture and gallery picker.
- [`Location`][pythonnative.native_modules.location.Location]: GPS
  and location services.
- [`FileSystem`][pythonnative.native_modules.file_system.FileSystem]:
  app-scoped file I/O.
- [`Notifications`][pythonnative.native_modules.notifications.Notifications]:
  local notifications.

See [Native modules guide](../guides/native-modules.md).

## Navigation

PythonNative navigation is **declarative** and **native-backed**:

- The user describes their app as a tree of navigators
  ([`create_stack_navigator`][pythonnative.create_stack_navigator],
  [`create_tab_navigator`][pythonnative.create_tab_navigator],
  [`create_drawer_navigator`][pythonnative.create_drawer_navigator])
  wrapped in
  [`NavigationContainer`][pythonnative.NavigationContainer], and
  names the root component `App` so the native templates can find
  it.
- The outermost `Stack.Navigator` delegates `navigate(...)`,
  `go_back()`, and `reset(...)` to the platform's native navigation
  controller: `UINavigationController` on iOS and the AndroidX
  Navigation Component on Android. Nested navigators (tabs inside a
  stack, stacks inside tabs) stay in Python and reuse the existing
  reconciler.
- Each pushed native screen is a fresh host with its own reconciler
  and `_ScreenHost`. Initial routes are forwarded via host arguments
  (`__pn_initial_route__` / `__pn_initial_params__`), so a pushed
  screen knows which `Stack.Screen` to render on its first frame.
- Inside any screen, [`use_navigation`][pythonnative.use_navigation]
  returns a `NavigationHandle`; [`use_route`][pythonnative.use_route]
  returns the current route name and params. Both are the same
  hooks regardless of whether the active navigator is native-backed
  or pure-Python.

See the [Navigation guide](../guides/navigation.md) for the full
walkthrough, including how `options={"title": ...}` flows into the
native navigation bar.

- iOS: one host `UIViewController` class, many instances pushed on a
  `UINavigationController`.
- Android: single host `Activity` with a `NavHostFragment` and a
  stack of generic `ScreenFragment`s driven by a navigation graph.

## Next steps

- Read the [Mental model](mental-model.md) for the high-level
  comparisons.
- Walk through the render loop in [Lifecycle](lifecycle.md).
- Dive into the flexbox engine in [Layout engine](layout.md).
- See the platform handlers up close in [Native views](native-views.md).
- Browse the API: [Package overview](../api/pythonnative.md).
