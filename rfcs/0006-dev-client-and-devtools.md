# RFC 0006: Dev client and DevTools

- Status: Implemented
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-10-08
- Implemented in: (this pull request)
- Supersedes / Superseded by: replaces the `--dev-client` connect-screen
  build from the dev workflow that predates the RFC process, and the
  plain-traceback development error overlay from RFC 0003

## Summary

PythonNative's runtime now matches React Native's feature surface, but the
first hour with it doesn't. Trying an app on a phone means installing Xcode
or the Android NDK and waiting minutes for a native build; pairing a phone
means typing a LAN address and a 32-character token; and once the app runs,
there's no way to set a breakpoint, inspect a component, see a network
request, or measure a frame. This RFC adds the development surface that
made React Native approachable, in Python's idiom:

- **PythonNative Go**, a prebuilt, generic dev client published with every
  release, which `pn start` installs on a simulator or emulator in seconds
  and which a phone opens by scanning a QR code.
- **A dev session protocol** that pairs any dev client with `pn start`
  through deep links, checks native compatibility at the handshake, and
  syncs pure-Python packages from the host environment.
- **PythonNative DevTools**, a web page served by `pn start` with a
  component tree and inspector, a console and REPL, a problems list, a
  network log, and live performance numbers for the browser preview and
  every connected device.
- **Breakpoint debugging** through `debugpy`: VS Code (or any Debug Adapter
  Protocol client) attaches to `localhost:5678`, and `pn start` tunnels the
  session to the preview, a simulator, an emulator, or a phone.
- **An on-device dev menu, element inspector, and performance monitor**,
  and a development error screen with component stacks, source excerpts,
  and collapsed framework frames.
- **An interactive `pn start`** and a fuller `pn init` scaffold.

It also fixes the correctness bugs the audit behind it found.

## Motivation

A September 2026 audit (v0.49.0) compared PythonNative's developer
experience with Expo, React Native DevTools, and ordinary Python tooling.
The runtime was the strongest part of the comparison; the loop around it
was the weakest.

### Getting an app onto a phone takes a native toolchain

```bash
pip install pythonnative
pn init my_app && cd my_app
pn start            # terminal one
pn run ios          # terminal two: Xcode, a 2 to 7 minute first build
```

Every device trial builds a native app. The iOS path needs Xcode; the
Android path needs a JDK, the Android SDK, the NDK, and CMake, because
Yoga is compiled from C++ on the developer's machine. RFC 0005 cut a cold
`pn run ios` from 6.7 minutes to 116 seconds, but that's still the first
thing a newcomer waits for. React Native has the same problem and solved
it with Expo Go: a prebuilt app that runs any project that doesn't add
native code.

The closest thing PythonNative has is `pn run ios --dev-client`, which
builds a generic shell locally, so it saves nothing on the first run.

### Pairing is manual

A phone connects by typing `192.168.1.20:8765/?token=...` into a text
field (`devclient.py`, `ConnectScreen`). There's no QR code and no deep
link. `pn run android` won't boot an emulator; it only lists running ones.
`pn start` reads no keyboard input, so there's no "press `i` to open iOS."

### There's nothing to debug with

- **No breakpoints.** `breakpoint()` in a device build calls `pdb`, which
  has no terminal to read from. There's no `debugpy` integration for the
  preview, a simulator, or a phone.
- **No inspector.** Nothing maps a widget on screen to the component that
  rendered it, its props, or its hook state.
- **No REPL, network log, or performance view.** Profiling works only in
  the host process (`PN_PROFILE`); on a device you'd have to write a trace
  from your own code and copy it off.
- **One-way protocol.** The dev client accepts only `sync` and `update`
  messages (`devclient.py`, `_handle`), and the server only receives logs.
  There's no channel to ask a running app anything.

### Errors are raw tracebacks

The development error overlay (`PNErrorOverlay.swift`, `ErrorOverlay.kt`)
shows `traceback.format_exception` output as one string. It doesn't say
which component was rendering, doesn't show the offending source line, and
buries the application's frames among the reconciler's. Warnings go to
stderr and nowhere else.

