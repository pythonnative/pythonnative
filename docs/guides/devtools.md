# PythonNative Go and DevTools

PythonNative's development surface has three parts:

- **Dev clients** run your project on a phone, simulator, or emulator
  and apply every save with Fast Refresh. PythonNative Go is a prebuilt
  dev client that runs any project without building it; your project's
  own debug build is a dev client too.
- **The dev menu, element inspector, and performance monitor** run on the
  device.
- **DevTools** is a web page served by `pn start`. It shows the component
  tree, a console and REPL, problems, network requests, and performance
  for the browser preview and every connected device.

Breakpoint debugging has its own guide: [Debugging](debugging.md).

## PythonNative Go

PythonNative Go is to PythonNative what Expo Go is to React Native: an
app that contains the framework and every built-in native module, and
loads your project's Python from `pn start`. Nothing is compiled on your
machine.

```bash
pn start          # terminal one: prints a QR code
```

Then do one of these:

- Press ++i++ in the `pn start` terminal to open the project on the iOS
  Simulator, or ++a++ for an Android emulator. The first time, `pn`
  downloads Go for your PythonNative version (or builds it, see below)
  and installs it; after that it opens in seconds.
- Run `pn go ios` or `pn go android` from another terminal, which does
  the same.
- On an Android phone with Go installed, scan the QR code with the
  camera. The code is a connect link that opens Go and points it at your
  computer.

### What runs in Go

Go runs a project when it adds no native code:

- **Python dependencies** listed in `[requirements]` are synced from the
  environment `pn start` runs in, as long as they're pure Python. Install
  them there first (`pn start` warns when one is missing).
- **Native plugins** and packages with **compiled extensions** (such as
  `numpy`) aren't in Go. `pn start` notices, and ++i++ and ++a++ build
  the project's own development app with `pn run` instead. A Go that
  connects anyway shows why it can't run the project and which command to
  use.
- **Permissions** for the built-in modules (camera, photos, location,
  notifications, biometrics, motion) are declared by Go. Your
  `pythonnative.toml` settings, such as the app name, icon, and URL
  schemes, apply only to your own builds.

Go must match the `pythonnative` version on your computer exactly, because
the framework is inside the app. `pn go` installs the matching version;
an older Go that connects is told to update.

### Where Go comes from

Each release attaches Go to its GitHub release: an iOS Simulator app and
an Android APK, with a SHA-256 checksum file. `pn go` downloads and
verifies the asset for your version and caches it under
`~/Library/Caches/pythonnative/go/<version>/` (`~/.cache/pythonnative`
on Linux, or `$PN_CACHE_DIR`). When there's no release asset, as with a
development checkout or no network, it builds Go once with your local
toolchain and caches the result. `pn go <platform> --build` forces a local
build, and `$PN_GO_BASE_URL` points downloads at a mirror.

Go isn't in the App Store. On a physical iPhone, `pn go ios --device
"My iPhone"` builds and signs Go with the `[ios].development_team` from
your `pythonnative.toml`. On a physical Android phone, `pn go android
--device <serial>` installs the APK over USB.

### Your project's development app

A project that adds native code runs in its own debug build, which `pn
run ios` and `pn run android` build and install. It's a dev client like
Go: it connects to `pn start`, syncs every save, and has the same dev
menu, inspector, and DevTools support. It registers a connect link of
its own, `pn-<app id>://connect?url=...`, so the QR code reopens it after
a restart. The native build reruns only when something native changes.

## Pairing

