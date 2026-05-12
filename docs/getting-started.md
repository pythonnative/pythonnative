# Getting Started

```bash
pip install pythonnative
pn --help
```

## Create a project

```bash
pn init MyApp
```

This scaffolds:

- `app/` with a minimal `main.py`
- `pythonnative.json` project config
- `requirements.txt`
- `.gitignore`

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
        pn.Button("Tap me", on_click=lambda: set_count(count + 1)),
        pn.Button("Open details", on_click=lambda: nav.navigate("Detail", {"count": count})),
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
            Stack.Screen("Home", HomeScreen, options={"title": "Home"}),
            Stack.Screen("Detail", DetailScreen, options={"title": "Detail"}),
            initial_route="Home",
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

## Run on a platform

```bash
pn run android
# or
pn run ios
```

- Uses bundled templates (no network required for scaffolding)
- Copies your `app/` into the generated project

If you just want to scaffold the platform project without building, use:

```bash
pn run android --prepare-only
pn run ios --prepare-only
```

This stages files under `build/` so you can open them in Android Studio or Xcode.

## Hot reload while developing

For day-to-day UI work, run with `--hot-reload`:

```bash
pn run android --hot-reload
pn run ios --hot-reload
```

The first run still builds and launches the native app. After that,
edits under `app/` are copied into the running app's writable source
overlay and the active page refreshes without a full rebuild.

PythonNative prefers a **Fast Refresh** path: each
[`@pn.component`][pythonnative.component] function is matched by
qualified name across the reloaded module, the live VNode tree's
function references are swapped in place, and the next render reuses
the existing hook state. So edits to the body of a component preserve
in-memory state (counters, scroll positions, etc.). When Fast Refresh
cannot find a clean swap — for example, after deeper structural
edits — PythonNative falls back to a full remount of the active page
so you never get stuck with a stale tree.

This works best for Python UI changes; native template changes
(Kotlin, Swift, manifests) still require a normal rebuild.

## Viewing logs

After the app launches, `pn run` attaches to the app's stdout/stderr so Python
`print()` output and tracebacks stream back into your terminal until you press
Ctrl+C:

```python
import pythonnative as pn


@pn.component
def App():
    count, set_count = pn.use_state(0)
    print(f"[App] render count={count}")
    return pn.Column(
        pn.Text(f"Count: {count}"),
        pn.Button("Tap me", on_click=lambda: set_count(count + 1)),
    )
```

- On Android, logs are streamed via `adb logcat` filtered to the
  `python.stdout` / `python.stderr` tags (that Chaquopy redirects `print()` to)
  plus the template's Kotlin tags.
- On iOS Simulator, the app is launched via `xcrun simctl launch --console-pty`,
  which forwards the Python process's standard streams to your terminal.

Pass `--no-logs` if you'd rather run fire-and-forget:

```bash
pn run android --no-logs
pn run ios --no-logs
```

## Clean

Remove the build artifacts safely:

```bash
pn clean
```