### Mismatches fail silently

The `hello` a dev client sends carries no `pythonnative` version, protocol
version, or contract fingerprint (`devclient.py`, `_hello`). A dev client
built before a plugin was added, or from another framework version, runs
the app against mismatched native code until something crashes.

### New projects start bare

`pn init` writes `app/main.py`, `pythonnative.toml`, and `.gitignore`. There
are no tests, no `pyproject.toml`, no pinned framework version, no editor
configuration, and no CI.

### Correctness bugs found by the audit

- `gestures.Tap(handler)` binds `handler` to `on_begin`, not `on_tap`:
  `_BaseGesture` is a positional frozen dataclass whose first field is
  `on_begin`, and `kind` is a settable public field.
- `type Node = Element | None | bool | Iterable[Node]` admits `str`,
  because `str` is an `Iterable[str]`. `pn.Column("label")` passes
  `mypy --strict` and the string is dropped at run time.
- Generated Swift prop decoders use `try!` 502 times
  (`NativeProps.swift`). A decoder that disagrees with its validator
  crashes the app instead of rejecting the commit.
- The RFC index omits RFC 0005, and the Android guides disagree about the
  supported JDK.

## Reference behavior

- **Expo Go** is a store-distributed app containing the Expo SDK. `npx expo
  start` prints a QR code; scanning it with the system camera opens Expo Go,
  which downloads the JavaScript bundle. Projects with custom native code
  build a **development build** (`expo-dev-client`) instead; the
  handshake compares a runtime version and refuses incompatible bundles.
- **The Metro terminal UI** reads single keys: `i` and `a` open the
  simulator and emulator, `r` reloads, `m` toggles the dev menu, `j` opens
  the debugger.
- **The dev menu** appears on shake, Cmd+D in the iOS Simulator, and Cmd+M
  (the menu key) in the Android emulator. It offers reload, the element
  inspector, the performance monitor, and the debugger.
- **React Native DevTools** connects through Metro's inspector proxy and
  shows a component tree with props and hooks, a console, a network
  panel, and a profiler.
- **LogBox** shows errors with a component stack, the relevant source
  excerpt, and collapsed framework frames, and links each frame to the
  editor through Metro's `/open-stack-frame` endpoint.

PythonNative follows this shape and deliberately differs in three places:

- **Python's debugger, not Chrome's.** JavaScript debugging speaks the
  Chrome DevTools Protocol. Python developers already use the Debug Adapter
  Protocol through `debugpy` in VS Code, PyCharm, and other editors, so
  breakpoints use `debugpy` and the developer's own editor. DevTools hosts
  everything else.
- **No store distribution.** Expo Go is in the App Store and Play Store.
  This repository can't publish to a store, so PythonNative Go is
  published as release assets: an iOS Simulator app and an Android APK.
  Physical iPhones need a local build signed with the developer's team.
- **No bundler.** Expo Go downloads one JavaScript bundle. PythonNative Go
  receives the project's source files through the existing
  content-addressed sync, and pure-Python packages are synced from the
  host's environment the same way.

## Design

### Overview

```
                   ┌──────────────── pn start ─────────────────┐
  VS Code ── DAP ──┤ :5678 debug proxy                         │
                   │                                           │
  DevTools page ───┤ /devtools ── ws role=devtools ─┐          │
                   │                                │ router   │
  Browser preview ─┤ ws role=preview ── in-process agent        │
                   │                                │          │
                   │ ws role=client ────────────────┘          │
                   └───────────────┬───────────────────────────┘
                                   │ sync, rpc, events, tunnel
           ┌───────────────────────┼────────────────────────┐
           │ PythonNative Go or a `pn run` debug build      │
           │ dev client ── devtools agent ── DevSupport     │
           └────────────────────────────────────────────────┘
```

Every dev client (Go, a `pn run` debug build, or the browser preview)
runs the same **devtools agent**. `pn start` routes DevTools requests and
debugger connections to whichever client is selected and broadcasts the
clients' events to every DevTools page.

### The dev session protocol

`pythonnative.devclient` and `pythonnative.devserver` speak version 2 of
the dev session protocol, which is independent of the bridge protocol.

