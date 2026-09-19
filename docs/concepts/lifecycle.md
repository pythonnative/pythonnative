# Lifecycle

PythonNative drives the UI through a small, predictable cycle:
**render**, **commit**, **effects**, and an optional **drain**. This
page walks through what happens at each step, how navigation changes
fold into it, and where you can hook in.

## A single render pass

A render pass is triggered by:

- Initial mount via [`create_screen`][pythonnative.create_screen].
- A setter from [`use_state`][pythonnative.use_state] or a `dispatch`
  from [`use_reducer`][pythonnative.use_reducer].
- A navigation event (`navigate`, `go_back`, `replace`).
- A hot-reload module swap (see [Hot reload guide](../guides/hot-reload.md)).

A `use_state` / `use_reducer` setter re-renders **locally**: only the
component that owns the changed state (and the subtree it returns) is
re-run. Setters never render inline: every setter call made during one
callback, effect, or task step lands in the same flush, scheduled on the
application loop (automatic batching), on every host including headless
tests. Sibling and ancestor components retain their native views and hook
state unless their own inputs or context change. Screens and mounted list
rows belong to the same logical tree. Navigation updates that tree, and
Fast Refresh preserves compatible component instances.

The phases:

1. **Render**. The affected `@component` function(s) run (for a state
   change, just the component whose setter fired). Hooks register state,
   queue effects, and capture closures. No native widgets change yet,
   so this phase is cheap and pure (modulo `use_state` updates).
2. **Commit**. The
   [`Reconciler`][pythonnative.reconciler.Reconciler] diffs the
   re-rendered subtree against the previous one, hands the smallest
   set of native mutations to the view backend in one
   `apply_mutations` call (the Swift and Kotlin component managers
   apply them; see [Native views](native-views.md)), and runs the
   layout pass.
3. **Layout effects**.
   [`use_layout_effect`][pythonnative.use_layout_effect] callbacks run
   on the application thread after committed geometry is available,
   before passive effects. They can inspect frames or issue view commands;
   the platform UI thread owns presentation.
4. **Passive effects**. Cleanup callbacks from the *previous* render
   run first; new [`use_effect`][pythonnative.use_effect] callbacks
   run after, in depth-first order so children run before parents. An
   exception raised by a layout or passive effect is routed to the
   nearest [`ErrorBoundary`][pythonnative.ErrorBoundary] exactly like a
   render error; it never fails the native surface.
5. **Drain**. If any effect set state, another render pass is queued
   immediately. A flush that keeps re-scheduling itself more than
   fifty times raises `RuntimeError("Too many re-renders")` from the
   component that keeps dirtying itself, routed through the nearest
   `ErrorBoundary` (or the RedBox in dev mode).

```text
[render] -> [commit + layout] -> [layout effects] -> [passive effects] -> drain? -> [render] ...
```

## Effects vs focus effects

[`use_effect(fn, deps)`][pythonnative.use_effect] fires after each
commit when its `deps` list changes (or every commit if `deps` is
omitted). This is right for subscriptions, timers, and synchronization
with mutable globals.

[`use_focus_effect(fn, deps)`][pythonnative.use_focus_effect] is
identical in shape but only fires when the screen is focused (and its
cleanup runs when the screen is blurred). Use it for camera streams,
GPS subscriptions, and anything that should be released as soon as the
user navigates away.

!!! tip "Effects can be coroutines"
    Both hooks accept an `async def` callback. The coroutine runs as a
    task on the framework loop and is cancelled automatically when the
    effect re-runs, the screen blurs (for focus effects), or the
    component unmounts; no manual task bookkeeping is needed. See the
    [Async + data guide](../guides/async.md).

## Mount, update, unmount

For a class-component-style mental model:

| Class lifecycle | PythonNative equivalent |
|---|---|
| `componentDidMount` | `use_effect(fn, deps=[])` |
| `componentDidUpdate` | `use_effect(fn, deps=[a, b])` |
| `componentWillUnmount` | the cleanup function returned from `use_effect` |
| `getDerivedStateFromProps` | a plain expression at the top of the component |
| `getSnapshotBeforeUpdate` | `use_layout_effect` (inspect committed geometry before passive effects) |

## Navigation lifecycle

When a screen mounts inside a navigator (stack, tab, or drawer):

1. The navigator builds the screen's element tree.
2. The reconciler commits it (phase 2 above).
3. Effects run; `use_focus_effect` callbacks fire because the screen
   is focused.

When the user navigates away:

1. `use_focus_effect` cleanups run.
2. If the screen is unmounted (e.g., popped from a stack), each
   `use_effect` cleanup runs as well.
3. If the screen is kept alive (a previous tab, for example), only
   the focus cleanup runs; effect state is preserved.

## App lifecycle (Android / iOS)

The screen host forwards the platform's app-level lifecycle to navigators
and effects:

- **Resume / `viewWillAppear`**: the active screen's `use_focus_effect`
  is re-armed, and the event carries fresh viewport metrics.
- **Pause / `viewWillDisappear`**: focus cleanups run.
- **Save / restore instance state**: acknowledged without calling into
  Python. The host caches navigation restoration state as Python
  publishes it, so platform state-saving never waits on the
  application thread.
- **Destroy / `dealloc`**: every effect cleanup runs and the
  reconciler tears down its native tree.

You can opt into these directly in app code by writing an effect that
checks the navigation handle's `is_focused()` state, but most apps
should reach for the [`use_focus_effect`][pythonnative.use_focus_effect]
hook instead.

## Putting it together: a subscription

```python
import asyncio
import pythonnative as pn

@pn.component
def LiveClock():
    now, set_now = pn.use_state("--:--")

    async def tick():
        while True:
            set_now(_format_now())
            await asyncio.sleep(1)

    pn.use_focus_effect(tick, deps=[])
    return pn.Text(now, style={"font_size": 48})
```

- The clock starts only while `LiveClock` is on the focused screen.
- Navigating away cancels the coroutine because the focus cleanup
  runs immediately.
- Returning to the screen restarts a fresh task; the user never sees
  the previous, stale state because `use_state` resets on remount.

## Next steps

- Build a feature that uses focus-aware effects: [Native modules guide](../guides/native-modules.md).
- See how the reconciler chooses what to mount: [Reconciliation](reconciliation.md).
- Wrap risky subtrees: [Error boundaries guide](../guides/error-boundaries.md).