A connect link carries the server's address and your
[dev token](dev-workflow.md#the-dev-token):

```text
pn-com.pythonnative.go://connect?url=http%3A%2F%2F192.168.1.20%3A8765%2F%3Ftoken%3D...
```

- The QR code `pn start` prints holds the link for the client that can
  run the project: Go when possible, otherwise your development app.
- `pn run` and `pn go` hand the link to the app they launch, using
  `localhost` on simulators and emulators (Android reaches it through `adb
  reverse`). On Android it's a deep link (`adb shell am start`); on iOS
  it travels in the launch environment (`PN_CONNECT_LINK`), because iOS
  asks for confirmation before following a link opened from the command
  line.
- A dev client remembers the servers it connected to and reconnects to
  the last one at launch. Go's home screen lists them, and accepts a
  pasted URL for networks where the camera can't help.

The handshake checks that the dev client can run the project. A client
built from another framework version, or before a plugin was added,
shows the mismatch and the command that fixes it, instead of running
against the wrong native code.

## The dev menu

Open the dev menu on a device with any of these:

- Shake the device.
- Press ++cmd+d++ in the iOS Simulator (or use **Device > Shake**). ++cmd+r++
  reloads.
- Press ++cmd+m++ in the Android emulator, or run `adb shell input
  keyevent 82`.
- Press ++m++ in the `pn start` terminal, which opens it on every
  connected device.
- Click **Dev menu** in the browser preview's toolbar, or press
  ++cmd+d++ there.

| Item | What it does |
| --- | --- |
| Reload | Reimports your modules and remounts the app with fresh state. |
| Open DevTools on your computer | Opens DevTools in your computer's browser. |
| Show element inspector | Tap any view to select the component that rendered it. |
| Show performance monitor | A floating panel with the UI frame rate, the Python loop's lag, and render and commit rates. |
| Debug with VS Code | Makes this device the debugger's target and explains how to attach. |
| Disconnect | Go only: returns to Go's home screen. |

### Element inspector

With the inspector on, taps select instead of pressing. The selected
view is outlined and labeled with its component path (`App › HomeScreen
› Card`), and DevTools jumps to the same component. Tap **Done** in the
banner to leave the inspector.

### Performance monitor

The monitor shows these numbers, updated each second:

- **UI fps:** measured by the native UI thread. It stays smooth while
  Python works, because native scrolling and animation graphs don't wait
  for Python.
- **PY lag:** how late a timer on the Python application loop fired. A
  high value means something blocked the loop: a slow render, a
  synchronous network call, or CPU work that belongs in a thread.
- **Renders and commits:** how many reconciler passes and native commits
  ran, and the slowest of each.
- **Components:** components rendered per second.

## The development error screen

In a development build, an error in a render, effect, event handler, or
async task shows the error screen instead of crashing:

- **The error type and message.**
- **The component stack:** the components that were rendering, innermost
  first, with the file and line that defines each. The same stack is
  added to the printed traceback as a note:

  ```text
  ZeroDivisionError: division by zero
  The above error occurred in <Counter> (app/main.py:14)
    in <HomeScreen> (app/main.py:30)
    in <App> (app/main.py:52)
  ```

- **Your frames with source excerpts,** with PythonNative's, the standard
  library's, and installed packages' frames collapsed into one row you can
  expand.
- **Buttons:** Reload, Dismiss, and Copy. Tapping one of your frames opens
  it in your editor on your computer (see [Editor links](#editor-links)).

Saving a fix dismisses the screen and Fast Refreshes. Errors and warnings
also appear in DevTools' Problems panel and in the terminal.

## DevTools

Open DevTools by pressing ++j++ in the `pn start` terminal, or with the
URL it prints (`http://localhost:8765/devtools?token=...`). The picker in
the header chooses which app the panels show: the browser preview or any
connected device. DevTools keeps a short history, so opening it after an
error still shows it.

### Components

The component tree for every screen, with search. Framework components
(navigators, providers) are hidden until you turn them on; their children
stay visible. Hovering a node outlines its view on the device. Selecting
one shows:

- its props, with nested values you can expand;
- its hooks in order, with the values of `use_state`, `use_ref`, and
  `use_memo` and the dependencies of effects;
- the context values it reads;
- the file and line that define it, and its layout frame when Python has measured it (for example, for a view with a ref or `on_layout`).

`use_state` values are editable: type a Python literal and press ++enter++
to set it, which re-renders the component. **Select element on device**
turns on the on-device inspector.

### Console

Logs from every connected app (`print`, warnings, errors, and reloads),
filterable by level, app, and text. The input at the bottom is a REPL
running inside the selected app, on its application loop:

```python
>>> pn.Platform.OS
'ios'
>>> node.state            # the component selected in Components
[3]
>>> node.set_state(0, 10)
>>> response = await pn.fetch("https://example.com/api/items")
>>> response.status
200
```

The namespace persists between evaluations and includes `pn`, `asyncio`,
`app` (your entry module), and `node`, the selected component. `await`
works at the top level.

### Problems

Every error and warning, with its component stack, your frames with
source excerpts, and collapsed framework frames. File names are editor
links.

### Network

Requests made with [`pn.fetch`][pythonnative.fetch]: method, URL,
status, duration, size, headers, and a preview of the request and
response bodies (the first 4 KB). Requests made with other clients, such
as `urllib` or `httpx`, aren't captured.

### Performance

Live charts of the UI frame rate, the Python loop's lag, and render and
commit times, plus the slowest recent commits. **Record trace** captures
a [Chrome trace](dev-workflow.md#profiling) of the selected app,
including the native commit phases, and downloads it for Perfetto or
Chrome's trace viewer. A switch shows the on-device performance monitor.

### Connect

The QR code and links, how to install Go, and the debugger
configuration.

## Editor links

Frame and component links in DevTools and the error screen ask `pn start`
to open the file on your computer. Device paths are mapped back to your
project (`app/main.py`), and only files inside the project or the
environment's packages can be opened. The editor is chosen in this order:

1. `$PN_EDITOR`, a command where `{file}` and `{line}` are replaced, such
   as `PN_EDITOR="subl {file}:{line}"` or `PN_EDITOR="pycharm --line {line}
   {file}"`;
2. VS Code's `code --goto`, when `code` is on your `PATH`;
3. the system's default application for the file.

## Security

Everything here runs only in development builds; release builds omit the
dev client, the agent, and DevTools support. DevTools pages, dev clients,
and the debugger proxy all require your dev token, and the debugger proxy
listens on `127.0.0.1` only. DevTools can run code in your app (that's
what the REPL is for), so treat the token like a password and keep the
URLs to your own devices.