**Handshake.** The client's `hello` describes its runtime:

```json
{
  "type": "hello",
  "session": 2,
  "client": "go",
  "platform": "ios",
  "device": "iPhone 17 Pro",
  "app": "app.main",
  "runtime": {
    "pythonnative": "0.50.0",
    "python": "3.13.15",
    "protocol": 6,
    "contracts": "<fingerprint>",
    "plugins": ["inbox-extension"],
    "distributions": {"httpx": "0.28.1"}
  },
  "files": {"app/main.py": "<sha256>"}
}
```

`client` is `"go"` for PythonNative Go and `"app"` for a project's own
debug build. The server compares the runtime with the project
(`devserver/compat.py`):

- The session protocol must match.
- A Go client must run the same `pythonnative` version as the host, and
  the project must not need native plugins or native-only packages.
- An app client's contract fingerprint must match the project's current
  contracts.

A mismatch is answered with `{"type": "incompatible", "reason": ...,
"fix": ...}`, shown on the device and in the terminal, instead of a sync.
The fix names the command that resolves it (`pn run ios --rebuild`, or
"this project adds native code; build it with `pn run ios`").

**Package sync.** The server resolves the project's `[requirements]`
against the host environment (`devserver/packages.py`). The distributions
already in the client's bundle are skipped. Pure-Python distributions are
sent with the sources and written under the overlay's `site-packages/`,
which the client appends to `sys.path`. A distribution with compiled
extensions makes the session incompatible for Go and is reported as a
warning for app clients, whose builds bundle their own wheels. The host
environment is the source because the browser preview already requires
`[requirements]` to be installed there.

**Requests and events.** Two message pairs are added:

- `{"type": "rpc", "id", "method", "params"}` from the server, answered
  by `{"type": "rpc_result", "id", "result"}` or `{"type": "rpc_result",
  "id", "error"}`.
- `{"type": "event", "topic", "data"}` from the client, for logs,
  problems, network records, performance samples, and inspector
  selections.

**Tunnels.** `{"type": "tunnel", "stream", "op": "open" | "data" |
"close", "port", "data"}` carries a TCP stream (base64 in `data`) between
a socket the server accepted and a localhost port on the device. The
debugger uses it, so a phone needs no open port.

**Deep links.** Every dev client registers the URL scheme
`pn-<application id>` (underscores become hyphens), so PythonNative Go
answers `pn-com.pythonnative.go://` and an app with id `com.example.my_app`
answers `pn-com.example.my-app://`. `<scheme>://connect?url=<server URL>`
connects to a server. `pn start` prints the link as a QR code. The CLI
opens it on Android with `adb shell am start`. On iOS it passes the same
link in the `PN_CONNECT_LINK` launch environment variable (`simctl launch`,
`devicectl process launch`), because iOS asks the user to confirm a link
opened with `simctl openurl`. Both replace the `PN_DEV_SERVER` launch
environment variable and the `pn_dev_server` intent extra, which carried a
bare server URL.

### PythonNative Go

PythonNative Go is the project-independent dev client: a debug build whose
`app/main.py` is the Go home screen and whose identity is fixed
(`com.pythonnative.go`, "PythonNative Go"). It declares every permission
the built-in modules use, so a project's camera, location, and
notification code works in it, and bundles no third-party packages.

**Distribution.** The release workflow builds Go for each release with
`scripts/build-go.py` and attaches three assets to the GitHub release:

- `pythonnative-go-<version>-ios-simulator.zip`
- `pythonnative-go-<version>-android.apk`
- `pythonnative-go-<version>.sha256`

**Installation.** `pn go ios` and `pn go android` (`project/go.py`) find
the artifact for the running `pythonnative` version in the shared cache
(`~/Library/Caches/pythonnative/go/<version>/`, or the platform's cache
directory), download and verify it when it's missing, and build it locally
with the project builder when no release asset exists (a development
checkout, or offline). `--build` forces the local build. They then install
it on the selected or booted simulator or emulator, booting one when none
is running, and open the connect link for the running `pn start`.
`pn go ios --device` builds and signs Go locally for a physical iPhone.

