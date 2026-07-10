# Navigation

PythonNative navigation is **declarative** and **native-backed**:

- You describe your screens once as a `Stack.Navigator` (or `Tab` /
  `Drawer`) tree.
- At the root of your app, the stack delegates to the platform's
  native navigation controller: `UINavigationController` on iOS and
  the AndroidX Navigation Component on Android.
- Each pushed screen runs in its own reconciler host, so the screen
  you came from is preserved by the platform (including scroll
  offsets, animations, gesture-driven back transitions).

Nested navigators (tabs inside a stack, or stacks inside tabs) are
managed entirely in Python; only the outermost stack delegates to
the host. The same `pn.use_navigation()` and `pn.use_route()` hooks
work everywhere.

## Declarative navigation

Save a module at `app/main.py` that defines an `App` component
wrapping a navigator in
[`NavigationContainer`][pythonnative.NavigationContainer]:

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()


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

The native templates (Android `ScreenFragment`, iOS `ViewController`)
import `app.main` and look up its top-level `App` attribute, so no
other wiring is required. `options={"title": ...}` propagates to the
native navigation bar.

### Stack navigator

A stack navigator manages a stack of screens; push to go forward, pop
to go back. At the root, push/pop run on the **native** navigation
controller; nested stacks manage their own state in Python.

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen, options={"title": "Home"}),
            Stack.Screen("Detail", DetailScreen, options={"title": "Detail"}),
            initial_route="Home",
        )
    )


@pn.component
def HomeScreen():
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Home", style={"font_size": 24}),
        pn.Button(
            "Go to Detail",
            on_press=lambda: nav.navigate("Detail", params={"id": 42}),
        ),
        style={"spacing": 12, "padding": 16},
    )

@pn.component
def DetailScreen():
    nav = pn.use_navigation()
    params = nav.get_params()
    return pn.Column(
        pn.Text(f"Detail #{params.get('id')}", style={"font_size": 20}),
        pn.Button("Back", on_press=nav.go_back),
        style={"spacing": 12, "padding": 16},
    )
```

### Tab navigator

A tab navigator renders a **native tab bar** and switches between
screens. On Android the tab bar is a `BottomNavigationView` from
Material Components; on iOS it is a `UITabBar`.

```python
Tab = pn.create_tab_navigator()


@pn.component
def App():
    return pn.NavigationContainer(
        Tab.Navigator(
            Tab.Screen("Home", HomeScreen, options={"title": "Home"}),
            Tab.Screen("Settings", SettingsScreen, options={"title": "Settings"}),
        )
    )
```

The tab bar emits a `TabBar` element that maps to platform-native views:

| Platform | Native view                  |
|----------|------------------------------|
| Android  | `BottomNavigationView`       |
| iOS      | `UITabBar`                   |

### Drawer navigator

A drawer navigator provides a side menu for switching screens.

```python
Drawer = pn.create_drawer_navigator()


@pn.component
def App():
    return pn.NavigationContainer(
        Drawer.Navigator(
            Drawer.Screen("Home", HomeScreen, options={"title": "Home"}),
            Drawer.Screen("Profile", ProfileScreen, options={"title": "Profile"}),
        )
    )


@pn.component
def HomeScreen():
    nav = pn.use_navigation()
    return pn.Column(
        pn.Button("Open Menu", on_press=nav.open_drawer),
        pn.Text("Home Screen"),
    )
```

### Nesting navigators

Navigators can be nested (for example, tabs containing stacks). When a
child navigator receives a `navigate()` call for an unknown route, it
automatically **forwards** the request to its parent navigator.
Similarly, `go_back()` at the root of a child stack forwards to the
parent.

Nested navigators stay in Python; only the outermost stack delegates
to the native navigation controller. This is the right default: tab
switches should be cheap, in-process, and reuse already-mounted
screens, while top-level pushes deserve a native navigation
controller, swipe-to-go-back, and proper state restoration.

```python
Stack = pn.create_stack_navigator()
Tab = pn.create_tab_navigator()


@pn.component
def MainTabs():
    return Tab.Navigator(
        Tab.Screen("Home", HomeScreen, options={"title": "Home"}),
        Tab.Screen("Settings", SettingsScreen, options={"title": "Settings"}),
    )


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Tabs", MainTabs, options={"title": "Home"}),
            Stack.Screen("Detail", DetailScreen, options={"title": "Detail"}),
        )
    )
