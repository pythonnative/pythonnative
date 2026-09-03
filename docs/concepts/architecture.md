# Architecture

PythonNative combines a **declarative reconciler** in Python with a
**native rendering core** in Swift and Kotlin. Python owns the
component tree, reconciliation, and layout; `PythonNativeKit` (iOS) and
the `pythonnative` Gradle module (Android) own every native view,
gesture recognizer, animation, and device API. The two halves talk over
a small, versioned [bridge](bridge.md), one transaction per commit.

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
   [`flush_dirty`][pythonnative.reconciler.core.Reconciler.flush_dirty]
   re-runs just those components instead of the whole app from the
   root (the full tree is only rebuilt on mount, navigation, and hot
   reload). Sibling and ancestor components whose state did not change
   are left untouched.
4. **Post-render effects.** Effects queued via
   [`use_layout_effect`][pythonnative.use_layout_effect] run
   synchronously inside the commit (after frames are set), and effects
   queued via [`use_effect`][pythonnative.use_effect] are flushed
   **after** the commit completes, matching React semantics. This
   guarantees that effect callbacks interact with the committed native
   tree.
5. **State batching.** Multiple state updates triggered during a
   render pass (e.g., from effects) are automatically batched into a
   single re-render. Explicit batching is available via
   [`batch_updates`][pythonnative.scheduler.batch_updates].
6. **Key-based reconciliation.** Children can be assigned stable
   `key` values to preserve identity across re-renders, which is
   critical for lists and dynamic content.
7. **Error boundaries.**
   [`ErrorBoundary`][pythonnative.ErrorBoundary] catches render
   errors in child subtrees and displays fallback UI, preventing a
   single component failure from crashing the entire page.
8. **Async components and Suspense.** A component body may be an
   `async def`. The reconciler drives it synchronously as far as it
   can (awaits on already-resolved data complete inline); if it
   blocks on pending work the render *suspends* and the nearest
   [`Suspense`][pythonnative.Suspense] boundary shows its fallback
   until the awaited work finishes.
   [`use_resource`][pythonnative.use_resource] starts fetches during
   render, and [`lazy`][pythonnative.lazy] code-splits components
   behind the same mechanism.
9. **Native rendering core.** Each commit's op list is serialized
   and applied by native **component managers**: a Swift
   `PNComponentManager` and a Kotlin `ComponentManager` per element
   type create views, apply props, position children, and report
   intrinsic sizes. Device APIs are **native modules** (Swift and
   Kotlin classes registered by name) reached through the same
   bridge. See [The native bridge](bridge.md).
10. **Thin native bootstrap.** The host app remains native (Android
   `Activity` or iOS `UIViewController`). It boots CPython, calls
   `pythonnative.bootstrap.start()`, and asks the `Host` module to
   create a screen for your root component; the reconciler drives the
   UI from there.
11. **`App` entry point.** The user's app module (`app/main.py`)
    defines a top-level component named `App`. Native templates
    import that module by path (`"app.main"`) and look up its `App`
    attribute, so users never write a separate registration step.
    Components with other names can still be loaded by passing an
    explicit dotted path like `"app.main.RootScreen"` to the
    template.

## Concurrency model

PythonNative is **async-first**: one `asyncio` event loop hosts every
coroutine in the framework (async component bodies, effects,
resources, native modules, animations, timers), and that loop lives
**on the platform's main thread**.

Because UIKit and the Android view system own the main thread's run
loop, the framework loop can't call `run_forever` and block. It runs
as a *guest* instead: whenever async work is scheduled, the runtime
asks the platform to pump the loop on the next main-queue turn
(the bridge's `pump` callback on iOS and Android, the Tk poll loop in
`pn preview`). One pump runs every ready callback and due timer,
then hands control back to the platform.

The payoff is that coroutines and rendering interleave on one thread:

- Async code can call state setters, read hook values, and (through
  the commit) touch native views without cross-thread marshaling.
- There are no locks and no thread-affinity bugs; "which thread am I
  on" stops being a question.
- Hook state is carried in `contextvars`, so a component that awaits
  in the middle of its body still resolves its hooks against the
  right instance when it resumes.

Synchronous scripts and tests drive the loop explicitly with
[`run_blocking`][pythonnative.runtime.run_blocking] and
[`drain`][pythonnative.runtime.drain]; async tests just `await`,
since [`get_loop`][pythonnative.runtime.get_loop] adopts an
already-running loop.

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
   flushes them all in a single `apply_mutations` transaction, which
   on device is one JSON payload handed to native. Event callbacks
   are routed to the Python-side
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
        pn.Button("+", on_press=lambda: set_count(count + 1)),
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
  with [`Context.Provider`][pythonnative.hooks.Context.Provider] and
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
- **Android**: every container is a `PNFrameLayout`; computed frames
  (in dp) are applied by the Kotlin manager through `MarginLayoutParams`.
- **iOS**: every container is a `PNContainerView`; computed frames (in
  points) are applied by the Swift manager through `bounds` and `center`.
- **Intrinsic content size**: leaf managers (`Text`, `Button`, `Image`,
  `TextInput`, ...) implement `measure` so the engine can ask them how
  big they want to be when no explicit size is set. The call is
  synchronous across the bridge.

See the [Layout engine](layout.md) concept page for a full walkthrough.

## Native views and the bridge

The reconciler talks to a
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry],
which owns the tag table and applies each commit's mutation list. On
device that is the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
in `pythonnative.native_views.bridge_backend`: it encodes the batch as
JSON and makes one call into native (`pn_bridge_apply` on iOS through
`ctypes`, `PNBridge.apply` on Android through Chaquopy). Native decodes
the transaction and dispatches each op to the component manager
registered for the element type.

