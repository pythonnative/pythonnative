# Desktop preview

`pn preview` renders your app in a native desktop window with **instant
Fast Refresh** on every save. It's the fastest way to build UI in
PythonNative: edit a component, hit save, and see the result in a second
(no simulator boot, no device deploy, no rebuild).

```bash
pn preview
```

The preview reuses the **same reconciler, hooks, navigation, async
runtime, and pure-Python flex layout engine** that run on device. Only
the leaf widgets differ: the desktop backend draws with
[Tkinter](https://docs.python.org/3/library/tkinter.html) instead of
UIKit / Android views. So behavior and layout match the device closely,
and your iteration loop collapses from minutes to seconds.

## Quick start

From a project directory (one created by `pn init`, with an `app/main.py`
that defines `App`):

```bash
pn preview
```

`pn preview` runs your real app code, so install your project's
dependencies in the same environment first: `pip install` whatever you
declared in `[requirements].packages` in `pythonnative.toml`. If an
import fails, the preview shows the traceback in the window instead of
crashing; install the missing package or fix the code and save to
recover.

This opens a phone-sized window, mounts your `App`, and starts watching
`app/` for changes. Edit any component and save: the window updates in
place while preserving component state (counters, text input, scroll
position, navigation stack).

```bash
pn preview                          # the project entry point (app/main.py → App)
pn preview app.screens.home         # a module whose App attribute to mount
pn preview app.main.DetailScreen    # a specific dotted component
pn preview --width 768 --height 1024  # tablet-sized window
pn preview --title "My App"
pn preview --no-hot-reload          # mount once, don't watch files
```

## Requirements

The preview uses Tkinter, Python's standard GUI toolkit, which ships
with most Python installations. If `pn preview` reports that Tkinter is
missing:

- **macOS** (Homebrew Python): `brew install python-tk`
- **Debian / Ubuntu**: `sudo apt-get install python3-tk`
- **Windows**: re-run the Python installer and enable the
  "tcl/tk and IDLE" optional feature.

No other dependencies are required; the desktop backend is pure Python.

## How it works

`pn preview` sets `PN_PLATFORM=desktop` and starts
`pythonnative.preview.run_preview`, which:

1. Opens a single Tk window with one *stage* frame.
2. Selects the Tkinter
   [native-view registry][pythonnative.native_views.get_registry], so
   every `pn.Text`, `pn.Button`, … maps to a Tk widget.
3. Mounts your `App` through a normal
   [`Reconciler`][pythonnative.reconciler.Reconciler] and pushes the
   window size in as the layout viewport.
4. Runs the Tk event loop on the main thread, polling ~60×/second to
   apply renders requested from the async runtime thread and to drain
   file-change reloads.
5. Watches `app/` with a
   [`FileWatcher`][pythonnative.hot_reload.FileWatcher] and Fast
   Refreshes on every save.

Layout is owned by the engine, not the widgets: the
[flex layout engine](../concepts/layout.md) computes an absolute frame
for every element, and the backend positions each Tk widget with that
frame. This is the same contract the iOS and Android backends follow, so
a column that lays out correctly on a phone lays out the same way in the
preview.

### Navigation

Root navigators (`create_stack_navigator`, tabs, drawer) drive a real
in-process stack of screen hosts in the preview, the same way they drive
`UINavigationController` / AndroidX Navigation on device. `navigate(...)`
pushes a new screen host (preserving the previous screen's state);
`go_back()` pops it. Each screen runs in its own reconciler host.

The Escape key acts as the system back action:
[`use_back_handler`][pythonnative.use_back_handler] subscribers on the
active screen get the first chance to consume it, and otherwise the
navigation stack pops, matching the Android hardware back button.

### Dev mode and the error overlay

The preview always runs with dev diagnostics on: unknown style keys
and duplicate list keys print `[PN] WARN` messages, hook-order
violations raise immediately, and uncaught errors from renders,
effects, and event handlers show a full-screen **RedBox** with the
traceback. Fix the code and save; a successful reload clears the
overlay. The same diagnostics run on device under `pn run` with hot
reload enabled.

## Fast Refresh

Saving a `.py` file under `app/` triggers a reload. The preview prefers
**Fast Refresh**: the changed modules are reloaded and the live VNode
tree's function references are swapped in place, so the next render
reuses existing hook state. Edits to a component body keep your
counters, form values, and scroll positions. When a clean swap isn't
possible (structural edits, a raised exception), the preview falls back
to a full remount so you're never stuck with a stale tree.

If your component raises at import time (a syntax error you're mid-fix
on), the preview shows the traceback as an overlay and recovers
automatically on your next successful save (no restart needed).

See the [Hot reload guide](hot-reload.md) for the underlying mechanics;
the desktop preview shares the same Fast Refresh engine.

## Branching on the platform

When the preview is running, [`Platform.OS`][pythonnative.Platform] is
`"desktop"`:

```python
import pythonnative as pn

pad = pn.Platform.select({"desktop": 12, "ios": 16, "android": 16, "default": 12})
```

Note that `Platform.select`'s `"native"` key matches iOS and Android
only; desktop is a development surface, so use an explicit `"desktop"`
key (or `"default"`) for it. You can also check
[`Platform.is_desktop`][pythonnative.Platform] or the
`pythonnative.utils.IS_DESKTOP` flag directly.

## What's faithful, and what's approximated

The preview is a **development tool**, optimized for fidelity of layout
and logic rather than pixel-perfect chrome.

Faithful:

- Flex layout, sizing, padding, spacing, absolute positioning.
- Component lifecycle, hooks, effects, context, error boundaries.
- Navigation (stack push/pop, tabs, drawer) and per-screen state.
- The async runtime, `use_query` / `use_mutation`, timers, and
  state-driven updates.
- Text wrapping and intrinsic sizing (measured with the same font the
  widget renders).

Approximated or omitted (Tkinter can't express these cheaply):

- Rounded corners, shadows, gradients, and per-widget opacity.
- Overflow **clipping**: a `ScrollView`'s content renders but isn't
  clipped to the viewport, and there's no interactive scrolling.
- Animations show their **end state** rather than smooth interpolation
  (translations are applied; scale/rotate/opacity are skipped).
- `Image` loads local PNG/GIF files; network URLs and JPEG fall back to
  a labeled placeholder. `WebView` shows a placeholder.

When the chrome matters, verify on device with `pn run`.

## When to use device builds instead

`pn preview` is for fast UI/logic iteration. Reach for `pn run` when you
need:

- Pixel-perfect native chrome and platform behaviors.
- Real device APIs (camera, location, notifications, biometrics, …).
- To test packaging, permissions, or store builds.

There's no desktop packaging target; ship to devices with
`pn run android` / `pn run ios`.

## Next steps

- Reference: [`pn` CLI](../api/cli.md).
- Mechanics shared with device hot reload: [Hot reload](hot-reload.md).
- How layout is computed: [Layout engine](../concepts/layout.md).
- Platform branching: [Platform & accessibility](platform-accessibility.md).
