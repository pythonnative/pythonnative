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

The one thing React Navigation can't do: on a device, every stack is
**native-backed**. Pushing a screen pushes a real `UIViewController` on
iOS or a `Fragment` on Android, at every nesting level, so you get the
platform's transitions, swipe-back, and state preservation for free.
Tab bars are native too; the drawer is drawn in Python on every
platform and styled by the navigation theme. Without a native host
(headless tests) the stack draws a themed header itself.

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
    Stack.Group(
        Stack.Screen("Settings", SettingsScreen),
        Stack.Screen("Compose", ComposeScreen),
        screen_options={"presentation": "modal"},
    ),
    screen_options=lambda route: {"title": route.name.title()},
    initial_route="Home",
)
```

On a device the stack pushes native screens whether it sits at the
root or inside a tab; the native container draws the header (title,
back button, and the `header_left` / `header_right` slots). Screens
beneath the top stay mounted with their state, so popping back
restores scroll position and inputs.

### Navigator-level options and groups

`Navigator(screen_options=...)` applies a
[`ScreenOptions`][pythonnative.ScreenOptions] dict, or a
`(route) -> dict` callable, to every screen. `Group(*screens,
screen_options=...)` layers another set on a subset of screens without
changing the route list; a group has no state of its own. Options
resolve in this order, later entries winning: navigator, group, the
screen itself, then `nav.set_options(...)` at runtime. Every navigator
(stack, tab, drawer) accepts both.

### Tabs

Tabs render a native tab bar (`UITabBar` on iOS, Material
`BottomNavigationView` on Android). Visited tabs stay mounted and
hidden, so switching back is instant and keeps state.

```python
Tab = pn.create_tab_navigator()

Tab.Navigator(
    Tab.Screen("Home", HomeScreen, title="Home", tab_bar_icon="house"),
    Tab.Screen("Inbox", InboxScreen, tab_bar_label="Inbox", tab_bar_badge=3),
    Tab.Screen("Settings", SettingsScreen, lazy=False),
    Tab.Screen("Camera", CameraScreen, unmount_on_blur=True),
    Tab.Screen("Feed", FeedScreen, freeze_on_blur=True),
    Tab.Screen("Threads", ThreadsStack, tab_bar_visible=False),
    tab_bar_style={"active_tint_color": "#FF2D55", "show_labels": False},
)
```

- `tab_bar_icon` takes a Lucide icon name (the same names as
  [`Icon`][pythonnative.Icon]) or a bundled image via `pn.asset(...)`.
  Both render identically on iOS and Android and tint with the tab bar.
- `lazy` (default `True`) mounts a tab the first time it's focused.
  `lazy=False` mounts it with the navigator.
- `unmount_on_blur=True` tears a tab down when it loses focus, for
  screens that hold expensive resources.
- `freeze_on_blur=True` reuses an unfocused tab's last rendered element
  instead of re-rendering it when the navigator re-renders. It's a
  parent-driven memo: a state change inside the frozen screen still
  re-renders that component, and the screen renders fresh again when it
  regains focus.
- `tab_bar_visible=False` hides the tab bar while that tab is focused.
  Set it on a tab whose nested stack pushes detail screens, or toggle it
  at runtime with `nav.get_parent().set_options(tab_bar_visible=False)`.
- `tab_bar_style` is a [`TabBarStyle`][pythonnative.TabBarStyle] with
  `background_color`, `active_tint_color`, `inactive_tint_color`,
  `translucent` (iOS only), and `show_labels`. Unset keys fall back to
  the [navigation theme](#theming).

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
nav.pop_to("Home", refresh=True)    # back to the most recent Home, merging params
nav.pop_to_top()                    # back to the first screen
nav.reset("Home")                   # replace the whole history
nav.reset(pn.Route("Home"), pn.Route("Detail", {"id": 1}))
nav.set_params(id=44)               # merge params into this screen's route
nav.set_options(title="Edited")     # change ScreenOptions at runtime
```

`pop_to` on a route that isn't in the history replaces the active
screen, as React Navigation does; on tab and drawer navigators it falls
back to `navigate`. `get_state()` is truthful right after an action,
because the navigator commits its state eagerly.

Introspection: `nav.route`, `nav.get_params()`, `nav.get_options()`,
`nav.get_state()`, `nav.get_parent()`, `nav.can_go_back()`,
`nav.is_focused()`, and `nav.kind` (`"stack"`, `"tab"`, or
`"drawer"`).

### Navigating from outside the tree

Push-notification handlers, deep-link code, and services have no
component in scope. Create a [`NavigationRef`][pythonnative.NavigationRef]
at module level with
[`create_navigation_ref`][pythonnative.create_navigation_ref] and bind
it with `NavigationContainer(ref=...)`:

```python
nav_ref = pn.create_navigation_ref()


@pn.component
def App():
    return pn.NavigationContainer(Stack.Navigator(...), ref=nav_ref)


def on_push_notification(payload):
    if nav_ref.is_ready():
        nav_ref.navigate("Thread", id=payload["thread"])
```

The ref proxies `navigate`, `go_back`, `push`, `pop`, `pop_to`,
`pop_to_top`, `replace`, `reset`, and `get_state` to the root
navigator, and exposes the root
[`Navigation`][pythonnative.Navigation] handle as `nav_ref.current`.
Every method raises `RuntimeError` while no container is mounted, so
check `is_ready()` from code that may run before the UI is up. The ref
resolves only routes the root navigator knows; reach a nested screen
with `nav_ref.navigate("Tabs", screen="Profile")`.

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

