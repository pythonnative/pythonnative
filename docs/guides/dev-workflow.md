# Development workflow

PythonNative's inner loop is modeled on Metro and Expo: one long-running
**dev server** in your terminal, and any number of **dev clients** (a
browser tab, simulators, emulators, physical phones) that connect to it.
You edit a file, you save, and every connected client Fast Refreshes in
place. Native builds happen only when something native changes.

```
  ┌────────────────────┐        ┌──────────────────────────────┐
  │  pn start          │  ws    │  browser preview (tab)       │
  │                    │◄──────►│  renders through the bridge  │
  │  watches app/      │        └──────────────────────────────┘
  │  syncs sources     │  ws    ┌──────────────────────────────┐
  │  streams logs      │◄──────►│  PythonNative Go, or your    │
  │  serves DevTools   │        │  debug build (simulator,     │
  │  proxies debugging │        │  emulator, phone on Wi-Fi)   │
  │                    │  ws    ┌──────────────────────────────┐
  │                    │◄──────►│  DevTools (browser tab)      │
  └────────────────────┘        └──────────────────────────────┘
```

## One terminal

Run the dev server for the whole session:

```bash
pn start          # dev server, QR code, and key commands
pn preview        # the same, and open the browser preview
```

`pn start` prints a QR code, the preview and DevTools URLs, and the
debugger address, then reads single keys:

