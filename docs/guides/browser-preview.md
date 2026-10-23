# Browser preview

`pn preview` renders your app in a browser tab, inside a phone frame,
with **Fast Refresh on every save**. It's the fastest way to build UI in
PythonNative: edit a component, save, and see the result in well under a
second, with no simulator boot, no device deploy, and no native build.

```bash
pn preview
```

The page runs the same renderer core as the iOS and Android apps,
compiled to WebAssembly, so commits are validated, laid out, and flattened
by the code that ships. Your components, hooks, reconciliation, logical
navigation, and async work run in the `pn preview` Python process. The page
mounts DOM elements in place of native widgets. Platform controls, fonts,
and device APIs differ from those in a mobile app.

## Quick start

From a project directory (one created by `pn init`, with an
`app/main.py` that defines `App`):

```bash
pn preview
```

This starts the [dev server](dev-workflow.md), opens
`http://localhost:8765/?token=...` in your default browser (the page
trades your [dev token](dev-workflow.md#the-dev-token) for a cookie and
drops it from the address bar), mounts your `App` in
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

Along the top of the page (on a narrow window the buttons shrink to icons;
hover one for its name and shortcut):

- **Device**: iPhone 15, iPhone 15 Pro Max, iPhone SE, iPad mini, Pixel 8,
  Pixel Fold (inner), or *Fill window*. Each device draws its own frame:
  the Dynamic Island, the iPhone SE's bezels and home button, the Android
  punch-hole camera and gesture handle. The status bar height and safe
  area insets follow the choice, so `use_safe_area_insets` and
  `use_window_dimensions` return realistic values. Switching devices
  re-lays out the running app without remounting it. The readout beside
  the menu shows the window size in points, and the zoom when the frame
  is scaled down to fit.
- **Rotate** (`r`): turn the device to landscape and back. A landscape
  iPhone hides its status bar and insets both sides for the sensor
  housing, as iOS does.
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
  the terminal prints, plus the page's own errors. A badge counts errors
  logged while it's closed. Drag its title bar to resize it.
- **Dev menu** (`Cmd+D` / `Ctrl+D`): reload, the element inspector, the
  performance monitor, and debugging with VS Code.
- **DevTools**: open [PythonNative DevTools](devtools.md) in a new tab.

The dot beside the project name shows the WebSocket connection. If you
stop `pn preview` the page waits and reconnects when the server returns;
the app is mounted fresh on reconnect. The device, orientation, color
scheme, and console state are remembered per browser.

## How it works

`pn preview` sets `PN_PLATFORM=web` and runs
[`pythonnative.preview.serve`][pythonnative.preview.serve], which:

1. Starts a [`DevServer`][pythonnative.devserver.DevServer] on a
   background thread: HTTP for the page and its assets, WebSocket for
   the page and for dev clients.
2. Installs a [`WebTransport`][pythonnative.bridge.web.WebTransport] as
   the bridge transport. It forwards the calls a device transport makes
   into the renderer core (commits, layout reads, commands, and animation
   requests) over the WebSocket to the core in the page, and the core's
   messages come back as callbacks. Commits acknowledge exact revisions
   with the frames of observed views.
3. Runs Python callbacks and tasks on the standard application asyncio loop.
   The page owns the core, DOM widgets, and the frame clock. Network I/O and
   Python work execute independently of the browser's UI thread.
4. When the page connects, tells it the entry module. The page asks
   the `Host` module to create a screen, exactly as
   `PNViewController` and `PNScreenFragment` do, and a
   [`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost]
   mounts your `App`.
5. Watches `app/` through the dev server and applies each change with
   [`apply_reload`][pythonnative.hot_reload.apply_reload], the same
   function the on-device dev client uses.

Layout is owned by the core, not the DOM: the
[flex layout engine](../concepts/layout.md) computes a frame for every
mounted element, and the page positions each element with that frame.
Text and controls are measured by the page with the same fonts and
elements it renders, so wrapping and intrinsic sizes match what you see.
Views that only affect layout are flattened, as on device, so a plain
`Row` or `Column` often has no element of its own; the element inspector
then selects the nearest mounted view. See
[The native bridge](../concepts/bridge.md#the-browser-preview) for how the
page plays the core's platform.

### Navigation

Root navigators (`StackNavigator`, `TabNavigator`, and
`DrawerNavigator`) drive a real stack of screens in the page, the same
way they drive `UINavigationController` and fragments on device. Each pushed
screen remains a logical child of the application's shared tree;
`navigate(...)` selects or adds a route, `go_back()` pops, and covered
screens keep their state.
Pushes and pops animate with the screen's `animation` and
`presentation` options.

Each stack draws a navigation bar from the top screen's options, the way
the native stacks do: `title`, `header_shown`, `header_large_title`,
`header_back_visible`, `header_back_title`, `header_tint_color`,
`header_style`, and `header_title_style`, with `header_left` and
`header_right` rendered in the bar. The back button pops through the same
path as an iOS swipe back, so a `before_remove` listener can veto it. A
stack at the root of the app replaces the host's own bar, as it does on
iOS.

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

- Flex layout, sizing, padding, gap, absolute positioning, and
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
- `Animated` timing, spring, and decay, run by the core's animator in
  the page, the same code the mobile apps use; transforms, opacity, and
  colors update on the page's animation frames.
- Gestures: the page forwards pointer events to the core's
  [gesture engine](gestures.md), the one Android uses. iOS uses UIKit's
  recognizers.
- Scrolling, `FlatList` / `SectionList` windowing, pull to refresh
  (drag the content down at the top, or scroll up past it with a
  trackpad or mouse wheel), and scroll-driven `Animated.event` bindings.
- Navigation transitions: card pushes slide over a parallaxing screen,
  modals slide up, and `Modal` honors `animation_type`.

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

The server binds to all interfaces by default so your own phones can
reach it, but it only answers clients that present your
[dev token](dev-workflow.md#the-dev-token). The LAN URLs `pn start`
prints carry the token, and anyone who has one can read your app's
source for as long as the token stays the same, so open them only on
your own devices. One page drives the app at a time: the newest tab to
connect takes over, and the previous one shows a notice until you reload
it. Use `--host 127.0.0.1` to keep the preview local.

## Next steps

- The whole loop, including simulators and devices:
  [Development workflow](dev-workflow.md).
- Mechanics shared with device Fast Refresh: [Fast Refresh](hot-reload.md).
- How layout is computed: [Layout engine](../concepts/layout.md).
- Platform branching: [Platform & accessibility](platform-accessibility.md).
