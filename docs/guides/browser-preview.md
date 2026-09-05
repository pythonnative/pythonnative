# Browser preview

`pn preview` renders your app in a browser tab, inside a phone frame,
with **Fast Refresh on every save**. It's the fastest way to build UI in
PythonNative: edit a component, save, and see the result in well under a
second, with no simulator boot, no device deploy, and no native build.

```bash
pn preview
```

The preview isn't a second rendering backend. The page is treated as a
**native runtime**: it receives the same JSON transactions the Swift and
Kotlin runtimes apply, answers the same `measure` / `command` /
`animate` requests, and raises the same events. Your Python runs in the
`pn preview` process with the on-device reconciler, screen host, hooks,
navigation, async runtime, and flex layout engine unchanged. Only the
leaf widgets differ: DOM elements instead of UIKit and Android views.

## Quick start

From a project directory (one created by `pn init`, with an
`app/main.py` that defines `App`):

```bash
pn preview
```

This starts the [dev server](dev-workflow.md), opens
`http://localhost:8765/` in your default browser, mounts your `App` in
a phone frame, and watches `app/` for changes. Edit any component and
save: the page updates in place while preserving component state
(counters, text input, scroll position, the navigation stack).

`pn preview` imports your real app code, so install your project's
dependencies in the same environment first (`pip install` whatever you
declared in `[requirements].packages`). `pn preview` warns about
missing ones on startup. If an import fails, the preview logs the
traceback in its console and the terminal; install the package or fix
the code and save to recover.

```bash
pn preview                        # the project entry point (app/main.py -> App)
pn preview app.screens.home       # mount a different module's App
pn preview --port 9000            # another port
pn preview --host 127.0.0.1       # don't expose the server on the LAN
pn preview --no-open              # start the server, open the tab yourself
pn start                          # the same server without opening a browser
```

`pn start` and `pn preview` are the same command; `pn preview` only
adds opening the tab. Simulators and devices launched with `pn run`
connect to the same server, so one terminal drives every client.

## The toolbar

Along the top of the page:

- **Device**: iPhone 15, iPhone 15 Pro Max, iPhone SE, Pixel 8, Pixel
  Fold (inner), iPad mini, or *Fill window*. The frame's size, safe
  area insets, and notch follow the choice, so `use_safe_area_insets`
  and `use_window_dimensions` return realistic values. Switching
  devices re-lays out the running app without remounting it.
- **Rotate** (`r`): swap width and height.
- **Dark / Light** (`d`): toggle the color scheme. `use_color_scheme`,
  `use_theme`, and `{"light": ..., "dark": ...}` dynamic colors all
  follow it live.
- **Back** (`Esc`): the system back action. `use_back_handler`
  subscribers on the active screen get the first chance to consume it;
  otherwise the navigation stack pops, matching the Android hardware
  back button.
- **Reload app** (`Shift+R`): tear the app down and mount it again from
  scratch, discarding all state (a full remount, not a Fast Refresh).
- **Console** (`` ` ``): show or hide a log panel with the same lines
  the terminal prints, plus the page's own errors.

The status dot shows the WebSocket connection. If you stop `pn preview`
the page waits and reconnects when the server returns; the app is
mounted fresh on reconnect.

## How it works

`pn preview` sets `PN_PLATFORM=web` and runs
[`pythonnative.preview.serve`][pythonnative.preview.serve], which:

1. Starts a [`DevServer`][pythonnative.devserver.DevServer] on a
   background thread: HTTP for the page and its assets, WebSocket for
   the page and for dev clients.
2. Installs a [`WebTransport`][pythonnative.bridge.web.WebTransport] as
   the bridge transport. Transactions the reconciler commits become
   `["apply", ops]` messages to the page; the page's events come back
   as `["cb", ...]` callbacks; synchronous questions (`measure` above
   all) block the main thread until the page answers.
3. Runs the transport's main loop on the main thread. That loop is the
   browser's stand-in for the UIKit / Android main queue: every
   callback and every `asyncio` pump runs there.
4. When the page connects, tells it the entry module. The page asks
   the `Host` module to create a screen, exactly as
   `PNViewController` and `PNScreenFragment` do, and a
   [`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost]
   mounts your `App`.
5. Watches `app/` through the dev server and applies each change with
   [`apply_reload`][pythonnative.hot_reload.apply_reload], the same
   function the on-device dev client uses.

Layout is owned by the engine, not the DOM: the
[flex layout engine](../concepts/layout.md) computes an absolute frame
for every element, and the page positions each element with that frame.
Text is measured by the page with the same font it renders, so wrapping
and intrinsic sizes match what you see.

