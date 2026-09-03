# Navigation

PythonNative navigation follows React Navigation's shape, so the
mental model carries over directly:

- You describe screens once as a `Stack.Navigator` (or `Tab` /
  `Drawer`) tree inside a
  [`NavigationContainer`][pythonnative.NavigationContainer].
- Screens call [`use_navigation`][pythonnative.use_navigation] for an
  imperative [`Navigation`][pythonnative.Navigation] handle and
  [`use_route`][pythonnative.use_route] for their params.
- Navigation state is a plain, serializable value
  ([`NavigationState`][pythonnative.navigation.NavigationState]), so it
  can be persisted, restored, and deep-linked.

The one thing React Navigation can't do: at the root of the app, the
stack is **native-backed**. Pushing a screen pushes a real
`UIViewController` on iOS or a `Fragment` on Android, so you get the
platform's transitions, swipe-back, and state preservation for free.
Nested navigators (tabs inside a stack, stacks inside tabs) are drawn
in Python and keep their screens mounted between switches.

## A complete example

Save a module at `app/main.py` that defines an `App` component:

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()


@pn.component
def HomeScreen():
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Home", style={"font_size": 24}),
        pn.Button("Open item 42", on_press=lambda: nav.navigate("Detail", id=42)),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def DetailScreen():
    nav = pn.use_navigation()
    route = pn.use_route()
    return pn.Column(
        pn.Text(f"Detail #{route.params['id']}", style={"font_size": 20}),
        pn.Button("Back", on_press=nav.go_back),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen, title="Home"),
            Stack.Screen(
                "Detail",
                DetailScreen,
                options=lambda route: {"title": f"Item {route.params['id']}"},
            ),
        )
    )
```

The native templates (Android `ScreenFragment`, iOS `ViewController`)
import `app.main` and look up its top-level `App`, so no other wiring
is required. `title` propagates to the native navigation bar.

`Screen(name, component, ...)` accepts every key of
[`ScreenOptions`][pythonnative.ScreenOptions] as a keyword, an
`options=` dict, or an `options=lambda route: {...}` callable for
options that depend on params. Keywords merge on top of `options`.

## Navigators

### Stack

A stack keeps a history. `navigate` goes to a screen (switching back to
it if it's already in the history), `push` always adds a new instance,
and `pop` / `go_back` return.

```python
Stack = pn.create_stack_navigator()

Stack.Navigator(
    Stack.Screen("Home", HomeScreen, title="Home"),
    Stack.Screen("Detail", DetailScreen, initial_params={"id": 0}),
    Stack.Screen("Settings", SettingsScreen, presentation="modal"),
    initial_route="Home",
)
```

At the root of a native host the stack pushes native screens; nested
stacks are drawn in Python with a header (title, back button, and the
`header_left` / `header_right` slots). Screens beneath the top stay
mounted with their state, so popping back restores scroll position and
inputs.

### Tabs

Tabs render a native tab bar (`UITabBar` on iOS, Material
`BottomNavigationView` on Android). Visited tabs stay mounted and
hidden, so switching back is instant and keeps state.

```python
Tab = pn.create_tab_navigator()

Tab.Navigator(
    Tab.Screen("Home", HomeScreen, title="Home", tab_bar_icon={"ios": "house.fill", "android": "ic_menu_compass"}),
    Tab.Screen("Inbox", InboxScreen, tab_bar_label="Inbox", tab_bar_badge=3),
    Tab.Screen("Settings", SettingsScreen, lazy=False),
    Tab.Screen("Camera", CameraScreen, unmount_on_blur=True),
)
```

- `lazy` (default `True`) mounts a tab the first time it's focused.
  `lazy=False` mounts it with the navigator.
- `unmount_on_blur=True` tears a tab down when it loses focus, for
  screens that hold expensive resources.

Inside a tab screen, `use_navigation()` returns a
[`TabNavigation`][pythonnative.navigation.TabNavigation] with
`jump_to(name, **params)`.

### Drawer

A drawer is like tabs with a slide-in menu instead of a tab bar.

```python
Drawer = pn.create_drawer_navigator()