**Home screen.** Go's home screen (`devclient.GoHome`) lists recent
servers, accepts a pasted URL, shows the connection state, and shows an
`incompatible` answer with its fix. Disconnecting from the dev menu
returns to it.

### `pn start` and the CLI

`pn start` prints a QR code for the connect link, the preview and DevTools
URLs, and the debugger address, then reads single keys when stdin is a
terminal:

| Key | Action |
| --- | --- |
| `i`, `a` | Open the app on the iOS Simulator or Android emulator: in Go when the project is compatible with it, otherwise as a `pn run` debug build |
| `I`, `A` | Always build and run the project's own debug build |
| `w` | Open the browser preview |
| `j` | Open DevTools |
| `r` | Reload every connected client |
| `m` | Open the dev menu on every connected device |
| `d` | Print the debugger status and the VS Code configuration |
| `c` | Clear the terminal |
| `?` | List the commands |
| `q` | Quit |

`--no-interactive` disables key handling. `--debug-port` moves the
debugger proxy (default `5678`; `0` disables it).

New and changed commands:

- `pn go ios|android [--device D] [--build]` installs and opens Go.
- `pn run` boots an Android emulator when none is running and hands the
  app a connect link instead of a bare server URL.
- `pn init` also writes `pyproject.toml` (pinning `pythonnative` and
  declaring `pytest` and `mypy` for development), `tests/test_app.py`
  using `pythonnative.testing`, `.vscode/launch.json` with the attach
  configuration, `.vscode/extensions.json`, and a GitHub Actions workflow
  that runs `pn lint`, `mypy`, and `pytest`.

### The devtools agent

`pythonnative.devtools` (development only) runs in every dev client and in
the preview process. Requests run on the application thread, so they see
a consistent tree.

| Method | Result |
| --- | --- |
| `tree` | Every live screen's component tree: node ids, names, kinds (component, native, provider, boundary, suspense), keys, native tags, and source locations |
| `inspect` | One node's props, hook state (`use_state` values, refs, memo and effect dependencies), consumed context values, layout frame, and source location; values are summarized safely and truncated |
| `set_state` | Replace one `use_state` slot with a Python literal, then re-render |
| `highlight` | Outline a node's native view, or clear the outline |
| `set_inspecting` | Turn the on-device element inspector on or off |
| `eval` | Evaluate Python in the app's namespace on the application loop, with top-level `await` and `node` bound to the selected component |
| `reload` | Remount every screen |
| `menu` | Show the dev menu |
| `perf` | Turn sampling and the on-device performance monitor on or off |
| `trace` | Start or stop a Chrome trace and return it |
| `debug` | Start the in-process debug adapter (on a worker thread, so the loop stays responsive) and return its port |
| `status` | Whether the inspector, monitor, sampling, and a debugger are active |

Events published by the agent:

- `log`: `print` output and `logging` records (the dev client's existing
  stream, now also structured).
- `problem`: an error or warning as an `ErrorReport` (below).
- `network`: one record per `pn.fetch` request: method, URL, status,
  timing, sizes, headers, and a body preview.
- `perf`: once a second while sampling, the application loop's lag,
  renders, commits and their durations, and the native frame rate.
- `select`: the node chosen with the on-device inspector.
- `inspecting`, `perf_monitor`, and `reload`: state changes DevTools
  mirrors.
- `open_devtools`, `open_editor`, and `debug_target`: requests the dev
  server acts on (open the page, open a file, attach the debugger to this
  app).

The inspector marks components and context providers defined inside
PythonNative as framework nodes, which DevTools hides by default. To tell
a framework context from the app's, `Context` records the module that
created it (`Context.module`).

### DevTools

`GET /devtools` serves a single page (`devserver/static/devtools/`), with
no build step, like the preview. It connects with `role=devtools` and the
dev token cookie, so a page opened from the printed URL is authenticated.
A target picker lists the preview and every connected client. Panels:

- **Components:** the tree with search; hovering a node highlights it on
  the target, and selecting it shows props, hooks, context, frame, and
  source with an editor link. State values are editable. A button turns
  on the on-device inspector, whose selections appear here.