Everything else crosses the same boundary:

- `measure(tag, w, h)` asks a manager for an intrinsic size, synchronously.
- `command(tag, name, args)` runs an imperative action (`focus`,
  `scroll_to_offset`, ...).
- `animate(tag, request)` starts, sets, or cancels a natively driven
  `Animated` value.
- `call(module, method, args)` invokes a native module method.

Native reaches back through a single callback for view events, module
results and events, screen lifecycle, animation completion, and loop
pumps. Events are keyed by tag: managers wire their platform listeners
once at view creation and emit `(tag, name, args)`; the
[`EventRegistry`][pythonnative.events.EventRegistry] resolves the
current Python callback. Gestures
([`pythonnative.gestures`](../api/gestures.md)) are recognized natively
and ride the same channel.

Off device the registry dispatches to Python
[`ViewHandler`][pythonnative.native_views.base.ViewHandler] objects
instead: Tkinter handlers for `pn preview` and an in-memory fake for
tests. The protocol is identical, so the reconciler never knows which
backend it is driving.

See [Native views](native-views.md) for the manager hooks and
[The native bridge](bridge.md) for the wire format.

## Comparisons

!!! note "Versus React Native"
    React Native's Fabric renderer and TurboModules have direct
    equivalents here: one serialized transaction per commit applied by
    native component managers, and named native modules with sync and
    async calls. The differences are the language (Python instead of
    JavaScript, no JSI), the layout engine (a Python Yoga port, so
    layout is identical on both platforms), and the async model (one
    asyncio loop on the main thread instead of a separate JS thread).

!!! note "Versus NativeScript"
    NativeScript exposes every platform API to JavaScript directly.
    PythonNative deliberately keeps platform code in Swift and Kotlin
    behind a small protocol, and adds a declarative reconciler layer and
    React-like hooks that NativeScript does not have by default.

See [Mental model](mental-model.md) for a wider comparison table.

## iOS flow

- The iOS template (Swift, CPython embedded through the C API) boots
  Python and calls `pythonnative.bootstrap.start()`, which loads the
  `PythonNativeKit` C entry points through `ctypes` and checks the
  protocol version.
- `PNViewController` asks Python (through the `Host` module callback)
  to create a screen for the root component and attaches the root view.
- Commits arrive as transactions; Swift component managers create and
  update UIKit views. Events, module results, and lifecycle flow back
  through the bridge callback on the main thread.

## Android flow

- The Android template (Kotlin plus Chaquopy) initializes Python in
  `MainActivity` and calls `pythonnative.bootstrap.start()`, which
  resolves `com.pythonnative.runtime.PNBridge` (the only Java class
  Python touches) and installs the Python callback.
- `PNScreenFragment` asks Python to create a screen and attaches the
  root view to the fragment container.
- Commits arrive as transactions; Kotlin component managers create and
  update Android views. The `pythonnative` Gradle module has no
  Chaquopy dependency, so it is unit-tested with plain JUnit.

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

Device APIs are native modules: Swift and Kotlin classes registered by
name, called from thin Python facades through the bridge, with Python
fallbacks for the desktop and tests. Built-ins include:

- [`Camera`][pythonnative.native_modules.camera.Camera]: photo
  capture and gallery picker.
- [`Location`][pythonnative.native_modules.location.Location]: GPS
  and location services.
- [`FileSystem`][pythonnative.native_modules.file_system.FileSystem]:
  app-scoped file I/O.
- [`Notifications`][pythonnative.native_modules.notifications.Notifications]:
  local notifications.

Packages can ship their own modules (and component managers) as native
plugins that `pn build` compiles into the app. See the
[Native modules guide](../guides/native-modules.md).

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
- The outermost `Stack.Navigator` delegates `push`, `pop`, `replace`,
  and `reset` to the platform's native navigation controller
  (`UINavigationController` on iOS, the AndroidX Navigation Component
  on Android) through the
  [`HostNavigator`][pythonnative.navigation.HostNavigator] protocol.
  Nested navigators (tabs inside a stack, stacks inside tabs) stay in
  Python, keep their screens mounted, and reuse the existing
  reconciler.
- Each pushed native screen is a fresh
  [`ScreenHost`][pythonnative.hosts.base.ScreenHost] with its own
  reconciler. The host receives the *serialized*
  [`NavigationState`][pythonnative.navigation.NavigationState] as its
  launch argument, so the pushed screen's navigator boots with the
  full history and renders the right `Stack.Screen` on its first
  frame.
- Inside any screen, [`use_navigation`][pythonnative.use_navigation]
  returns a [`Navigation`][pythonnative.Navigation] handle and
  [`use_route`][pythonnative.use_route] returns the current
  [`Route`][pythonnative.navigation.Route]. Both are the same hooks
  regardless of whether the active navigator is native-backed or
  pure-Python.

See the [Navigation guide](../guides/navigation.md) for the full
walkthrough, including how `options={"title": ...}` flows into the
native navigation bar.

- iOS: one `PNViewController` class, many instances pushed on a
  `UINavigationController`.
- Android: single host `Activity` with a `NavHostFragment` and a
  stack of generic `PNScreenFragment`s driven by a navigation graph.

Both are driven by the `Host` native module (`push`, `pop`, `replace`,
`reset`, `set_options`), so the Python navigator has no platform
branches.

## Next steps

- Read the [Mental model](mental-model.md) for the high-level
  comparisons.
- Walk through the render loop in [Lifecycle](lifecycle.md).
- Dive into the flexbox engine in [Layout engine](layout.md).
- See the component managers up close in [Native views](native-views.md).
- Read the wire protocol in [The native bridge](bridge.md).
- Browse the API: [Package overview](../api/pythonnative.md).