Drawer.Navigator(
    Drawer.Screen("Feed", FeedScreen, title="My Feed"),
    Drawer.Screen("Profile", ProfileScreen, title="Profile"),
    drawer_width=280,
)


@pn.component
def FeedScreen():
    nav = pn.use_navigation()  # a DrawerNavigation
    return pn.Column(
        pn.Button("Menu", on_press=nav.open_drawer),
        pn.Text("Feed"),
    )
```

[`DrawerNavigation`][pythonnative.navigation.DrawerNavigation] adds
`open_drawer()`, `close_drawer()`, `toggle_drawer()`, and
`is_drawer_open()`. The system back action closes an open drawer
before it does anything else.

## The `Navigation` handle

[`use_navigation`][pythonnative.use_navigation] returns the
[`Navigation`][pythonnative.Navigation] handle for the *current
screen*. Route names come first; params are keyword arguments.

```python
nav.navigate("Detail", id=42)       # go to Detail (back to it if it's in the history)
nav.push("Detail", id=43)           # always push a new Detail
nav.replace("Login")                # swap the current screen
nav.pop()                           # back one screen (also nav.go_back())
nav.pop(2)                          # back two
nav.pop_to_top()                    # back to the first screen
nav.reset("Home")                   # replace the whole history
nav.reset(pn.Route("Home"), pn.Route("Detail", {"id": 1}))
nav.set_params(id=44)               # merge params into this screen's route
nav.set_options(title="Edited")     # change ScreenOptions at runtime
```

Introspection: `nav.route`, `nav.get_params()`, `nav.get_options()`,
`nav.get_state()`, `nav.get_parent()`, `nav.can_go_back()`,
`nav.is_focused()`, and `nav.kind` (`"stack"`, `"tab"`, or
`"drawer"`).

### Listeners

```python
@pn.component
def EditScreen():
    nav = pn.use_navigation()
    dirty, set_dirty = pn.use_state(False)

    def guard():
        def on_before_remove(event):
            if dirty:
                event.prevent_default()
                pn.Alert.show("Discard changes?", "You have unsaved edits.")

        return nav.add_listener("before_remove", on_before_remove)

    pn.use_effect(guard, [dirty])
    ...
```

Events are `"focus"`, `"blur"`, `"before_remove"` (call
`event.prevent_default()` to keep the screen), and `"state"` (fired
with the navigator's new state). `add_listener` returns an unsubscribe
callable, so it slots straight into `use_effect`.

Native back gestures on iOS can't be intercepted by `before_remove`;
set `gesture_enabled=False` on screens that need a guard.

## Route params

[`use_route`][pythonnative.use_route] returns the current
[`Route`][pythonnative.navigation.Route]: `route.name`,
`route.params`, and a stable `route.key` for this visit.

```python
@pn.component
def DetailScreen():
    route = pn.use_route()
    return pn.Text(f"Item #{route.params.get('id', 0)}")
```

`initial_params` on `Screen(...)` fill in defaults; `navigate` /
`push` params merge on top.

## Focus

[`use_is_focused`][pythonnative.use_is_focused] is `True` only for the
visible screen: inactive tabs, screens beneath the top of a stack, and
screens covered by a pushed native screen all read `False`.
[`use_focus_effect`][pythonnative.use_focus_effect] runs an effect
while focused and runs its cleanup on blur:

```python
@pn.component
def Feed():
    def start_polling():
        timer = schedule_refresh()
        return timer.cancel

    pn.use_focus_effect(start_polling, [])
    ...
```

## Nesting

Navigators nest freely. A request the current navigator can't satisfy
bubbles to its parent: `navigate("Settings")` from deep inside one tab
switches tabs, and `go_back()` at the bottom of a nested stack pops the
outer one.

```python
Root = pn.create_stack_navigator()
Tabs = pn.create_tab_navigator()


@pn.component
def MainTabs():
    return Tabs.Navigator(
        Tabs.Screen("Home", HomeScreen, title="Home"),
        Tabs.Screen("Profile", ProfileScreen, title="Profile"),
    )


@pn.component
def App():
    return pn.NavigationContainer(
        Root.Navigator(
            Root.Screen("Tabs", MainTabs, header_shown=False),
            Root.Screen("Detail", DetailScreen),
        )
    )
