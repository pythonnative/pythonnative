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

The generated `app/main.py` is a small, typed app with two screens:

```python
import pythonnative as pn


class Styles:
    def __init__(self, theme: pn.Theme) -> None:
        self.screen = pn.style(padding=theme.spacing.md, gap=theme.spacing.md, align_items="stretch")
        self.title: pn.Style = {**theme.typography.title, "color": theme.colors.text}
        self.body: pn.Style = {**theme.typography.body, "color": theme.colors.text}


@pn.component
def HomeScreen() -> pn.Node:
    count, set_count = pn.use_state(0)
    nav = pn.use_navigation()
    styles = pn.use_styles(Styles)
    return pn.ScrollView(
        pn.Column(
            pn.Text("Hello from PythonNative!", style=styles.title),
            pn.Text(f"Tapped {count} times", style=styles.body),
            pn.Button("Tap me", on_press=lambda: set_count(count + 1)),
            pn.Button("Open detail", on_press=lambda: nav.push(DetailScreen(count=count))),
            style=styles.screen,
        )
    )


@pn.component
def DetailScreen(count: int) -> pn.Node:
    nav = pn.use_navigation()
    styles = pn.use_styles(Styles)
    return pn.Column(
        pn.Text(f"The count was {count}", style=styles.body),
        pn.Button("Back", on_press=nav.go_back),
        style=styles.screen,
    )


Root = pn.StackNavigator(
    pn.Screen(HomeScreen, title="Home"),
    pn.Screen(DetailScreen, title="Detail"),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root)
```

Key ideas:

- **`@pn.component`** marks a function as a PythonNative component. The function returns an element tree (a `pn.Node`) describing the UI, and PythonNative creates and updates native views to match. Its parameters are its props, so your type checker verifies every call.
- **`pn.use_state(initial)`** creates local component state. Call the setter to update it and the UI re-renders automatically.
- **Screens are components.** `DetailScreen(count: int)` declares its route params as ordinary parameters, and `nav.push(DetailScreen(count=count))` navigates to it with a checked call. See [Navigation](guides/navigation.md).
- **`pn.StackNavigator(...)`** is a module-level value listing the screens. `pn.NavigationContainer(Root)` renders it and makes [`pn.use_navigation()`][pythonnative.use_navigation] available in every screen.
- **The `Styles` class** derives styles from the active [`Theme`][pythonnative.Theme]'s tokens. [`pn.use_styles(Styles)`][pythonnative.use_styles] builds it once per theme, so the app follows the system's light and dark appearance. See [Styling](guides/styling.md).
- **The `App` function** is the entry point. The Android and iOS templates import `app.main`, look up its top-level `App` attribute, and start rendering. If you'd rather expose a differently-named component, configure your templates to load an explicit dotted path like `"app.main.RootScreen"`.
- Element functions like `pn.Text(...)`, `pn.Button(...)`, and `pn.Column(...)` create lightweight descriptions, not native objects.

On a device, the root stack drives the **native** navigation controller (`UINavigationController` on iOS, fragments on Android). Every screen stays part of one Python component tree, so providers and state above the navigator are shared, and the previous screen keeps its state while another is pushed on top.

The scaffold passes strict type checking and `pn lint`, which checks the [rules of hooks](concepts/hooks.md#rules-of-hooks):

```bash
pn lint
```

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
browser (the URL carries your per-user
[dev token](guides/dev-workflow.md#the-dev-token) once), and mounts your project's `App` in a phone frame. It **Fast
Refreshes on every save**: edit a component, save, and the page updates
in place while keeping component state (counters, form input, scroll
position, the navigation stack). Your components, hooks, async work, and
logical navigation use the shared Python runtime. The page speaks the
same bridge protocol as the mobile renderers, implements widgets with DOM
elements, and computes layout with Yoga WebAssembly.

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
dev server on `localhost:8765`, passes its URL and your dev token to
the app, and the app connects on startup. From then on it's a **dev client**: every save
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
--device "My iPhone"`); the CLI passes your Mac's LAN address instead
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
def App() -> pn.Node:
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