| Key | Action |
| --- | --- |
| ++i++, ++a++ | Open the app on the iOS Simulator or an Android emulator: in [PythonNative Go](devtools.md#pythonnative-go) when the project can run there, otherwise as the project's own debug build (`pn run`) |
| ++shift+i++, ++shift+a++ | Always build and run the project's own debug build |
| ++w++ | Open the browser preview |
| ++j++ | Open [DevTools](devtools.md#devtools) |
| ++r++ | Reload every connected app |
| ++m++ | Open the [dev menu](devtools.md#the-dev-menu) on every connected device |
| ++d++ | Show which app the [debugger](debugging.md) attaches to, and the VS Code configuration |
| ++c++ | Clear the terminal |
| ++question++ | List the commands |
| ++q++ | Quit |

Scan the QR code with a phone's camera to open the project there. Every
connected app pulls any sources newer than what it holds and from then on
Fast Refreshes on every save. Its `print()` output, tracebacks, and
reload notices stream back to the `pn start` terminal.

The same actions are commands, for scripts and second terminals: `pn go
ios`, `pn go android`, `pn run ios`, and `pn run android` find the dev
server on `localhost:8765` (`--port` to change it), install the app, and
open it with a connect link carrying your [dev token](#the-dev-token).
Rerunning `pn run` is cheap: when nothing native changed since the last
build (see [When native rebuilds happen](#when-native-rebuilds-happen))
it reinstalls the previous artifact and relaunches in a few seconds.

## What `pn start` does

The dev server is one Python process, standard library only, doing
three jobs:

1. **Serves sources.** It computes a content-addressed manifest of
   `app/` (`sha256` per file) and hands connected clients whatever
   they're missing. Clients report what they already hold, so a fresh
   build after `pn run` transfers nothing and a stale install catches
   up in one round trip.
2. **Watches for changes.** Every save under `app/` broadcasts an
   `update` to each client with the new file contents. Each client
   reloads the affected modules and runs
   [Fast Refresh](hot-reload.md) on its mounted screens.
3. **Hosts the browser preview.** `GET /` is a preview page that
   renders the app in a phone frame. The page is a bridge peer exactly
   like the Swift and Kotlin runtimes; the reconciler for it runs
   inside `pn start` itself. See the
   [Browser preview guide](browser-preview.md).
4. **Serves DevTools and the debugger.** `GET /devtools` is the
   [DevTools](devtools.md#devtools) page, which talks to every connected
   app through the server, and `127.0.0.1:5678` accepts
   [debugger](debugging.md) connections and forwards them to an app.

Logs from every peer are interleaved in the terminal and prefixed with
the source: `[ios iPhone 15]`, `[android Pixel 8]`, `[browser]`, and
`[pn]` for the server's own messages.

Endpoints, for scripting and curiosity:

| Path | Purpose | Token |
|---|---|---|
| `GET /` | Browser preview page | No |
| `GET /static/<name>` | The preview's scripts and styles | No |
| `GET /status` | Server, project, and connected-peer info (JSON) | Yes |
| `GET /manifest` | `{"version", "entry", "files": {path: sha256}}` | Yes |
| `GET /file/<path>` | Raw bytes of one synced source file | Yes |
| `GET /assets/<path>` | A file under `app/assets/`, plus the asset manifest and font CSS | Yes |
| `GET /devtools` | The DevTools page (`/devtools/<name>` for its assets) | No |
| `GET /connect` | Connect links, server URLs, and the QR code as SVG (JSON) | Yes |
| `WS /ws?role=client` | Dev session protocol (version 2) | Yes |
| `WS /ws?role=preview` | Browser preview bridge channel | Yes |
| `WS /ws?role=devtools` | DevTools pages | Yes |
| `TCP 127.0.0.1:5678` | Debug Adapter Protocol proxy | Via the app's session |

For example, `curl -H "X-PN-Token: $(cat ~/.pythonnative/dev-token)"
localhost:8765/status` prints the server's status.

### Flags

```bash
pn start [entry] [--port 8765] [--host 0.0.0.0] [--debug-port 5678] [--no-interactive] [--open]
pn preview [entry] [--port 8765] [--host 0.0.0.0] [--debug-port 5678] [--no-interactive] [--no-open]
```

`entry` overrides the entry module from `pythonnative.toml` (for
example `app.screens.settings` to mount one screen's `App`). The server
binds to all interfaces by default so phones on your network can reach
it; pass `--host 127.0.0.1` to keep it local. `--debug-port 0` turns the
debugger proxy off, and `--no-interactive` stops `pn start` from reading
keys (it never does when stdin isn't a terminal).

### The dev token

The dev server hands out your application's source code, so it only
answers clients that present your **dev token**. `pn start` generates
the token the first time it runs, stores it in
`~/.pythonnative/dev-token` (readable only by you, mode `0600`), and
reuses it after every restart, so debug builds that `pn run` installed
keep connecting.

- The URLs `pn start` prints carry it as `?token=...`. When you open the
  preview URL, the page trades the token for an `HttpOnly`,
  `SameSite=Strict` cookie and drops it from the address bar. Opening
  the bare `http://localhost:8765/` in a browser that has never seen the
  token leaves the preview waiting; open the printed URL once instead.
- `pn run`, `pn go`, and the QR code pass the token to the app inside
  the connect link, and the app remembers it for its next launch.
- Scripts can send it in an `X-PN-Token` header or a `token` query
  parameter.

The server also rejects WebSocket connections from other web pages: a
browser's upgrade request must come from the server's own origin
(its `Origin` host and port must match the `Host` header). Native dev
clients send no `Origin`, so they only need the token.

To issue a new token (for example, after sharing a URL you shouldn't
have), stop `pn start`, delete `~/.pythonnative/dev-token`, and start it
again. Installed dev clients then need the new QR code (or a fresh `pn
run` or `pn go`), and the browser preview needs the newly printed URL. Two environment variables
override the file: `PN_DEV_TOKEN` supplies the token itself, and
`PN_DEV_TOKEN_FILE` points at another file. Set them the same way for
`pn start` and `pn run`.

## Dev clients

A **dev client** is an app that runs your project's Python from `pn
start`: either [PythonNative Go](devtools.md#pythonnative-go), the
prebuilt client that runs any project without native code, or your
project's own debug build from `pn run`. On launch,
`pythonnative.bootstrap.start(dev=True)` calls
[`devclient.start_if_configured`][pythonnative.devclient.start_if_configured],
which:

- takes the server URL, including the dev token, from the connect link
  that launched the app (`pn-<app id>://connect?url=...`, which `pn run`,
  `pn go`, and the QR code open), or reconnects to the last server it
  used;
- connects over WebSocket on a daemon thread and says `hello`, describing
  its runtime (framework version, bridge protocol, plugins, and bundled
  packages) and a hash of every source it holds in its writable
  **overlay**. On the first launch the overlay is seeded from the sources
  bundled in the build, so a build made from the current tree reports
  everything up to date;
- receives a `sync` with only the files that differ, or an `incompatible`
  answer naming the command that fixes a mismatch (an outdated Go, or a
  build that predates a plugin). Synced files go into the overlay, which
  sits ahead of the bundled sources on `sys.path`, and a Fast Refresh
  applies the modules that changed. Nothing changed, nothing reloads;
- installs the pure-Python packages from `[requirements]` that its bundle
  lacks, copied from the environment `pn start` runs in;
- mirrors `print`, warnings, and tracebacks to the server, and answers
  [DevTools](devtools.md#devtools) and the [debugger](debugging.md);
- reports every reload (`fast_refresh` or `remount`, and which modules).

Release builds never include any of this: `pn build` produces a
standalone app with your sources bundled and no dev client. Its copy of
`pythonnative` leaves out the development modules entirely (the dev
client, the DevTools agent, Fast Refresh, the dev server, the CLI, and
the test helpers); see
[Building for release](building-for-release.md#what-a-release-bundle-leaves-out).

### Simulators and emulators

Press ++i++ or ++a++ in the `pn start` terminal, or run `pn go ios`, `pn
go android`, `pn run ios`, or `pn run android`. The CLI handles the
plumbing: the iOS Simulator shares the Mac's loopback interface, so the
link uses `localhost`, and for Android the CLI runs `adb reverse` so
`localhost:8765` inside the emulator (or a USB-attached phone) reaches
the server. When no Android device is running, `pn` boots the first
emulator from Android Studio's Device Manager.

### Physical phones

A phone is on your Wi-Fi rather than your loopback, so it uses your
computer's LAN address. Scan the QR code `pn start` prints with the
camera; it opens the dev client with that address and your token. `pn
run ios --device <name>` and `pn go ios --device <name>` pass the LAN
address too. Both machines must be on the same network and the port must
not be firewalled. If auto-detection picks the wrong interface, pass the
device URL that `pn start` printed, token included:

```bash
pn run ios --device "Owen's iPhone" --dev-server "http://192.168.1.20:8765/?token=..."
```

Fast Refresh, DevTools, and the debugger work the same over Wi-Fi.

## When native rebuilds happen

A debug build has to go through Gradle or Xcode only when a **native
input** changes:

- `pythonnative.toml` (permissions, app id, requirements, versions)
- the bundled native template that ships with your `pythonnative`
  version
- the `pythonnative` package itself (after `pip install -U`)
- project-local native plugins
- the build flavor: platform, iOS SDK (device vs. simulator), release

`pn run` hashes the *contents* of all of those into one fingerprint
(see [`fingerprint.compute`][pythonnative.project.fingerprint.compute])
and writes it next to the build after a successful toolchain run. On
the next `pn run`, if the fingerprint matches and a dev server is up to
deliver current sources, the previous artifact is reinstalled and
launched. Edits under `app/` never trigger a rebuild; they're synced.

Force the toolchain with `--rebuild`. Stage without building with
`--prepare-only` (useful for opening the project in Xcode or Android
Studio).

If no dev server is running when you `pn run`, the CLI says so and
builds an app that runs its bundled sources without Fast Refresh.
Start `pn start` and relaunch to connect it.

## Which client for which job

| Task | Use |
|---|---|
| Layout, state, navigation, most component work | Browser preview |
| Anything touching device APIs (camera, location, haptics, biometrics) | Simulator or device |
| Text rendering, fonts, platform chrome, gesture feel | Simulator or device |
| Performance | A physical device |
| Demoing to someone at a desk | Browser preview on your own screen |

The browser preview runs your real Python in the `pn start` process and
shares Python reconciliation, hooks, and logical navigation with device
builds. Its renderer uses Yoga WebAssembly and DOM widgets, and
implements a subset of native modules (`Alert`, `Clipboard`, `Linking`,
`Share`, `Haptics`, `NetInfo`, `AppState`, `Device`); everything else
uses the pure-Python fallbacks in
[`pythonnative.native_modules.fallback`](../api/native_modules.md),
so a `Camera` call returns an "unavailable" result rather than a
photo.

## Logs and errors

Every dev client mirrors its Python output to the server, so the
`pn start` terminal is the one place to watch, and DevTools' Console
shows the same lines per app. Uncaught exceptions in renders, effects,
and handlers show the [development error screen](devtools.md#the-development-error-screen)
on the affected screen (on device and in the preview), with the
component stack and your source, and print the traceback in the
terminal.
Errors before any screen mounts (an `ImportError` in `app/main.py`,
say) print in the terminal and pop up in the preview's console; fix
the file and save to recover, nothing needs restarting.

`pn logs ios` / `pn logs android` still attach a native log stream
(`os_log`, `logcat`) when you need lower-level output than the dev
client mirrors.

## Dependencies

The browser preview imports your app in the `pn start` process, so any
package under `[requirements].packages` must be installed in the same
Python environment (`pip install` it, or run `uv run --with <pkg> pn
start`). `pn start` warns when one is missing. Device builds resolve
their own wheels from the same list; see [PyPI packages](pypi-packages.md).

## Profiling

Set `PN_PROFILE` to a writable file path before starting the Python process:

```bash
PN_PROFILE=/tmp/pythonnative-trace.json pn preview
```

Collection retains the latest 10,000 timing events and exports the trace at
normal process exit. The trace identifies rendered components and separates
Python preparation, acknowledgement, and native decode, queue, preflight,
mutation, and layout durations. Counters cover bridge bytes/operations, list
snapshot rows and patches, and mounted views. `Profiler.summary()` reports
retained-sample p50/p95/max durations, work counters, and gauges.

Setting `PN_PROFILE` here captures the preview's Python process; it doesn't
configure an environment variable inside a connected mobile app. To trace a
device, use **Record trace** in DevTools' Performance panel, which captures
the selected app and downloads the same trace format.

Run the reproducible headless work benchmark from the repository root:

```bash
python scripts/benchmark-rendering.py --rows 100000 --edits 20 > benchmark.json
```

It compares ordinary sequence replacement with `ListData`, asserts bounded
metadata and mounted-view work, and emits JSON. Timings include profiling and
aren't device frame-rate measurements or CI thresholds.

The runtime benchmark times `import pythonnative` in fresh interpreters,
element construction, a 300-component re-render, and commit preparation:

```bash
python scripts/benchmark-runtime.py --output runtime.json
```

Compare its numbers between changes on one machine. CI doesn't gate on them;
`tests/test_performance_budgets.py` instead checks the deterministic causes
of slowness (source parsing or contract derivation at import, eagerly loaded
subsystems, per-field render journaling, `inspect.Signature` binding, and
release-mode prop validation). On a device, a debug iOS build logs
`[PN] First screen attached ... ms after process start` once per launch.

For an explicit capture in a headless test:

```python
import pythonnative as pn
from pythonnative.profiling import Profiler
from pythonnative.testing import render


@pn.component
def App() -> pn.Node:
    return pn.Text("Profiled render")


with Profiler() as profiler:
    result = render(App())
    result.unmount()

profiler.export("trace.json")
```

The same context manager can surround work on the application's Python
thread in an embedded runtime. Choose an app-writable path when exporting
on a device. Open the resulting
Chrome trace in Perfetto or a compatible trace viewer. The profiler doesn't
retain component trees or application snapshots. Use Instruments on iOS and
Android's platform profiling tools for native frames, input, and scrolling.

## Next steps

- [Browser preview](browser-preview.md): device frames, dark mode,
  keyboard shortcuts, what's approximated.
- [Fast Refresh](hot-reload.md): what survives a reload, what
  doesn't, and why.
- [CLI reference](../api/cli.md) for every flag.
- [Dev server API](../api/devserver.md) if you want to script against
  the server or embed a client.
