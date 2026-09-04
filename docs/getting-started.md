# Getting Started

PythonNative requires Python 3.13 or newer on your development
machine: the same interpreter version your app embeds, so packages
resolve identically on both.

```bash
pip install pythonnative
pn --help
```

## Create a project

```bash
pn init my_app
cd my_app
```

This creates a `my_app/` directory containing:

- `app/` with a minimal `main.py`
- `pythonnative.toml`: your project configuration (app id, version,
  permissions, assets, and signing). See
  [Configuration](guides/configuration.md).
- `.gitignore`

A name has to be lowercase letters, digits, `-`, and `_`, starting with
a letter, so the directory name and the `name` field in the generated
config stay identical. Run `pn init` without a name to scaffold into the
current directory instead, named after it; that name is used as-is.

A minimal `app/main.py` looks like:

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()


@pn.component
def HomeScreen():
    nav = pn.use_navigation()
    count, set_count = pn.use_state(0)
    return pn.Column(
        pn.Text(f"Count: {count}", style={"font_size": 24}),
        pn.Button("Tap me", on_press=lambda: set_count(count + 1)),
        pn.Button("Open details", on_press=lambda: nav.navigate("Detail", count=count)),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def DetailScreen():
    route = pn.use_route()
    return pn.Text(f"Count was {route.params.get('count', 0)}", style={"padding": 16})


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen, title="Home"),
            Stack.Screen("Detail", DetailScreen, title="Detail"),
        )
    )
```

Key ideas:

- **`@pn.component`** marks a function as a PythonNative component. The function returns an element tree describing the UI. PythonNative creates and updates native views automatically.
- **`pn.use_state(initial)`** creates local component state. Call the setter to update it and the UI re-renders automatically.
- **`pn.create_stack_navigator()`** returns a `Stack` with `.Navigator` and `.Screen` factories. Wrap them in `pn.NavigationContainer` to enable [`pn.use_navigation()`][pythonnative.use_navigation] and [`pn.use_route()`][pythonnative.use_route] anywhere below.
- **The `App` function** is the entry point. The Android and iOS templates import `app.main`, look up its top-level `App` attribute, and start rendering. If you'd rather expose a differently-named component, configure your templates to load an explicit dotted path like `"app.main.RootScreen"`.
- **`style={...}`** passes visual and layout properties as a dict (or list of dicts) to any component.
- Element functions like `pn.Text(...)`, `pn.Button(...)`, `pn.Column(...)` create lightweight descriptions, not native objects.

When the root `Stack.Navigator` is rendered inside the host's first screen, `navigate(...)` and `go_back()` drive the **native** navigation controller (UINavigationController on iOS, AndroidX Navigation Component on Android). Each pushed screen runs in its own reconciler host, so state on the previous screen is preserved by the platform stack.

## Configure your app

Everything about your app's *identity* (its bundle/application id,
display name, version, the device permissions it requests, its icon and
splash, third-party packages, and signing) lives in a single
`pythonnative.toml` at the project root:

```toml
[app]
id = "com.example.my_app"
name = "my_app"
display_name = "My App"
version = "1.0.0"
build = 1

[permissions]
camera = "Scan receipts with your camera."
notifications = true

[assets]
icon = "assets/icon.png"
```

The build system reads this file for every command, so `pn run`,
`pn build`, `pn doctor`, and `pn app-id` all stay in sync. See the full
[Configuration reference](guides/configuration.md) and the
[Permissions guide](guides/permissions.md).

## Start the dev server

Everything during development goes through one long-running process,
the dev server. Start it in a terminal and leave it running:

```bash
pn preview
```

`pn preview` starts the server, opens `http://localhost:8765/` in your
browser, and mounts your project's `App` in a phone frame. It **Fast
Refreshes on every save**: edit a component, save, and the page updates
in place while keeping component state (counters, form input, scroll
position, the navigation stack). Navigation, hooks, async, and the flex
layout engine run exactly as they do on device, because the page is a
bridge peer like the Swift and Kotlin runtimes and reuses the same
reconciler and screen host; only the leaf widgets differ (DOM elements
instead of UIKit / Android views).

