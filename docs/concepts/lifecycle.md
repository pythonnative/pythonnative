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
re-run, not the whole app. The full tree is rebuilt from the root only
on initial mount, navigation, and hot reload. Sibling and ancestor
components keep their existing native views and hook state untouched.

The phases:

1. **Render**. The affected `@component` function(s) run (for a state
   change, just the component whose setter fired). Hooks register state,
   queue effects, and capture closures. No native widgets change yet,
   so this phase is cheap and pure (modulo `use_state` updates).
2. **Commit**. The
   [`Reconciler`][pythonnative.reconciler.Reconciler] diffs the
   re-rendered subtree against the previous one and applies the
   smallest set of native mutations through the registered
   [`ViewHandler`][pythonnative.native_views.base.ViewHandler]s.
3. **Effects**. Cleanup callbacks from the *previous* render run
   first; new [`use_effect`][pythonnative.use_effect] callbacks run
   after, in depth-first order so children commit before parents.
4. **Drain**. If any effect set state, another render pass is queued
   immediately. The screen host caps the loop to prevent runaway
   re-renders.

```text
[render] -> [commit] -> [effects] -> drain? -> [render] ...
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

!!! warning "Effects are not awaitable"
    Returning an awaitable from an effect doesn't await it. Schedule
    async work explicitly (e.g., via `asyncio.create_task`) and store
    the resulting cancellation handle in the effect's cleanup
    closure.

## Mount, update, unmount

For a class-component-style mental model:

| Class lifecycle | PythonNative equivalent |
|---|---|
| `componentDidMount` | `use_effect(fn, deps=[])` |
| `componentDidUpdate` | `use_effect(fn, deps=[a, b])` |
| `componentWillUnmount` | the cleanup function returned from `use_effect` |
| `getDerivedStateFromProps` | a plain expression at the top of the component |
| `getSnapshotBeforeUpdate` | not exposed; handle in commit-time platform APIs if needed |

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
  is re-armed.
- **Pause / `viewWillDisappear`**: focus cleanups run.
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

    def start_clock():
        async def tick():
            while True:
                set_now(_format_now())
                await asyncio.sleep(1)

        task = asyncio.create_task(tick())
        return task.cancel  # cleanup

    pn.use_focus_effect(start_clock, deps=[])
    return pn.Text(now, style={"font_size": 48})
```

- The clock starts only while `LiveClock` is on the focused screen.
- Navigating away cancels the task because the focus cleanup runs
  immediately.
- Returning to the screen restarts a fresh task; the user never sees
  the previous, stale state because `use_state` resets on remount.

## Next steps

- Build a feature that uses focus-aware effects: [Native modules guide](../guides/native-modules.md).
- See how the reconciler chooses what to mount: [Reconciliation](reconciliation.md).
- Wrap risky subtrees: [Error boundaries guide](../guides/error-boundaries.md).