```

Inside `HomeScreen`, calling `nav.navigate("Detail")` walks up to the
root `Stack.Navigator`, which pushes a fresh native screen.
`nav.navigate("Settings")` from inside `DetailScreen` walks up to the
`Tab.Navigator` (after popping back) and switches tabs.

## NavigationHandle API

Inside any screen rendered by a navigator,
[`use_navigation`][pythonnative.use_navigation] returns a handle with:

- **`.navigate(route_name, params=...)`**: navigate to a named route
  with optional params.
- **`.go_back()`**: pop the current screen.
- **`.get_params()`**: get the current route's params dict.
- **`.reset(route_name, params=...)`**: reset the stack to a single
  route.

### Drawer-specific methods

When inside a drawer navigator, the handle also provides:

- **`.open_drawer()`**: open the drawer.
- **`.close_drawer()`**: close the drawer.
- **`.toggle_drawer()`**: toggle the drawer open/closed.

## Focus-aware effects

Use [`use_focus_effect`][pythonnative.use_focus_effect] to run effects
only when a screen is focused:

```python
@pn.component
def DataScreen():
    data, set_data = pn.use_state(None)

    pn.use_focus_effect(lambda: fetch_data(set_data), [])

    return pn.Text(f"Data: {data}")
```

## Route parameters

Use [`use_route`][pythonnative.use_route] for convenient access to
route params:

```python
@pn.component
def DetailScreen():
    params = pn.use_route()
    item_id = params.get("id", 0)
    return pn.Text(f"Item #{item_id}")
```

## Lifecycle

PythonNative forwards lifecycle events from the host:

- `on_create`: triggers the initial render.
- `on_start`.
- `on_resume`.
- `on_pause`.
- `on_stop`.
- `on_destroy`.
- `on_restart` (Android only).
- `on_save_instance_state`.
- `on_restore_instance_state`.

## Platform specifics

### iOS (UIViewController per screen)
- Each pushed screen is a Swift `ViewController` instance with its
  own Python `_ScreenHost` and reconciler.
- Screens are pushed and popped on a root `UINavigationController`
  set up by the template's `SceneDelegate`.
- The declarative `Stack.Navigator` delegates to
  `nav.pushViewController_animated_` / `popViewControllerAnimated_`
  and the initial-route name is forwarded via the host's
  `requestedScreenPath` / `requestedScreenArgsJSON` properties.
- Screen `options.title` is applied via `UIViewController.title`,
  which the surrounding `UINavigationController` picks up.

### Android (single Activity, Fragment stack)
- The host `MainActivity` embeds a `NavHostFragment` containing a
  navigation graph with a single generic `ScreenFragment` destination.
- Each pushed screen is a fresh `ScreenFragment` instance with its own
  Python `_ScreenHost` and reconciler; arguments live in Fragment
  arguments (`screen_path` / `args_json`) and restore across
  configuration changes.
- Push/pop delegate to `NavController` through a small `Navigator`
  Kotlin helper, including `popToRoot` for `Stack.reset(...)`.
- Screen `options.title` is forwarded to `Activity.setTitle`.

### Why per-screen hosts?

Pushing onto a native stack is most useful when the new screen does
not have to re-bootstrap Python or re-run the whole tree. Each
pushed view-controller / fragment owns its own Python `_ScreenHost`,
so:

- The previous screen's reconciler stays alive in memory; its hook
  state and native views are preserved by the platform stack.
- The new screen's `_ScreenHost` resolves its initial route from the
  arguments passed by the parent's `navigate(...)` call, so the
  declarative `Stack.Navigator` always renders the right screen on
  the first frame.
- Hot reload runs **per host**: each active screen swaps its
  function references in place ("Fast Refresh") and only the screens
  that cannot be refreshed cleanly fall back to a full remount.

## Comparison to other frameworks

- **React Native**. Android: single `Activity`, screens managed via
  `Fragment`s. iOS: screens map to `UIViewController`s pushed on
  `UINavigationController`.
- **NativeScript**. Android: single `Activity`, pages as `Fragment`s.
  iOS: pages as `UIViewController`s on `UINavigationController`.
- **Flutter**. Android: single `Activity`. iOS:
  `FlutterViewController` hosts Flutter's navigator.

## Next steps

- See worked navigation examples: [Examples/Navigation](../examples/navigation.md).
- Browse the API: [Navigation](../api/navigation.md).
- Learn how focus interacts with effects: [Lifecycle](../concepts/lifecycle.md).