```bash
pn preview                    # server + browser tab for app/main.py -> App
pn preview app.screens.home   # mount a different module's App
pn start                      # the server without opening a browser
```

Use the toolbar to switch device frames, rotate, toggle dark mode, or
send a back press. The preview is a **development** surface for layout
and logic; platform chrome is approximated and device APIs are
simulated. Ship to devices with `pn run`. See the
[Browser preview guide](guides/browser-preview.md).

## Run on a device or simulator

With the dev server still running, in a second terminal:

```bash
pn run android
# or
pn run ios
```

`pn run` stages the bundled native template, copies your `app/` in,
builds a debug app, installs it, and launches it. The CLI finds the
dev server on `localhost:8765`, bakes its URL into the build, and the
app connects on startup. From then on it's a **dev client**: every save
under `app/` syncs to the device and Fast Refreshes the running screens,
and the app's `print` output and tracebacks stream back into the
`pn start` terminal.

Rerunning `pn run` is cheap. The native toolchain only runs when a
native input changed (`pythonnative.toml`, the template, the
`pythonnative` package, native plugins); otherwise the previous build
is reinstalled in seconds. Force a rebuild with `--rebuild`.

If you just want to scaffold the platform project without building, use:

```bash
pn run android --prepare-only
pn run ios --prepare-only
```

This stages files under `build/` so you can open them in Android Studio or Xcode.

Physical iPhones on the same Wi-Fi work the same way (`pn run ios
--device "My iPhone"`); the CLI bakes in your Mac's LAN address instead
of `localhost`. See the [Development workflow](guides/dev-workflow.md)
for the details, including the reusable `--dev-client` shell app.

Native template changes (Kotlin, Swift, manifests) and edits to
`pythonnative.toml` still require a rebuild; `pn run` detects them and
runs the toolchain automatically.

## Viewing logs

A connected dev client mirrors its Python `print()` output, warnings,
and tracebacks to the `pn start` terminal, so that one window shows
every client. `pn run` also attaches to the app's native log stream
after launch until you press Ctrl+C, which is where lower-level output
(and anything printed before the client connects) shows up:

```python
import pythonnative as pn


@pn.component
def App():
    count, set_count = pn.use_state(0)
    print(f"[App] render count={count}")
    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Button("Tap me", on_press=lambda: set_count(count + 1)),
    )
```

- On Android, logs are streamed via `adb logcat` filtered to the
  `python.stdout` / `python.stderr` tags (that Chaquopy redirects `print()` to)
  plus the `PythonNative` tag the Kotlin runtime logs under.
- On iOS Simulator, the app is launched via `xcrun simctl launch --console-pty`,
  which forwards the Python process's standard streams to your terminal.

Pass `--no-logs` if you'd rather run fire-and-forget:

```bash
pn run android --no-logs
pn run ios --no-logs
```

## Check your toolchain

Before your first build, run `pn doctor` to verify the local toolchain
(Java/Android SDK for Android; Xcode/Simulator and a signing team for
iOS) and validate your `pythonnative.toml`:

```bash
pn doctor            # check everything
pn doctor android    # only Android-relevant checks
pn doctor ios        # only iOS-relevant checks
```

It prints `[ok]` / `[!]` / `[x]` for each check and exits non-zero when
something will block a build, so it's safe to run in CI.

## Build for release

When you're ready to ship, `pn build` produces signed, distributable
artifacts:

```bash
pn build android     # release APK + AAB
pn build ios         # signed .ipa via xcodebuild archive/export
```

Release builds need signing configured in `pythonnative.toml` (a
keystore for Android, a development team for iOS). See
[Building for release](guides/building-for-release.md) for the full
walkthrough.

## Clean

Remove the build artifacts safely:

```bash
pn clean
```
