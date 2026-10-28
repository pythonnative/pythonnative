# Native views

The reconciler doesn't know what a `Text` or a `Button` is. It produces
a flat list of **mutation ops** (create, update, insert, destroy) that
reference views by integer **tag**, and hands the whole list to the process-wide **view backend** (from
[`get_backend`][pythonnative.native_views.get_backend]) in a single
`apply_mutations` call per commit.

On a device that backend is the
[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]:
it builds the wire commit once, serializes it once, and hands it to the
**renderer core** across the [native bridge](bridge.md) in one call. The
core validates and lays out the commit and queues a mount transaction,
which the platform's UI thread applies through a Swift or Kotlin
**component manager** per element type. The browser preview runs the
same core as WebAssembly in the page, which mounts DOM elements. In tests
[`FakeBackend`][pythonnative.testing.FakeBackend] commits to the host
build of the same core and records what a platform would mount. Python
never holds a native view object and never runs a Python "view handler";
production and tests both talk to a backend.

This page describes that boundary, walks through what a component
manager does, and covers the fake backend used by `pytest`.

## The commit protocol

Every commit is one transaction: an ordered list of ops from
`pythonnative.mutations`, which the core accepts or rejects as a whole.

| Op | Meaning |
|---|---|
| `CreateOp(tag, type_name, props)` | Create a native view for `tag`. Props are already *clean*: callables have been routed to the event registry. |
| `UpdateOp(tag, changed_props)` | Apply only the props that changed (`UNSET` removes a prop; `None` is explicit null). |
| `InsertOp(parent_tag, child_tag, index)` | Place the child at `index` (move-aware: an attached child is repositioned, not duplicated). |
| `DestroyOp(tag)` | Release the native view (detaching it from its parent) and drop the tag record. |

Geometry isn't an op: the core lays out each commit and sends frames to
the platform with the mount, and to Python for observed views.

