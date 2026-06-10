# Native views

The reconciler doesn't know what a `Text` or a `Button` is. It produces
a flat list of **mutation ops** — create, update, insert, remove,
destroy, set-frame — that reference views by integer **tag**, and hands
the whole list to the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] in
a single
[`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations]
call per commit. The registry resolves each tag to a native view and
dispatches each op to the right
[`ViewHandler`][pythonnative.native_views.base.ViewHandler].

This page describes that boundary, walks through what a handler
actually does on each platform, and covers the fake backend used by
`pytest`.

## The commit protocol

Every commit is one transaction: an ordered list of ops from
`pythonnative.mutations`, applied atomically from the perspective of
the render loop.

| Op | Meaning |
|---|---|
| `CreateOp(tag, type_name, props)` | Create a native view for `tag`. Props are already *clean* — callables have been routed to the event registry. |
| `UpdateOp(tag, changed_props)` | Apply only the props that changed (removed props arrive as `None`). |
| `InsertOp(parent_tag, child_tag, index)` | Place the child at `index` (move-aware: an attached child is repositioned, not duplicated). |
| `RemoveOp(parent_tag, child_tag)` | Detach the child without destroying it. |
| `DestroyOp(tag)` | Release the native view and drop the tag record. |
| `SetFrameOp(tag, x, y, w, h)` | Apply a layout frame. Only emitted for frames that actually changed. |

Tags matter because the diff phase is pure: it runs before any native
view exists, so ops can't reference views directly. Tags also give the
native side a stable identity for event routing and animation
bookkeeping, and a flat op list is trivially serializable — the door
stays open for applying mutations through a single JNI/ObjC crossing.

## The handler protocol

Every native widget is implemented as a class that fulfils the
[`ViewHandler`][pythonnative.native_views.base.ViewHandler] interface.
The registry resolves tags to views; handlers receive native view
objects:

| Method | When it's called |
|---|---|
| `create(tag, props)` | Once, when the element first mounts. Returns a native view object. |
| `update(view, changed_props)` | On commits where the element survived the diff with changed props. |
| `insert_child(parent, child, index)` | When a child appears in (or moves to) a slot. |
| `remove_child(parent, child)` | When a child is detached. |
| `destroy(view)` | When the view is released — unhook listeners, cancel image loads, etc. |
| `set_frame(view, x, y, width, height)` | When the layout engine computed a different frame than last pass. |
| `measure_intrinsic(view, max_w, max_h)` | Called by the layout engine on leaf widgets that need a content-derived size. |

Handlers receive the `tag` at creation so they can wire their platform
listeners **once**, dispatching back through
[`dispatch_event`][pythonnative.events.dispatch_event]:

```python
from pythonnative.events import dispatch_event, event_names


class MyHandler(ViewHandler):
    def create(self, tag, props):
        v = NativeWidget()
        if "on_change" in event_names(props):
            v.addChangeListener(lambda value: dispatch_event(tag, "on_change", value))
        self.update(v, props)
        return v

    def update(self, view, changed):
        if "text" in changed:
            view.setText(changed["text"] or "")

    def set_frame(self, view, x, y, width, height):
        view.setFrame(x, y, width, height)

    def measure_intrinsic(self, view, max_w, max_h):
        size = view.measure(max_w, max_h)
        return (size.width, size.height)
```

Handlers do **not** read flex / margin / padding props themselves —
those are interpreted by `pythonnative.layout` and turned into
`SetFrameOp`s. A handler only needs to apply the frame it is given.

## Events never cross the bridge

Callable props (`on_press`, `on_change`, …) are stripped before a
`CreateOp`/`UpdateOp` is built and registered in the process-wide
[`EventRegistry`][pythonnative.events.EventRegistry] keyed by
`(tag, name)`. The native payload carries only `_pn_events` — a
`frozenset` of the event names present — so handlers can wire expensive
listeners (scroll delegates, gesture recognizers) conditionally.

The payoff: a re-render that only changes a callback's identity (every
lambda is a fresh object!) costs **zero** native calls. The registry
swaps the Python-side callback and the already-wired native listener
picks it up on the next dispatch.

## The registry

The [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
maps element type strings to handler *instances* and owns the
tag-to-view table. The registry is selected lazily by platform:

- On Android, `pythonnative.native_views.android.register_handlers`
  populates the registry with Chaquopy-backed handlers.
- On iOS, `pythonnative.native_views.ios.register_handlers` does the
  same with handlers built on rubicon-objc plus raw `libobjc` bindings
  for delegate-heavy widgets.
- On the desktop (`pn preview`, with `PN_PLATFORM=desktop`),
  `pythonnative.native_views.desktop.register_handlers` populates the
  registry with Tkinter-backed handlers. See the
  [Desktop preview guide](../guides/desktop-preview.md).
- Off-device under `pytest`, the backend is replaced with a fake via
  [`set_registry`][pythonnative.native_views.set_registry] (or by
  constructing the `Reconciler` with the fake directly).

Per-op failures inside `apply_mutations` are isolated: a bad prop on
one view logs a tripwire instead of desyncing the whole transaction.

## Layout and styling

Layout-related style keys are interpreted by the central
`pythonnative.layout` engine, *not* by the platform handlers. The
full list (sizing, flex, position, margin, padding, spacing, …) is
documented in [Component properties](../api/component-properties.md).
The set of keys the layout engine consumes is exposed as
`pythonnative.layout.LAYOUT_STYLE_KEYS`.

Handlers only deal with **visual** properties — colours, fonts,
borders, corner radii, image scaling, text content. After each commit
the reconciler runs the layout pass and emits `SetFrameOp`s for every
node whose frame changed.

On each platform that boils down to:

- **iOS**: every container is a plain `UIView` with
  `translatesAutoresizingMaskIntoConstraints = NO`; `set_frame`
  assigns `view.frame = CGRect(x, y, w, h)`. Leaf widgets implement
  `measure_intrinsic` via `sizeThatFits_`. Visual props
  (`background_color`, `corner_radius`, `font_*`, `color`, `text_align`,
  …) are applied directly through UIKit setters.
- **Android**: every container is a plain `FrameLayout`; `set_frame`
  builds a `MarginLayoutParams` and sets `view.x` / `view.y`. Padding
  in `dp` is computed from `Resources.getDisplayMetrics().density`. Leaf
  widgets implement `measure_intrinsic` with `View.measure(...)` plus
  `MeasureSpec`. Visual props are applied through `setBackgroundColor`,
  `setTextColor`, `setTextSize`, etc.

Because layout is centralised, the same `style` dict produces the same
geometry on Android and iOS — there is no "container-only" vs
"child-only" trap to fall into.

## Children

Children of a container element become subviews of the corresponding
native view. The reconciler determines insertion order (and reorders
on key change) and expresses it as `InsertOp` / `RemoveOp` pairs; the
handler performs the actual native mutations:

- iOS containers use `insertSubview_atIndex_` on a plain `UIView`.
- Android containers use `addView(child, index)` /
  `removeView(child)` on a `FrameLayout`.

`InsertOp` is move-aware: handlers reposition a child that is already
attached rather than duplicating it, which is how keyed reorders avoid
recreating views.

## Testing without a device

Production handlers require Chaquopy (Android) or rubicon-objc (iOS),
neither of which is available on a developer laptop. The test suite
sidesteps this with `tests/fake_backend.py` — a shared in-memory
backend implementing the same mutation protocol while keeping a real
tree of `FakeView` objects:

```python
from fake_backend import FakeBackend
from pythonnative.reconciler import Reconciler

backend = FakeBackend()
rec = Reconciler(backend)
rec.mount(MyComponent())

root = backend.views[rec.root_tag()]
assert root.find_first("Text").props["text"] == "Hello"
assert backend.ops_of("create")  # every applied op is recorded
```

Unlike the production registry, the fake **raises** on malformed
transactions (unknown tags, double-destroys), so reconciler bugs fail
tests loudly instead of being swallowed. See the
[Testing guide](../guides/testing.md).

## Custom widgets

Adding a widget is a three-step process, and the
[`pythonnative.sdk`](../api/sdk.md) module gives you a ready-made,
type-checked entry point for each step:

1. Define a frozen [`Props`][pythonnative.sdk._components.Props]
   dataclass listing the widget's API surface.
2. Implement a [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
   subclass per platform and decorate it with
   [`@native_component`][pythonnative.sdk._components.native_component].
3. Hand callers an
   [`element_factory`][pythonnative.sdk._components.element_factory]
   that validates kwargs against the dataclass and returns regular
   `Element` instances.

```python
from dataclasses import dataclass
from typing import Optional
import pythonnative as pn
from pythonnative.sdk import Props, ViewHandler, element_factory, native_component


@dataclass(frozen=True)
class RatingProps(Props):
    value: float = 0.0
    on_change: Optional[callable] = None
    style: Optional[pn.StyleProp] = None


@native_component("Rating", props=RatingProps, platforms=("ios",))
class IOSRatingHandler(ViewHandler):
    def create(self, tag, props):
        ...  # build a UIView wrapping star UIImageViews
    def update(self, view, changed):
        ...


Rating = element_factory("Rating")
```

After registration the reconciler treats `Rating` like any other
element. PyPI plugins can register their handlers automatically via
the `pythonnative.handlers` entry-point group (see
[`ENTRY_POINT_GROUP`][pythonnative.sdk._components.ENTRY_POINT_GROUP]),
so users only have to `pip install` your package.

For the full walkthrough — typed props, iOS handler, Android handler,
distribution as a plugin, unit-testing — see the
[Custom native components guide](../guides/custom-native-components.md).

## Next steps

- Browse the API: [Native views](../api/native_views.md).
- Read the [Layout engine](layout.md) concept page to understand how
  `SetFrameOp`s are produced.
- See how the reconciler drives handlers: [Reconciliation](reconciliation.md).
- Wrap a device API instead of a widget: [Native modules guide](../guides/native-modules.md).