`before_remove` fires for **every** removal of the route: `pop`,
`pop_to`, `navigate` back to an existing route, `replace`, `reset`,
the Android back action, and the iOS swipe-back or sheet pull-down;
`event.data["action"]` names the cause. While a route has a
`before_remove` listener the stack marks its native screen as guarded,
so UIKit refuses the pop synchronously and asks Python first; a vetoed
back therefore doesn't animate the screen out and back in, and if the
race is lost the stack restores the native screens to match Python's
state. `gesture_enabled=False` (iOS only) disables the swipe gesture
outright instead.

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

### Typed params

Declare a screen's params as a `TypedDict` and pass it to `use_route`.
`route.params` is then typed for your editor and type checker, and the
hook verifies at the screen's first render that every required key is
present, naming the missing ones instead of failing later with a
`KeyError`:

```python
from typing import NotRequired, TypedDict


class DetailParams(TypedDict):
    id: int
    title: NotRequired[str]


@pn.component
def DetailScreen():
    route = pn.use_route(DetailParams)
    return pn.Text(f"Item #{route.params['id']}")  # id: int
```

Params travel over the bridge as JSON, so keep them to JSON-friendly
values (strings, numbers, booleans, lists, and dicts).

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

A root stack renders keyed logical `Screen` children within one application
reconciler. UIKit navigation controllers and Android fragments present those
existing roots. Pushing a screen preserves providers, repositories, and state
above the navigator. Covered screens remain mounted until they leave the stack.
Native containers own the content rectangle below their navigation bars.

Navigation changes are cached on the native host before lifecycle state-saving
callbacks. Back requests return to Python asynchronously so `before_remove`
listeners and back handlers can decide whether to remove a route.

Header factories (`header_left` and `header_right`) render ordinary Python
components within their route's providers and navigation context. Their native
views are installed in UIKit navigation items or the Android toolbar.

### Presentation and transitions

`presentation` is `"card"` (default, a push) or one of the modal
styles: `"modal"`, `"full_screen_modal"`, `"form_sheet"`, or
`"transparent_modal"`. On iOS these map to `pageSheet`, `fullScreen`,
`formSheet`, and `overFullScreen`; a sheet contains its own stack, so
cards pushed from a modal screen push within the sheet. Android presents
every modal style as a full-screen screen with a slide-from-bottom
transition, which is what React Navigation's native stack does there.

`animation` picks the push transition on both platforms: `"default"`,
`"none"`, `"fade"`, `"slide_from_right"`, or `"slide_from_bottom"`.
Android pushes and pops slide by default, draw a back arrow in an
inset-aware toolbar, and render `header_large_title` as an expanded
toolbar with a larger title (iOS uses the system large title).

Two options are iOS-only and ignored on Android: `header_back_title`
(the label of the back button on the next screen; Android shows a bare
arrow) and `gesture_enabled` (whether the interactive swipe-back can
pop the screen; Android's system back is always available). Predictive
back on Android is enabled at the activity level: the system back
preview appears once Python reports that the stack can't pop; screens
themselves don't animate with the gesture.

## Theming

Navigators draw their chrome from a
[`NavigationTheme`][pythonnative.NavigationTheme]: a frozen record with
`dark: bool` and six [`NavigationColors`][pythonnative.NavigationColors]
(`primary`, `background`, `card`, `text`, `border`, `notification`),
the same shape as React Navigation's theme object. Pass one to
`NavigationContainer(theme=...)`; without one, navigators pick
[`DEFAULT_NAVIGATION_THEME`][pythonnative.DEFAULT_NAVIGATION_THEME] or
[`DARK_NAVIGATION_THEME`][pythonnative.DARK_NAVIGATION_THEME] from the
color scheme and switch when it changes.

```python
import dataclasses

BRAND = dataclasses.replace(
    pn.DEFAULT_NAVIGATION_THEME,
    colors=dataclasses.replace(pn.DEFAULT_NAVIGATION_THEME.colors, primary="#FF2D55"),
)


@pn.component
def App():
    scheme = pn.use_color_scheme()
    return pn.NavigationContainer(
        Stack.Navigator(...),
        theme=pn.DARK_NAVIGATION_THEME if scheme == "dark" else BRAND,
    )
```

The theme supplies the default header tint, header background, title
color, tab tint, and tab bar background sent to the native containers
(explicit `header_tint_color`, `header_style`, `header_title_style`,
and `tab_bar_style` keys win), and the Python-drawn header, drawer
panel, and fallbacks use it directly. Read it in your own components
with [`use_navigation_theme`][pythonnative.use_navigation_theme]:

```python
@pn.component
def Card(*children):
    theme = pn.use_navigation_theme()
    return pn.View(*children, style=pn.style(background_color=theme.colors.card))
```

## Testing

Use `render`, `press`, and `back` to exercise complete navigation flows in one
tree. `FakeHost` supplies lifecycle focus and restoration state when needed.

```python
from pythonnative.testing import render

def test_home_opens_detail():
    result = render(App())
    result.press(result.get_by_text("Open item 42"))
    assert result.get_by_text("Item 42")
    assert result.back()
    assert result.get_by_text("Open item 42")
```

## Next steps

- See worked navigation examples: [Examples/Navigation](../examples/navigation.md).
- Browse the API: [Navigation](../api/navigation.md).
- Learn how focus interacts with effects: [Lifecycle](../concepts/lifecycle.md).