```

To land on a specific screen inside a nested navigator, pass
`screen=`; the remaining params go to that screen:

```python
nav.navigate("Tabs", screen="Profile", user="ada")
```

## State, persistence, and deep links

The container reports every state change and accepts an initial state,
so persisting navigation is a few lines:

```python
@pn.component
def App():
    saved, set_saved = pn.use_persisted_state("nav", None)
    return pn.NavigationContainer(
        Root.Navigator(...),
        initial_state=saved,
        on_state_change=lambda state: set_saved(state.to_dict()),
    )
```

`initial_state` accepts a `NavigationState` or its `to_dict()` form.
State restored by the native host (a pushed native screen re-entering
Python) takes precedence, then `initial_state`, then the launch URL.

Deep links map URLs to states with
[`LinkingConfig`][pythonnative.LinkingConfig]:

```python
linking = pn.LinkingConfig(
    prefixes=["myapp://", "https://example.com"],
    screens={
        "Tabs": {
            "path": "",
            "screens": {"Home": "home", "Profile": "u/:user"},
        },
        "Detail": {"path": "item/:id", "parse": {"id": int}},
    },
)

pn.NavigationContainer(Root.Navigator(...), linking=linking)
```

`myapp://item/42?ref=mail` opens `Detail` with
`{"id": 42, "ref": "mail"}`; `https://example.com/u/ada` opens the
`Profile` tab. The URL that launched the app seeds the initial state,
and URLs that arrive while running dispatch as `navigate` calls.
`linking.url_from_state(state)` goes the other way, for sharing.

## Native screens

At the root of a native host, `Stack.Navigator` never mutates its own
state for pushes and pops. It hands the *serialized next state* to the
host (`push_screen`, `pop_screens`, `replace_screen`,
`reset_screens`), the platform creates a new view controller or
fragment, and the new screen's navigator boots from that state. Each
native screen owns a Python
[`ScreenHost`][pythonnative.hosts.base.ScreenHost] and reconciler, so:

- The previous screen's hook state and native views are preserved by
  the platform stack.
- The new screen renders the right route on its first frame.
- Hot reload runs per host: each active screen swaps its function
  references in place ("Fast Refresh"), falling back to a remount only
  for screens that can't be refreshed cleanly.

`title` and the other header options are pushed to the host through
`set_screen_options`, so `nav.set_options(title=...)` updates the
native bar.

### iOS
- Each pushed screen is a Swift `ViewController` on a root
  `UINavigationController` set up by the template's `SceneDelegate`.
- `presentation="modal"` presents the screen as a sheet.
- `gesture_enabled=False` disables the interactive pop gesture.

### Android
- The host `MainActivity` embeds a `NavHostFragment` with a single
  generic `ScreenFragment` destination; each pushed screen is a fresh
  fragment whose arguments carry the serialized navigation state, so
  it restores across configuration changes.
- Push and pop delegate to `NavController` through a small `Navigator`
  Kotlin helper.
- The hardware back button and predictive back gesture run
  `before_remove` listeners and
  [`use_back_handler`][pythonnative.use_back_handler] callbacks
  before the platform pops.

## Testing

Navigation is fully testable without a device with
[`pythonnative.testing`](../api/testing.md). Rendering under a
[`FakeHost`][pythonnative.testing.FakeHost] records what a root stack
would ask the platform to do:

```python
from pythonnative.testing import FakeHost, render

def test_home_opens_detail():
    host = FakeHost()
    result = render(App(), host=host)
    result.press(result.get_by_text("Open item 42"))
    state, options = host.pushed[0]
    assert state["routes"][-1]["name"] == "Detail"
    assert options["title"] == "Item 42"
```

Without a host, the same stack renders in Python so `get_by_text`,
`press`, and `back()` drive a whole flow in one test. See the
[Testing guide](testing.md).

## Next steps

- See worked navigation examples: [Examples/Navigation](../examples/navigation.md).
- Browse the API: [Navigation](../api/navigation.md).
- Learn how focus interacts with effects: [Lifecycle](../concepts/lifecycle.md).