Tags matter because the diff phase is pure: it runs before any native
view exists, so ops can't reference views directly. Tags also give the
core and the platform a stable identity for event routing and animation
bookkeeping, and the flat op list is what makes a single crossing per
commit possible. On the wire each op is a short JSON array
(`["c", tag, "Text", {...}]`); see [Commits](bridge.md#commits). The
platform receives the core's binary
[mount transaction](bridge.md#mount-transactions) instead, which leaves
out views the core flattened.

## Component managers

On device every element type is implemented by a Swift
`PNComponentManager` (in `PythonNativeKit`) and a Kotlin
`ComponentManager` (in the `pythonnative` Gradle module). One manager
instance serves every view of its type; per-view state lives on the
view. The hooks mirror the mount transaction:

| Hook | When it runs |
|---|---|
| `makeView` / `createView(tag, props)` | Once per mounted create. Builds the platform view and applies initial props. |
| `apply(props, initial)` | On create (full props) and on every update (changed keys only; removed props arrive as `null`). |
| `insertChild(parent, child, index)` | On insert, at the mounted index. Move-aware. |
| `removeChild(parent, child)` | When a child is detached. |
| `destroy(view)` | On delete. Unwires gestures and animations, then removes the view. |
| `setFrame(view, x, y, w, h)` | For each frame op, with the frame relative to the nearest mounted ancestor. Frames are points (iOS) or dp (Android). |
| `measure(view, maxW, maxH)` | On the UI thread, when the core needs the size of an `intrinsic` leaf; the view is a prototype configured with the leaf's props, and the result is cached. |
| `command(view, name, args)` | For imperative actions (`focus`, `scroll_to_offset`, ...), queued behind pending mounts. |

The core interprets flex, margin, and padding props with Yoga. Managers
apply visual props, apply the frames the core computed, and measure the
controls that only the platform can size. Animated values arrive as prop
writes from the core's animator on each display frame.

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

## The backend

The backend protocol is what the reconciler talks to: `apply_mutations`,
`resolve_view`, `command`, `measure_in_window`, and the animation hooks
(`install_animation_graph`, `set_animated_property`, `start_animation`,
`cancel_animation`). The implementation is chosen lazily by
[`get_backend`][pythonnative.native_views.get_backend]:

- On iOS and Android, a
  [`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
  forwards every commit, layout read, command, and animation request to
  the renderer core. Before its first commit it imports the
  `pythonnative.handlers` entry points so plugin component schemas are
  registered.
- In the browser preview (`pn preview`, with `PN_PLATFORM=web`), the
  same `BridgeBackend` commits through a
  [`WebTransport`][pythonnative.bridge.web.WebTransport] to the core
  running in the page, which mounts DOM elements. See the
  [Browser preview guide](../guides/browser-preview.md).
- Under `pytest`, a [`FakeBackend`][pythonnative.testing.FakeBackend] is
  installed with [`set_backend`][pythonnative.native_views.set_backend]
  (the shipped pytest plugin and
  [`render`][pythonnative.testing.render] do this for you), or passed to
  the `Reconciler` directly.
- Anywhere else, with no backend installed, `get_backend` raises
  instead of guessing.

Imperative access to a mounted view goes through the typed
[handle](../api/handles.md) the reconciler publishes on `ref.current`;
`ViewHandle.command` forwards to the backend's `command`.

The core validates an entire commit before applying it. A rejected
commit leaves the surface as it was. A transaction that fails to mount on
the UI thread fails the surface, and further incremental updates require a
reset and remount. See [Commits](bridge.md#commits) for the failure
contract.

## Layout and styling

Layout-related style keys are interpreted by the core's Yoga engine. The full
list (sizing, flex, position, margin, padding, gap, ...) is
documented in [Component properties](../api/component-properties.md).
The set of keys the layout engine consumes is exposed as
`pythonnative.style.LAYOUT_STYLE_KEYS`.

Managers only deal with **visual** properties: colors, fonts, borders,
corner radii, image scaling, and text content. After each commit the core
computes layout, sends frames to the platform with the mount, and returns
the changed frames of observed views to Python. Headless tests use the
same core.

On each platform that boils down to:

- **iOS**: every container is a `PNContainerView` (a plain `UIView`)
  with `translatesAutoresizingMaskIntoConstraints` on; `setFrame` sets
  `bounds.size` and `center` so transforms and scroll offsets survive.
  Control managers implement `measure` via `sizeThatFits`. Shared visual
  props are applied by `PNViewStyler`.
- **Android**: every container is a `PNFrameLayout`; `setFrame`
  converts dp to pixels and positions the view through
  `MarginLayoutParams`. Control managers implement `measure`
  with `View.measure(...)` and `MeasureSpec`. Shared visual props are
  applied by `ViewStyler`.

Yoga provides shared layout rules. Native font metrics and control sizes
can produce different intrinsic measurements on Android and iOS.

## Children

Children of a container element become subviews of the corresponding
native view, or of the nearest mounted ancestor when the container is
flattened. The reconciler determines insertion order (and reorders
on key change) and expresses it as `InsertOp` / `DestroyOp`; the core
translates that into mounted indices, and the manager performs the native
mutation (`insertSubview(_:at:)` on iOS, `addView(child, index)` on
Android). Inserts are move-aware, which is how keyed reorders avoid
recreating views.

## Testing without a device

The test suite never loads Swift or Kotlin. It uses
[`FakeBackend`][pythonnative.testing.FakeBackend], a `BridgeBackend`
that commits to the host build of the renderer core while keeping a tree
of [`FakeView`][pythonnative.testing.FakeView] objects for the logical
views, with the frames Yoga computed.
[`render`][pythonnative.testing.render] wires it up:

```python
from pythonnative.testing import render

result = render(MyComponent())
assert result.get_by_text("Hello")
assert result.backend.ops_of("create")  # every applied op is recorded
```

The fake raises on malformed transactions, including unknown tags and
double destroys, and the core rejects invalid props as it does on a
device, so tests expose invalid mutation sequences. Custom
components defined with `define_component` render into the fake like
any element; there is no separate Python stand-in to write. See the
[Testing guide](../guides/testing.md).

Underneath, a [`FakeTransport`][pythonnative.bridge.fake.FakeTransport]
plays the platform's UI thread: it decodes each mount transaction the
core produces and keeps the mounted view tree (`backend.native.views`,
flattened views excluded). Native decoders and managers have their own
XCTest and JUnit suites inside the native libraries.

## Custom widgets

Adding a widget means a Swift manager, a Kotlin manager, and a Python
definition; the [`pythonnative.sdk`](../api/sdk.md) module gives you a
type-checked entry point for the Python half:

1. Define a frozen [`Props`][pythonnative.sdk.Props] dataclass listing
   the widget's API surface.
2. Implement `PNComponentManager` / `ComponentManager` subclasses and
   register them under the element name from a `PNPlugin` entry.
3. Call [`define_component(name, props)`][pythonnative.sdk.define_component],
   which registers the props schema for the contract generator and the
   core's commit validation and returns the typed element factory.

After that the reconciler treats the new element like any other: it is
validated, laid out, committed, and refreshed exactly like a built-in.
Headless tests render it into the `FakeBackend`, and the browser
preview draws it as a labeled placeholder. `pn build` compiles the
plugin's native sources into the app and PyPI packages define their
components automatically through entry points. See the
[Custom native components guide](../guides/custom-native-components.md)
for the full walkthrough.

## Next steps

- The wire protocol: [The native bridge](bridge.md).
- Browse the API: [Native views](../api/native_views.md).
- Read the [Layout engine](layout.md) concept page to understand how
  frames are computed and which views are flattened.
- See how the reconciler drives the backend: [Reconciliation](reconciliation.md).
- Wrap a device API instead of a widget: [Native modules guide](../guides/native-modules.md).