- **Console:** logs from every target with level and target filters, and
  a REPL bound to the selected target.
- **Problems:** errors and warnings with component stacks, source
  excerpts, collapsed framework frames, and editor links.
- **Network:** requests made with `pn.fetch`, with headers and body
  previews.
- **Performance:** live numbers and charts for frame rate, loop lag, and
  commit times, a table of recent commits, and trace recording that
  downloads a file for Perfetto or Chrome.
- **Connect:** the QR code, URLs, how to install Go, and the debugger
  configuration.

**Editor links** call the server, which opens `file:line` with
`$PN_EDITOR`, then `code --goto`, then the system's default handler.
Device paths are mapped back to the project: overlay and bundle paths
under `app/` resolve to the project's `app/`, and synced packages to the
host environment.

### Debugging

`pn start` listens on `127.0.0.1:5678`. Each connection is a debugging
session for the selected target (the most recently connected client
unless DevTools picked another). The server asks the target's agent to
start `debugpy` with an in-process debug adapter
(`debugpy.listen(..., in_process_debug_adapter=True)`), which needs no
subprocess, then joins the connection to the adapter: directly for the
preview, and through a tunnel for a device.

- **Getting `debugpy` onto the device.** `debugpy` becomes a dependency of
  `pythonnative` on the host (app bundles never include it). The first debugging session syncs its
  pure-Python sources to the client, without its compiled speedups, like
  any other package.
- **Path mapping.** The agent maps the device's overlay and bundle paths to
  the project root and host packages before starting the adapter, so
  breakpoints set in the editor bind on the device.
- **Threads.** The dev client's network and tunnel threads, and the dev
  server's threads in the preview process, are marked as debugger threads
  so a breakpoint doesn't freeze the connection that serves it. Native UI
  keeps running while Python is paused; native events queue.
- **`breakpoint()`.** Dev clients set `sys.breakpointhook`: with a
  debugger attached it pauses there, and without one it reports the
  location and how to attach, instead of starting `pdb` with no terminal.

`pn init` writes this configuration:

```json
{
  "name": "PythonNative: Attach",
  "type": "debugpy",
  "request": "attach",
  "connect": {"host": "127.0.0.1", "port": 5678},
  "justMyCode": true
}
```

### Errors and warnings

`pythonnative.errors` builds an `ErrorReport` from an exception:

```python
@dataclass(frozen=True)
class ErrorReport:
    phase: str                         # "render", "effect", "event", ...
    type: str
    message: str
    component_stack: tuple[ComponentFrame, ...]
    frames: tuple[StackFrame, ...]     # with source excerpts and a framework flag
    text: str                          # the formatted traceback
```

The reconciler records the component path while rendering in development
mode and attaches it to an exception the first time it passes a component
boundary, which also adds a note to the traceback (`PEP 678`):

```
ZeroDivisionError: division by zero
The above error occurred in <Counter> (app/main.py:14)
  in <HomeScreen> (app/main.py:30)
  in <App> (app/main.py:52)
```

The development error screen on iOS and Android, and the preview's, show
the error type and message, the component stack, application frames with
source excerpts, framework frames collapsed into one row that expands, and
Reload, Dismiss, Copy, and Open in Editor buttons. Warnings carry the
component that was rendering and appear in the DevTools Problems panel.

### Native runtimes

A new non-contract module, `DevSupport`, joins `Host`, `Layout`, and
`Runtime` on both platforms and in the preview. It's inert until Python
enables it, which happens only in development mode.

| Method | Behavior |
| --- | --- |
| `enable` | Start listening for menu triggers |
| `highlight` | Draw an outline and a label over a view, or clear it |
| `set_inspecting` | Intercept taps and report the tapped view's tag as an `inspect` event |
| `set_perf_monitor` | Show or hide the floating monitor, with Python's lines and the native frame rate |
| `frame_stats` | The UI thread's frames per second and dropped frames since the last call |

