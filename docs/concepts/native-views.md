# Native views

The reconciler doesn't know what a `Text` or a `Button` is. It produces
a flat list of **mutation ops** (create, update, insert, remove,
destroy, set-frame) that reference views by integer **tag**, and hands
the whole list to the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] in
a single
[`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations]
call per commit.

On a device that registry is the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]:
it serializes the batch and sends it across the
[native bridge](bridge.md) in one call, where a Swift or Kotlin
**component manager** per element type creates and updates the real
views. Off device the registry dispatches to Python
[`ViewHandler`][pythonnative.native_views.base.ViewHandler] objects
(Tkinter for `pn preview`, an in-memory fake for tests).

This page describes that boundary, walks through what a component
manager does, and covers the fake backend used by `pytest`.

## The commit protocol

Every commit is one transaction: an ordered list of ops from
`pythonnative.mutations`, applied atomically from the perspective of
the render loop.

| Op | Meaning |
|---|---|
| `CreateOp(tag, type_name, props)` | Create a native view for `tag`. Props are already *clean*: callables have been routed to the event registry. |
| `UpdateOp(tag, changed_props)` | Apply only the props that changed (removed props arrive as `None`). |
| `InsertOp(parent_tag, child_tag, index)` | Place the child at `index` (move-aware: an attached child is repositioned, not duplicated). |
| `DestroyOp(tag)` | Release the native view (detaching it from its parent) and drop the tag record. |
| `SetFrameOp(tag, x, y, w, h)` | Apply a layout frame. Only emitted for frames that actually changed. |

Tags matter because the diff phase is pure: it runs before any native
view exists, so ops can't reference views directly. Tags also give the
native side a stable identity for event routing and animation
bookkeeping, and the flat op list is what makes a single crossing per
commit possible. On the wire each op is a short JSON array
(`["c", tag, "Text", {...}]`); see [Transactions](bridge.md#transactions).

## Component managers

On device every element type is implemented by a Swift
`PNComponentManager` (in `PythonNativeKit`) and a Kotlin
`ComponentManager` (in the `pythonnative` Gradle module). One manager
instance serves every view of its type; per-view state lives on the
view. The hooks mirror the op list:

| Hook | When it runs |
|---|---|
| `makeView` / `createView(tag, props)` | Once per `c` op. Builds the platform view and applies initial props. |
| `apply(props, initial)` | On create (full props) and on every `u` op (changed keys only; removed props arrive as `null`). |
| `insertChild(parent, child, index)` | On `i`. Move-aware and clamped. |
| `removeChild(parent, child)` | When a child is detached. |
| `destroy(view)` | On `d`. Unwires gestures and animations, then removes the view. |
| `setFrame(view, x, y, w, h)` | On `f`. Frames are points (iOS) or dp (Android). |
| `measure(view, maxW, maxH)` | Synchronously, when the layout engine needs a content-derived size. |
| `command(view, name, args)` | For imperative actions (`focus`, `scroll_to_offset`, ...). |
| `startAnimation` / `cancelAnimation` | For natively driven `Animated` values. |

Managers do **not** read flex, margin, or padding props; those are
interpreted by `pythonnative.layout` and turned into `f` ops. A
manager only applies the frame it is given.

Managers fire events by tag through `PNEvents.emit(view, "on_change",
[value])` (Swift) or `PNEvents.fire(view, "on_change", value)`
(Kotlin). The bridge routes them to
[`dispatch_event`][pythonnative.events.dispatch_event].

## Events never cross the bridge as callables

Callable props (`on_press`, `on_change`, ...) are stripped before a
`CreateOp`/`UpdateOp` is built and registered in the process-wide
[`EventRegistry`][pythonnative.events.EventRegistry] keyed by
`(tag, name)`. The native payload carries only `_pn_events` (the list
of event names present) so managers can wire expensive listeners
(scroll delegates, gesture recognizers) conditionally.

The payoff: a re-render that only changes a callback's identity (every
lambda is a fresh object) costs **zero** native calls. The registry
swaps the Python-side callback and the already-wired native listener
picks it up on the next dispatch.

## The registry

The [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
protocol is what the reconciler talks to. The implementation is chosen
lazily by [`get_registry`][pythonnative.native_views.get_registry]:

- On iOS and Android, a
  [`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
  forwards every transaction, measurement, command, and animation
  request to native.
- On the desktop (`pn preview`, with `PN_PLATFORM=desktop`), a
  handler-based registry populated by
  `pythonnative.native_views.desktop.register_handlers` renders with
  Tkinter. See the [Desktop preview guide](../guides/desktop-preview.md).
- Under `pytest`, the backend is replaced with a fake via
  [`set_registry`][pythonnative.native_views.set_registry] (or by
  constructing the `Reconciler` with the fake directly).

Per-op failures are isolated on both sides: a bad prop on one view
logs a tripwire (Python) or a rate-limited native log instead of
desyncing the whole transaction.

## Layout and styling

Layout-related style keys are interpreted by the central
`pythonnative.layout` engine, *not* by the platform managers. The full
list (sizing, flex, position, margin, padding, spacing, ...) is
documented in [Component properties](../api/component-properties.md).
The set of keys the layout engine consumes is exposed as
`pythonnative.layout.LAYOUT_STYLE_KEYS`.

Managers only deal with **visual** properties: colors, fonts, borders,
corner radii, image scaling, text content. After each commit the
reconciler runs the layout pass and emits `SetFrameOp`s for every node
whose frame changed.

On each platform that boils down to:

- **iOS**: every container is a `PNContainerView` (a plain `UIView`)
  with `translatesAutoresizingMaskIntoConstraints` on; `setFrame` sets
  `bounds.size` and `center` so transforms and scroll offsets survive.
  Leaf managers implement `measure` via `sizeThatFits`. Shared visual
  props are applied by `PNViewStyler`.
- **Android**: every container is a `PNFrameLayout`; `setFrame`
  converts dp to pixels and positions the view through
  `MarginLayoutParams`. Leaf managers implement `measure`
  with `View.measure(...)` and `MeasureSpec`. Shared visual props are
  applied by `ViewStyler`.

Because layout is centralized, the same `style` dict produces the same
geometry on Android and iOS.

## Children

Children of a container element become subviews of the corresponding
native view. The reconciler determines insertion order (and reorders
on key change) and expresses it as `InsertOp` / `DestroyOp`; the
manager performs the native mutation (`insertSubview(_:at:)` on iOS,
`addView(child, index)` on Android). `InsertOp` is move-aware, which
is how keyed reorders avoid recreating views.

## Testing without a device

The test suite never loads Swift or Kotlin. It uses
[`FakeBackend`][pythonnative.testing.FakeBackend], an in-memory
backend implementing the same mutation protocol while keeping a real
tree of [`FakeView`][pythonnative.testing.FakeView] objects.
[`render`][pythonnative.testing.render] wires it up:

```python
from pythonnative.testing import render

result = render(MyComponent())
assert result.get_by_text("Hello")
assert result.backend.ops_of("create")  # every applied op is recorded
```

Unlike the production backend, the fake **raises** on malformed
transactions (unknown tags, double-destroys), so reconciler bugs fail
tests loudly instead of being swallowed. See the
[Testing guide](../guides/testing.md).

The bridge itself is tested with
[`FakeTransport`][pythonnative.bridge.fake.FakeTransport], which
decodes the JSON transactions the `BridgeBackend` produces and keeps a
view tree the way native would. Native decoders and managers have
their own XCTest and JUnit suites inside the templates.

## Custom widgets

Adding a widget means a Swift manager, a Kotlin manager, and a Python
registration; the [`pythonnative.sdk`](../api/sdk.md) module gives you
a type-checked entry point for the Python half:

1. Define a frozen [`Props`][pythonnative.sdk._components.Props]
   dataclass listing the widget's API surface.
2. Implement `PNComponentManager` / `ComponentManager` subclasses and
   register them under the element name from a `PNPlugin` entry.
3. Call [`register_component`][pythonnative.sdk._components.register_component]
   (or decorate a desktop
   [`ViewHandler`][pythonnative.native_views.base.ViewHandler] with
   [`@native_component`][pythonnative.sdk._components.native_component])
   and hand callers an
   [`element_factory`][pythonnative.sdk._components.element_factory].

After registration the reconciler treats the new element like any
other. `pn build` compiles the plugin's native sources into the app and
PyPI packages register automatically through entry points. See the
[Custom native components guide](../guides/custom-native-components.md)
for the full walkthrough.

## Next steps

- The wire protocol: [The native bridge](bridge.md).
- Browse the API: [Native views](../api/native_views.md).
- Read the [Layout engine](layout.md) concept page to understand how
  `SetFrameOp`s are produced.
- See how the reconciler drives the backend: [Reconciliation](reconciliation.md).
- Wrap a device API instead of a widget: [Native modules guide](../guides/native-modules.md).
