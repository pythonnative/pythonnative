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
- `pyproject.toml`, which pins this `pythonnative` version and declares
  `pytest` and `mypy` for development
- `tests/test_app.py`, a test that renders the app headlessly with
  [`pythonnative.testing`](guides/testing.md); run it with `pytest`
- `.vscode/launch.json`, the [debugger](guides/debugging.md)
  configuration, and `.vscode/extensions.json`
- `.github/workflows/ci.yml`, which runs `pn lint`, `mypy`, and `pytest`
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
pn start
```

It prints a QR code, the URLs of the browser preview and DevTools, and
the debugger's address, then waits for single-key commands. From here
there are three ways to see your app.

### On a simulator or emulator, without building

Press ++i++ for the iOS Simulator or ++a++ for an Android emulator.
`pn start` installs [PythonNative Go](guides/devtools.md#pythonnative-go),
a prebuilt app that runs any PythonNative project without native code,
and opens your project in it. No Xcode or Gradle build runs. (The first
time, `pn` downloads Go for your version; in a development checkout of
PythonNative it builds Go once instead.)

### On your phone

Install Go on the phone (`pn go android --device <serial>` over USB, or
`pn go ios --device "My iPhone"`, which signs it with your
`[ios].development_team`), then scan the QR code with the phone's camera.
The phone and your computer must be on the same Wi-Fi.

### In the browser

Press ++w++, or start with `pn preview` instead. The browser preview
mounts your project's `App` in a phone frame. It's a **development**
surface for layout and logic; platform chrome is approximated and device
APIs are simulated. See the [Browser preview guide](guides/browser-preview.md).

Every one of these **Fast Refreshes on every save**: edit a component,
save, and the app updates in place while keeping component state
(counters, form input, scroll position, the navigation stack). Logs and
tracebacks from every app stream back into the `pn start` terminal.
Press ++question++ for the other commands, and see the
[Development workflow](guides/dev-workflow.md).

## Debug, inspect, and measure

- **The dev menu.** Shake the device, press ++cmd+d++ in the iOS
  Simulator or ++cmd+m++ in the Android emulator, or press ++m++ in `pn
  start`. It reloads the app and turns on the element inspector and the
  performance monitor. See [PythonNative Go and DevTools](guides/devtools.md).
- **DevTools.** Press ++j++ for the component tree with props and hooks,
  a console with a REPL inside the running app, problems with component
  stacks, network requests, and performance.
- **Breakpoints.** Run the **PythonNative: Attach** configuration in VS
  Code and set breakpoints in `app/`; they bind on the device. See
  [Debugging](guides/debugging.md).

## Build your own development app

Go doesn't contain native code your project adds: native plugins, or
packages with compiled extensions such as `numpy`. Such a project runs in
its own debug build, which `pn start` builds for you when you press ++i++
or ++a++. To build it directly, with the dev server still running:

```bash
pn run android
# or
pn run ios
```

`pn run` stages the bundled native template, copies your `app/` in,
builds a debug app, installs it, and opens it with a link to the dev
server. From then on it behaves like Go: every save under `app/` syncs to
the device and Fast Refreshes.

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