### Navigation

Root navigators (`create_stack_navigator`, tabs, drawer) drive a real
stack of screens in the page, the same way they drive
`UINavigationController` / AndroidX Navigation on device. Each pushed
screen gets its own host and reconciler; `navigate(...)` pushes,
`go_back()` pops, and the previous screen's state survives underneath.
Pushes and pops animate with a slide.

### Dev mode and errors

The preview always runs with dev diagnostics on: unknown style keys and
duplicate list keys print `[PN] WARN` messages, hook-order violations
raise immediately, and uncaught errors from renders, effects, and event
handlers show a full-screen **RedBox** with the traceback. Fix the code
and save; a successful reload clears the overlay. Errors that happen
before any screen exists (an import error in `app/main.py`) print in
the terminal and the page console.

## Fast Refresh

Saving a `.py` file under `app/` reloads the changed modules and swaps
every affected component function into the live tree in place, so the
next render reuses the existing hook state. Edits to a component body
keep your counters, form values, scroll positions, and navigation
stack. When a clean swap isn't possible, the screen remounts instead
so you're never stuck with a stale tree. See the
[Fast Refresh guide](hot-reload.md) for the mechanics; the preview and
device builds share the same engine.

## Branching on the platform

When the preview is running, [`Platform.OS`][pythonnative.Platform] is
`"web"`:

```python
import pythonnative as pn

pad = pn.Platform.select({"web": 12, "ios": 16, "android": 16, "default": 12})
```

`Platform.select`'s `"native"` key matches iOS and Android only; the
browser is a development surface, so use an explicit `"web"` key (or
`"default"`) for it. You can also check
[`Platform.is_web`][pythonnative.Platform] or the
`pythonnative.utils.IS_WEB` flag directly.

## What's faithful, and what's approximated

The preview is a **development tool**, optimized for fidelity of layout
and logic rather than pixel-perfect platform chrome.

Faithful:

- Flex layout, sizing, padding, spacing, absolute positioning, and
  safe areas for the chosen device frame.
- Component lifecycle, hooks, effects, context, error boundaries,
  Suspense.
- Navigation (stack push and pop, tabs, drawer, modals) and per-screen
  state.
- The async runtime, `use_resource`, `use_query`, timers, and
  state-driven updates.
- Text wrapping and intrinsic sizing.
- Colors (hex, rgb(a), named, `{"light", "dark"}`), border radius,
  borders, opacity, shadows, and overflow clipping.
- `Animated` timing, spring, and decay, run through the same
  `animate` protocol the native animators implement; transforms,
  opacity, and colors animate on the compositor.
- Gestures: the page streams raw pointer events to the Python
  [gesture arbiter](gestures.md), the same one Android uses.
- Scrolling, `FlatList` / `SectionList` windowing, pull to refresh,
  and scroll-driven `Animated.event` bindings.

Approximated or absent:

- Fonts are the browser's system stack, not San Francisco or Roboto,
  so glyph metrics differ slightly.
- Native controls (`Switch`, `Slider`, `Picker`, `DatePicker`,
  `SegmentedControl`) are styled HTML inputs rather than platform
  widgets.
- `WebView` is an `<iframe>`, which many sites refuse to load in.
- `Image` loads whatever the browser can (PNG, JPEG, GIF, WebP, SVG)
  from files under `app/` or URLs; asset resolution otherwise matches
  device builds.
- Device APIs: `Alert`, `Clipboard`, `Linking`, `Share`, `Haptics`
  (`navigator.vibrate`), `NetInfo`, `AppState`, and `Device` are
  implemented in the page. Everything else (`Camera`, `Location`,
  `Notifications`, `Biometrics`, `Storage`, ...) uses the pure-Python
  fallbacks in
  [`pythonnative.native_modules.fallback`](../api/native_modules.md):
  in-memory stores, `"unknown"` states, and "unavailable" results.
- Components without a browser implementation render a labeled
  placeholder box so the layout around them stays truthful.

When the chrome matters, verify on device with `pn run`.

## Sharing the preview

The server binds to all interfaces by default, so someone on the same
network can open `http://<your-ip>:8765/` and see the app. One page
drives the app at a time: the newest tab to connect takes over, and the
previous one shows a notice until you reload it. Use
`--host 127.0.0.1` to keep the preview local.

## Next steps

- The whole loop, including simulators and devices:
  [Development workflow](dev-workflow.md).
- Mechanics shared with device Fast Refresh: [Fast Refresh](hot-reload.md).
- How layout is computed: [Layout engine](../concepts/layout.md).
- Platform branching: [Platform & accessibility](platform-accessibility.md).