Menu triggers send a `menu` event: a shake on devices, Cmd+D and
Ctrl+Cmd+Z in the iOS Simulator (`PNWindow`, a `UIWindow` subclass the
template's scene delegate now uses), and the menu key on Android, which
the emulator sends for Cmd+M. Cmd+R in the simulator sends `reload`, and
the inspector's Done button sends `inspect_done`. The menu itself is the
existing `Alert` action sheet (`Alert.choose`), so it needs no new native
UI. Tapping one of the application's frames on the error screen sends a
`host` event, `open_in_editor`, which the agent forwards to the dev server.

`Host.show_error` takes the structured report. The bridge protocol moves to
version 6 for these two changes; dev clients built before it must be
rebuilt, which the handshake reports.

### Browser preview

The preview implements `DevSupport` with DOM overlays: an outline and
label over the inspected element, click-to-inspect, and a perf monitor
box. Its toolbar gains a Dev menu button and a DevTools link, and its error
overlay shows the structured report.

### Correctness fixes

- Gesture descriptors are `@dataclass(frozen=True, kw_only=True)` with
  `kind` as a `ClassVar`, so `Tap(on_tap=...)` is the only spelling and a
  positional handler is a type error.
- `Node` excludes `str` and `bytes`: it's `Element | None | bool |
  list[Node] | tuple[Node, ...] | Iterator[Node]`.
- Generated Swift and Kotlin prop getters no longer crash when a value
  doesn't decode (the Swift ones used `try!` 502 times). A getter records
  the failure and returns `nil`, and the transaction fails the operation
  that read it with "props for <type> tag <n>: field <key> didn't decode",
  which takes the existing failed-commit path instead of terminating the
  app.
- `Alert.choose` on Android hid every option when it also had a message,
  because an `AlertDialog` shows either a message or a list. The message
  now joins the title, and a cancel option stays a button.
- After a preview page went away with a commit in flight, the next page's
  mount failed on a surface marked as failed. The preview now waits for the
  in-flight commit and resets the surface before mounting for a new page,
  and a host ignores commit failures from a tree it already released.
- The RFC index lists RFC 0005 and this RFC; the Android guides state one
  supported JDK range.

## Removals

- `pn run --dev-client`, `ConnectScreen`, and
  `devclient.placeholder_main_source`. PythonNative Go replaces the
  locally built generic shell; a project's own debug build remains the
  dev client for projects with native code.
- The `PN_DEV_SERVER` launch environment variable on iOS and the
  `pn_dev_server` intent extra on Android, and
  `configure_dev_environment`'s `server_url` parameter: connect links
  replace them.
- The string-only `trace` payload of `Host.show_error`.
- The unversioned dev `hello`.
- `kind` as a dataclass field of the gesture descriptors; it becomes a
  class variable, and gesture descriptors are keyword-only.

## Alternatives considered

- **Chrome DevTools Protocol for Python.** Implementing CDP's debugger
  domain over `sys.monitoring` would put everything in one window, but
  it would be a new debugger nobody's editor supports. `debugpy` is what
  Python developers already have.
- **Hosting DevTools in the editor.** A VS Code extension could show the
  tree, but it would exclude other editors and need a marketplace
  release. A page served by `pn start` works everywhere and reuses the
  preview's serving code.
- **Opening a debug port on the device.** Simpler than a tunnel, but it
  exposes arbitrary code execution to the local network and needs
  `adb forward` for Android. The tunnel inherits the dev token's
  authentication.
- **Syncing the `pythonnative` package to Go.** That would let one Go
  build serve every framework version, but the bundled package is already
  imported when the dev client connects. Matching versions exactly is
  simpler and is what Expo does with SDK versions.
- **Mobile wheels for package sync.** Resolving `[requirements]` for the
  device's tags on every connection would be exact but slow and would
  need network access; the host environment is already required by the
  preview.
- **mDNS discovery.** Finding servers on the LAN without a QR code needs a
  responder in `pn start`, local network permissions, and Bonjour
  declarations. QR codes and recent servers cover the same need.

## Non-goals

- Publishing PythonNative Go to the App Store or Play Store, or to
  TestFlight.
- Over-the-air updates.
- An in-app QR scanner; the system camera opens the connect link.
- mDNS or Bonjour discovery.
- Native-only packages in Go, such as `numpy` (those projects use their
  own debug build).
- Capturing HTTP made without `pn.fetch` (`urllib`, `httpx`) in the
  Network panel.
- An on-device list of warnings; they appear in the terminal and DevTools.
- A memory profiler or heap snapshots.
- The API cleanup from the same audit (export trimming, a `State` object,
  typed `use_mutation`); that's its own RFC.

## Testing and rollout

- **Unit tests:** the QR encoder against reference matrices, the session
  handshake and compatibility rules, package resolution and purity, the
  RPC router, the tunnel (a TCP echo through a fake client), the agent's
  tree and inspection with `FakeBackend`, state editing, the REPL, network
  records, component stacks and error reports, key handling in `pn start`,
  Go artifact resolution with a fake downloader, and the `pn init`
  scaffold, which must pass `pn lint`, `mypy --strict`, and its own tests.
- **Browser tests:** DevTools against a running `pn start`.
- **Native tests:** the `DevSupport` module and the structured error
  screen in the Swift and Kotlin suites.
- **Manual end-to-end:** Go built locally and opened on an iOS simulator
  and an Android emulator through the CLI; the dev menu, inspector,
  performance monitor, error screen, and a `debugpy` session through the
  tunnel; recorded below.
- **Docs:** a PythonNative Go and DevTools guide, a Debugging guide, a
  DevTools API page, and updated Getting Started, Development workflow, CLI,
  architecture, troubleshooting, and home pages and README.
- **Release:** the release workflow builds and attaches the Go assets;
  `pn go` falls back to a local build until the first release that has
  them.

## Recorded validation

Measured on an Intel Mac (x86_64) with Xcode 26.3, an iPhone Air
simulator (iOS 26.2), and an API 31 x86_64 Android emulator, while other
work kept the host's load average between 80 and 900, so durations are
indicative only.

- **Tests:** the Python suite (2,347 tests), the browser tests, 113 iOS
  XCTests, and the Android unit suites pass. New suites cover error reports
  and component stacks, the agent, the dev session protocol (handshake,
  compatibility, routing, tunnels, package sync), Go's artifacts, the key
  commands and editor links, the QR encoder (bit-identical to `segno` and
  `qrcode` over 3,433 matrices), and the DevTools page.
- **iOS, PythonNative Go.** `pn go ios --build` built Go, installed it,
  and launched it with the connect link in the launch environment. It
  connected, synced the scaffolded project, and Fast Refreshed from the
  home screen into the app. DevTools listed the device, showed its
  component tree and hooks, edited a `use_state` value (the screen
  re-rendered), outlined a component on the device, and turned on the
  performance monitor (60 UI fps). `m` opened the dev menu. Saving a
  component that divides by zero showed the error screen with the
  component stack (`<Ratio>`, `<HomeScreen>`, `<App>`), the failing line
  highlighted, and 46 framework frames collapsed.
- **Android, PythonNative Go.** `pn go android --build` booted an emulator,
  built and installed Go, and opened the connect link; Go connected and ran
  the project. The menu key opened the dev menu, and the element inspector
  selected a `Text` and labeled it `App › HomeScreen › Text`.
- **Debugging.** A Debug Adapter Protocol client attached through `pn
  start` to the preview, to the iOS simulator, and to the Android emulator.
  The first session synced `debugpy` (218 files) to the device. A
  breakpoint in `HomeScreen` bound, a re-render stopped on it with stack
  frames mapped to the host's `app/main.py` and `pythonnative` sources, and
  the session continued and detached cleanly.
- **Not verified here:** downloading Go from a GitHub release (the first
  release with the assets will exercise it), physical devices, and VS
  Code's own UI (the protocol client was a script speaking the same DAP
  messages).

Two problems found during this validation changed the design. `simctl
openurl` makes iOS ask before opening the app, so the CLI passes connect
links to iOS in the launch environment instead. And debugger data sent
right behind a tunnel's `open` arrived before the device's local
connection existed, so the dev client now buffers it.

