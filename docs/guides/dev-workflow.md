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
  │  streams logs      │◄──────►│  iOS Simulator / Android     │
  │                    │        │  emulator (pn run)           │
  │                    │  ws    ┌──────────────────────────────┐
  │                    │◄──────►│  phone on the same Wi-Fi     │
  └────────────────────┘        └──────────────────────────────┘
```

## The two-terminal setup

Terminal one runs the dev server for the whole session:

```bash
pn start          # dev server only
pn preview        # dev server and open the browser preview
```

Terminal two builds and launches a debug app whenever you need one:

```bash
pn run ios
pn run android
```

`pn run` finds the dev server on `localhost:8765` (`--port` to change
it), bakes the server's URL into the debug build, installs it, and
launches. The app connects on startup, pulls any sources newer than
what it shipped with, and from then on Fast Refreshes on every save.
Its `print()` output, tracebacks, and reload notices stream back to the
`pn start` terminal, so you can leave `pn run` and keep working from one
window.

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

Logs from every peer are interleaved in the terminal and prefixed with
the source: `[ios iPhone 15]`, `[android Pixel 8]`, `[browser]`, and
`[pn]` for the server's own messages.

Endpoints, for scripting and curiosity:

| Path | Purpose |
|---|---|
| `GET /` | Browser preview page |
| `GET /status` | Server, project, and connected-peer info (JSON) |
| `GET /manifest` | `{"version", "entry", "files": {path: sha256}}` |
| `GET /file/<path>` | Raw bytes of one synced source file |
| `WS /ws?role=client` | Dev-client protocol |
| `WS /ws?role=preview` | Browser preview bridge channel |

### Flags

```bash
pn start [entry] [--port 8765] [--host 0.0.0.0] [--open]
pn preview [entry] [--port 8765] [--host 0.0.0.0] [--no-open]
```

`entry` overrides the entry module from `pythonnative.toml` (for
example `app.screens.settings` to mount one screen's `App`). The server
binds to all interfaces by default so phones on your network can reach
it; pass `--host 127.0.0.1` to keep it local.

## Dev clients

A **dev client** is a debug build of your app. On launch,
`pythonnative.bootstrap.start(dev=True)` calls
[`devclient.start_if_configured`][pythonnative.devclient.start_if_configured],
which:

- reads the server URL the CLI baked in (`PN_DEV_SERVER`), or the one
  saved from the last session;
- connects over WebSocket on a daemon thread and says `hello` with a
  hash of every source it holds in its writable **overlay**. On the
  first launch the overlay is seeded from the sources bundled in the
  build, so a build made from the current tree reports everything
  up to date;
- receives a `sync` with only the files that differ, writes them into
  the overlay (which sits ahead of the bundled sources on `sys.path`),
  and applies a Fast Refresh for the modules that changed. Nothing
  changed, nothing reloads;
- mirrors `print`, warnings, and tracebacks to the server;
- reports every reload (`fast_refresh` or `remount`, and which modules).

Release builds never include any of this: `pn build` produces a
standalone app with your sources bundled and no dev client.

### Simulators and emulators

`pn run ios` and `pn run android` handle the URL plumbing. The iOS
Simulator shares the Mac's loopback interface, so `localhost` works.
For Android the CLI runs `adb reverse` so `localhost:8765` inside the
emulator (or a USB-attached phone) reaches the server.

### Physical iPhones

A physical iOS device is on your Wi-Fi rather than your loopback, so
`pn run ios --device <name>` bakes in the Mac's first LAN address
instead. Both machines must be on the same network and the port must
not be firewalled. If auto-detection picks the wrong interface, pass
the URL explicitly:

```bash
pn run ios --device "Owen's iPhone" --dev-server ws://192.168.1.20:8765/ws?role=client
```

Fast Refresh works the same over Wi-Fi; there's no longer a USB-only
path.

### The dev-client shell app

Sometimes you want one installed app that can load *any* project, the
way Expo Go does. Build a shell with:

```bash
pn run ios --dev-client
pn run android --dev-client
```

The shell has no app of its own. It opens a
[`ConnectScreen`][pythonnative.devclient.ConnectScreen] where you type
a dev server URL (the last one used is prefilled). After the first sync the real
`app.main` from the overlay shadows the placeholder and the screen
remounts into your app. The URL is remembered for next launch, so a
shell built once keeps working across projects as long as their native
inputs (native plugins, `[requirements].packages`, permissions) are the
same.

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
| Demoing to someone at a desk | Browser preview (`--host` and share the URL) |

The browser preview runs your real Python in the `pn start` process and
uses the same reconciler, layout engine, hooks, and navigation as
device builds. It approximates leaf widgets with DOM elements and
implements a subset of native modules (`Alert`, `Clipboard`, `Linking`,
`Share`, `Haptics`, `NetInfo`, `AppState`, `Device`); everything else
uses the pure-Python fallbacks in
[`pythonnative.native_modules.fallback`](../api/native_modules.md),
so a `Camera` call returns an "unavailable" result rather than a
photo.

## Logs and errors

Every dev client mirrors its Python output to the server, so the
`pn start` terminal is the one place to watch. Uncaught exceptions in
renders, effects, and handlers show a RedBox on the affected screen
(on device and in the preview) and print the traceback in the terminal.
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

## Next steps

- [Browser preview](browser-preview.md): device frames, dark mode,
  keyboard shortcuts, what's approximated.
- [Fast Refresh](hot-reload.md): what survives a reload, what
  doesn't, and why.
- [CLI reference](../api/cli.md) for every flag.
- [Dev server API](../api/devserver.md) if you want to script against
  the server or embed a client.
