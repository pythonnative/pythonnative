# Navigation

PythonNative navigation keeps React Navigation's model (stacks, tabs,
drawers, a container at the root, and a handle for moving between
screens) and expresses it in ordinary, typed Python:

- **Screens are components.** A screen's parameters *are* its route
  params, so `nav.push(ItemScreen(id=42))` is checked by your type
  checker exactly like any other call.
- **Navigators are values.** You define them once at module level with
  [`StackNavigator`][pythonnative.StackNavigator],
  [`TabNavigator`][pythonnative.TabNavigator], or
  [`DrawerNavigator`][pythonnative.DrawerNavigator], and render the root
  one with [`NavigationContainer`][pythonnative.NavigationContainer].
- **Nesting is static.** A navigator can be a screen of another
  navigator, so deep links and navigation calls reach nested screens
  without extra arguments.
- **State is a value.** Navigation state is a plain, serializable
  [`NavigationState`][pythonnative.navigation.NavigationState], so it
  can be persisted, restored, and derived from a URL.

On a device every stack is **native-backed**. Pushing a screen pushes a
real `UIViewController` on iOS or a `Fragment` on Android, at every
nesting level, so you get the platform's transitions, swipe-back, and
state preservation for free. Tab bars are native too. The drawer is
drawn in Python on every platform. Without a native host (headless
tests) the stack draws a themed header itself.

## A complete example

Save a module at `app/main.py` that defines an `App` component:

```python
import pythonnative as pn


@pn.component
def HomeScreen() -> pn.Node:
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Home", style={"font_size": 24}),
        pn.Button("Open item 42", on_press=lambda: nav.push(ItemScreen(id=42))),
        style={"gap": 12, "padding": 16},
    )


@pn.component
def ItemScreen(id: int, tab: str = "details") -> pn.Node:
    nav = pn.use_navigation()
    pn.use_screen_options(title=f"Item {id}")
    return pn.Column(
        pn.Text(f"Item {id} ({tab})", style={"font_size": 20}),
        pn.Button("Back", on_press=nav.go_back),
        style={"gap": 12, "padding": 16},
    )


Root = pn.StackNavigator(
    pn.Screen(HomeScreen, title="Home"),
    pn.Screen(ItemScreen, path="items/{id}"),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, link_prefixes=["myapp://"])
```

The native templates (Android `ScreenFragment`, iOS `ViewController`)
import `app.main` and look up its top-level `App`, so no other wiring
is required. `title` propagates to the native navigation bar, and
`myapp://items/42?tab=reviews` opens `ItemScreen(id=42, tab="reviews")`.

## Screens and params

A screen is any `@pn.component`. Its parameters are the route's
params, and parameter defaults are the defaults for params the caller
leaves out:

```python
@pn.component
def ItemScreen(id: int, tab: str = "details") -> pn.Node: ...


nav.push(ItemScreen(id=42))                 # tab == "details"
nav.push(ItemScreen(id=42, tab="reviews"))
nav.push(ItemScreen(idd=42))                # a type error, and a TypeError at run time
```

Calling a screen component doesn't render it. It builds an
[`Element`][pythonnative.Element] that carries the params, and the
navigator renders the screen as `ItemScreen(**route.params)`. Because
the call goes through the component's own signature, a missing or
misspelled param fails at the call site. In development builds a param
whose value doesn't match its annotation also produces a
[`diagnostics`][pythonnative.diagnostics] warning.

A route stores only the params the caller passed; the screen gets its
parameter defaults when it renders. So navigating back to an existing
route with `ItemScreen(id=6)` merges `id` and keeps any other params it
already had.

Params travel over the bridge and into saved state as JSON, so keep
them to JSON-friendly values: strings, numbers, booleans, `None`,
lists, and dicts. Pass an id and look the record up in the screen,
rather than passing the record itself.

[`use_route`][pythonnative.use_route] returns the screen's
[`Route`][pythonnative.navigation.Route] for the rare code that needs
its identity: `route.name`, the raw `route.params` dict, and
`route.key`, which is unique for each visit. Outside a navigator it
returns a placeholder route named `"__root__"`, so screens also render
standalone in previews and tests.

## Navigators

A navigator lists its screens. Each entry is a
[`Screen`][pythonnative.Screen], a [`Group`][pythonnative.Group], or a
bare component or navigator, which is shorthand for `pn.Screen(x)`:

```python
Root = pn.StackNavigator(
    HomeScreen,                                   # same as pn.Screen(HomeScreen)
    pn.Screen(ItemScreen, title="Item", path="items/{id}"),
    pn.Group(pn.Screen(ComposeScreen), pn.Screen(FiltersScreen), presentation="modal"),
    screen_options=pn.ScreenOptions(header_large_title=True),
    initial=HomeScreen,
)
```

- The **route name** defaults to the component's name (`"ItemScreen"`)
  or, for a nested navigator, its `name=`. Names appear in serialized
  state and diagnostics; your code never passes them around. Two
  screens with the same name raise `ValueError`; give one of them
  `pn.Screen(Component, name="Other")`.
- `initial` selects the first screen. It takes a component, a
  navigator, or an element carrying params (`initial=ItemScreen(id=1)`),
  and defaults to the first entry. Parameter defaults replace React
  Navigation's `initialParams`.
- `screen_options` applies [`ScreenOptions`][pythonnative.ScreenOptions]
  to every screen. `pn.ScreenOptions(...)` is a `TypedDict`, so its keys
  are checked statically.

Navigators are immutable. Define them at module level, after the
screens they list. Calling a navigator (`Root()`) returns the element
that renders it, which is how the container and nested navigators use
it.

### Stack

A stack keeps a history. `navigate` goes to a screen (returning to it
if it's already in the history), `push` always adds a new instance, and
`pop` and `go_back` return.

On a device the stack pushes native screens whether it sits at the
root or inside a tab. The native container draws the header: the title,
the back button, and the `header_left` and `header_right` slots.
Screens beneath the top stay mounted with their state, so popping back
restores scroll position and inputs.

### Tabs

Tabs render a native tab bar (`UITabBar` on iOS, Material
`BottomNavigationView` on Android). Visited tabs stay mounted and
hidden, so switching back is instant and keeps state.

```python
Tabs = pn.TabNavigator(
    pn.Screen(HomeScreen, title="Home", tab_bar_icon="house"),
    pn.Screen(InboxScreen, tab_bar_label="Inbox", tab_bar_badge=3),
    pn.Screen(SettingsScreen, lazy=False),
    pn.Screen(CameraScreen, unmount_on_blur=True),
    pn.Screen(FeedScreen, freeze_on_blur=True),
    tab_bar_style=pn.TabBarStyle(active_tint_color="#FF2D55", show_labels=False),
)
```

- Every tab is created when the navigator mounts, so every tab except
  the `initial` one must be callable without arguments. Give tab
  parameters defaults; the navigator raises `TypeError` when it's built
  otherwise.
- `tab_bar_icon` takes a Lucide icon name (the same names as
  [`Icon`][pythonnative.Icon]) or a bundled image via `pn.asset(...)`.
  Both render identically on iOS and Android and tint with the tab bar.
- `lazy` (default `True`) mounts a tab the first time it's focused.
  `lazy=False` mounts it with the navigator.
- `unmount_on_blur=True` tears a tab down when it loses focus, for
  screens that hold expensive resources.
- `freeze_on_blur=True` holds back new params for an unfocused tab until
  it regains focus. Navigators already skip an unfocused tab whose params
  didn't change, and a state change inside the tab still re-renders it.
- `tab_bar_visible=False` hides the tab bar while that tab is focused.
  Set it on a tab whose nested stack pushes detail screens, or toggle it
  at run time with `nav.get_parent().set_options(tab_bar_visible=False)`.
- `tab_bar_style` is a [`TabBarStyle`][pythonnative.TabBarStyle] with
  `background_color`, `active_tint_color`, `inactive_tint_color`,
  `translucent` (iOS only), and `show_labels`. Unset keys fall back to
  the [theme](#theming).

Inside a tab screen, `use_navigation()` returns a
[`TabNavigation`][pythonnative.navigation.TabNavigation], which adds
`jump_to(target)`. Most screens don't need it: `nav.navigate(...)`
switches tabs too.

### Drawer

A drawer is like tabs with a slide-in menu instead of a tab bar. Like
tabs, drawer screens other than `initial` must be callable without
arguments.

```python
from pythonnative.navigation import DrawerNavigation


@pn.component
def FeedScreen() -> pn.Node:
    nav = pn.use_navigation()
    assert isinstance(nav, DrawerNavigation)
    return pn.Column(
        pn.Button("Menu", on_press=nav.open_drawer),
        pn.Text("Feed"),
    )


Drawer = pn.DrawerNavigator(
    pn.Screen(FeedScreen, title="My feed"),
    pn.Screen(ProfileScreen, title="Profile"),
    drawer_width=280,
)
```

[`DrawerNavigation`][pythonnative.navigation.DrawerNavigation] adds
`open_drawer()`, `close_drawer()`, `toggle_drawer()`,
`is_drawer_open()`, and `jump_to(target)`, which also closes the menu.
`use_navigation()` is typed as the base
[`Navigation`][pythonnative.Navigation], so narrow it with
`isinstance` before calling the drawer methods. The system back action
closes an open drawer before it does anything else.

## Screen options

There's one way to set options statically and one way to set them
from a screen's render.

**Statically**, pass [`ScreenOptions`][pythonnative.ScreenOptions]
keywords to `pn.Screen(...)`, to `pn.Group(...)`, or as the navigator's
`screen_options=`. A `Group` layers options over a subset of screens
without changing the route list; it has no state of its own. Every
navigator (stack, tab, and drawer) accepts all three.

**Dynamically**, call
[`use_screen_options`][pythonnative.use_screen_options] from the
screen's render. Options computed there follow the screen's props and
state, so a dynamic title or a header button lives next to the code it
depends on:

```python
@pn.component
def ComposeScreen(draft_id: int | None = None) -> pn.Node:
    nav = pn.use_navigation()
    text, set_text = pn.use_state("")
    pn.use_screen_options(
        title="New message" if draft_id is None else "Edit draft",
        header_right=pn.Button("Send", on_press=nav.go_back, disabled=not text),
    )
    return pn.TextInput(value=text, on_change=set_text, placeholder="Message")
```

`use_screen_options` runs as a layout effect and updates the navigator
only when the options actually change. The navigator reuses the
screen's element when it re-renders for an option change, so setting
options doesn't re-render the screen and can't loop.
`header_left` and `header_right` take an element. To change another
screen's options, call `set_options(...)` on its handle, for example
`nav.get_parent().set_options(tab_bar_visible=False)`.

Options resolve in this order, later entries winning: the navigator's
`screen_options`, each enclosing `Group`, the `Screen` itself, then
options set at run time. An unknown option key raises `TypeError`.

## The `Navigation` handle

[`use_navigation`][pythonnative.use_navigation] returns the
[`Navigation`][pythonnative.Navigation] handle for the *current
screen*. Destinations are screen elements, built by calling the screen
component with its params:

```python
nav.navigate(ItemScreen(id=42))          # go to it (back to it if it's in the history)
nav.push(ItemScreen(id=43))              # always push a new instance
nav.replace(LoginScreen())               # swap the current screen
nav.pop()                                # back one screen (also nav.go_back())
nav.pop(2)                               # back two
nav.pop_to(HomeScreen)                   # back to the most recent HomeScreen
nav.pop_to(ItemScreen(id=1))             # ... merging new params into it
nav.pop_to_top()                         # back to the first screen
nav.reset(HomeScreen(), ItemScreen(id=1))  # replace the whole history
nav.set_params(id=44)                    # re-render this screen with new arguments
nav.set_options(title="Edited")          # change ScreenOptions at run time
```

`pop_to` and `jump_to` also accept a bare component or navigator when
there are no params to merge. `pop_to` on a screen that isn't in the
history replaces the active screen, as React Navigation does; on tab
and drawer navigators it falls back to `navigate`. `set_params` checks
the merged params against the screen's signature, so a misspelled name
raises `TypeError`. `get_state()` is truthful right after an action,
because the navigator commits its state eagerly.

Introspection: `nav.route`, `nav.get_options()`, `nav.get_state()`,
`nav.get_parent()`, `nav.can_go_back()`, `nav.is_focused()`, and
`nav.kind` (`"stack"`, `"tab"`, or `"drawer"`).

### How targets are found

A target is matched by component identity. The handle searches its
own navigator first, then the navigators statically nested in it, then
each enclosing navigator in turn. A screen can therefore navigate
anywhere in the tree without knowing its shape: pushing a detail screen
from inside a tab reaches the root stack, and navigating to a screen
inside a nested navigator opens that navigator on the screen. A target
that no navigator in the tree renders raises `ValueError`.

### Navigating from outside the tree

Push-notification handlers, deep-link code, and services have no
component in scope. Create a [`NavigationRef`][pythonnative.NavigationRef]
at module level and bind it with `NavigationContainer(ref=...)`:

```python
nav_ref = pn.NavigationRef()


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, ref=nav_ref)


def on_push_notification(payload: dict[str, str]) -> None:
    if nav_ref.is_ready():
        nav_ref.navigate(ThreadScreen(id=payload["thread"]))
```

The ref proxies `navigate`, `push`, `replace`, `pop`, `go_back`,
`pop_to`, `pop_to_top`, `reset`, and `get_state` to the root
navigator, and exposes the root [`Navigation`][pythonnative.Navigation]
handle as `nav_ref.current`. Because the root navigator reaches every
statically nested screen, the ref can open any screen in the app.
Every method raises `RuntimeError` while no container is mounted, so
check `is_ready()` from code that may run before the UI is up.

### Listeners

```python
from collections.abc import Callable

from pythonnative.navigation import NavigationEvent


@pn.component
def EditScreen() -> pn.Node:
    nav = pn.use_navigation()
    dirty, set_dirty = pn.use_state(False)

    def guard() -> Callable[[], None]:
        def on_before_remove(event: NavigationEvent) -> None:
            if dirty:
                event.prevent_default()
                pn.Alert.show("Discard changes?", "You have unsaved edits.")

        return nav.add_listener("before_remove", on_before_remove)

    pn.use_effect(guard, [nav, dirty])
    return pn.TextInput(on_change=lambda _: set_dirty(True))
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
so UIKit refuses the pop synchronously and asks Python first. A vetoed
back therefore doesn't animate the screen out and back in, and if the
race is lost the stack restores the native screens to match Python's
state. `gesture_enabled=False` (iOS only) disables the swipe gesture
outright instead.

## Focus

[`use_is_focused`][pythonnative.use_is_focused] is `True` only for the
visible screen: inactive tabs, screens beneath the top of a stack, and
screens covered by a pushed native screen all read `False`.
[`use_focus_effect`][pythonnative.use_focus_effect] runs an effect
while focused and runs its cleanup on blur:

```python
from collections.abc import Callable


@pn.component
def FeedScreen() -> pn.Node:
    def start_polling() -> Callable[[], None]:
        timer = schedule_refresh()
        return timer.cancel

    pn.use_focus_effect(start_polling, [])
    return FeedList()
```

## Nesting

A navigator is a valid screen, so nesting is part of the static
definition:

```python
Tabs = pn.TabNavigator(
    pn.Screen(FeedScreen, title="Feed", tab_bar_icon="house"),
    pn.Screen(ProfileScreen, title="Me", tab_bar_icon="user"),
    name="Main",
)

Root = pn.StackNavigator(
    pn.Screen(Tabs, header_shown=False),
    pn.Screen(ItemScreen),
)
```

A nested navigator needs a route name: pass `name=` to the navigator or
`pn.Screen(Tabs, name="Main")`. From any screen:

- `nav.push(ItemScreen(id=7))` from inside the feed tab pushes onto the
  root stack, above the tab bar.
- `nav.navigate(ProfileScreen(user="ada"))` from `ItemScreen` returns
  to the tabs and selects the profile tab with `user="ada"`. No
  `screen=` argument is needed: the root stack finds `ProfileScreen`
  inside `Tabs` and seeds the nested state.
- `go_back()` at the bottom of a nested stack pops the outer one.

Because nesting is static, a navigator rendered from inside a
component body (instead of listed as a screen) is invisible to target
resolution and deep links. List navigators as screens.

## State and persistence

The container reports every state change and accepts an initial state.
To restore navigation across launches, load the saved state before the
container mounts, because `initial_state` is read once:

```python
from typing import Any

import pythonnative as pn


@pn.component
async def RestoredNavigation() -> pn.Node:
    saved: dict[str, Any] | None = await pn.use_resource(lambda: pn.AsyncStorage.get_json("nav"), [])

    def save(state: pn.NavigationState) -> None:
        pn.run_async(pn.AsyncStorage.set_json("nav", state.to_dict()))

    return pn.NavigationContainer(Root, initial_state=saved, on_state_change=save)


@pn.component
def App() -> pn.Node:
    return pn.Suspense(RestoredNavigation(), fallback=pn.ActivityIndicator())
```

`initial_state` accepts a `NavigationState` or its `to_dict()` form. A
saved state that no longer matches the navigators (a screen was renamed
or gained a required parameter) is ignored. State restored by the
native host (a pushed native screen re-entering Python) takes
precedence, then `initial_state`, then the launch URL.

## Deep links

A screen's `path` is its deep link. Paths use Python format-string
placeholders, and a nested navigator's path prefixes the paths of its
screens. Pass the URL prefixes the app answers to as
`NavigationContainer(link_prefixes=...)`:

```python
import enum


class Tab(enum.Enum):
    DETAILS = "details"
    REVIEWS = "reviews"


@pn.component
def ItemScreen(id: int, tab: Tab = Tab.DETAILS, preview: bool = False) -> pn.Node: ...


Tabs = pn.TabNavigator(
    pn.Screen(FeedScreen, path="feed"),
    pn.Screen(ProfileScreen, path="u/{user}"),
    name="Main",
)

Root = pn.StackNavigator(
    Tabs,
    pn.Screen(ItemScreen, path="items/{id}"),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, link_prefixes=["myapp://", "https://example.com"])
```

- `myapp://items/42?tab=reviews` opens
  `ItemScreen(id=42, tab=Tab.REVIEWS)`, and `https://example.com/u/ada`
  opens the profile tab with `user="ada"`.
- Path placeholders and query parameters become the screen
  component's arguments, converted with its annotations: `str`, `int`,
  `float`, `bool` (`1`, `true`, `yes`, `on`, and their negatives),
  `Enum` subclasses (by value, then by name), `Literal` values, and
  `Optional` of any of those.
- Query parameters the component doesn't accept are ignored. A URL
  whose values don't convert, or that lacks a required parameter,
  matches nothing instead of passing a string through.
- A nested navigator without a `path` adds no prefix, so `Tabs` above
  contributes `feed` and `u/{user}` at the top level.
- A link into a stack keeps the stack's initial screen beneath the
  target, so back returns there.
- The URL that launched the app seeds the initial state, and URLs that
  arrive while the app is running navigate.

There's no separate route tree to keep in sync: the container derives
its pattern table from the navigators once. To build a URL for sharing,
or to test your paths, use
[`LinkTable`][pythonnative.navigation.LinkTable] directly:

```python
from pythonnative.navigation import LinkTable

links = LinkTable(Root, ["myapp://"])
state = links.state_from_url("myapp://items/42")
assert state is not None and links.url_from_state(state) == "myapp://items/42"
```

## Native screens

A root stack renders keyed logical `Screen` children within one
application reconciler. UIKit navigation controllers and Android
fragments present those existing roots. Pushing a screen preserves
providers, stores, and state above the navigator. Covered screens
remain mounted until they leave the stack. Native containers own the
content rectangle below their navigation bars.

Navigation changes are cached on the native host before lifecycle
state-saving callbacks. Back requests return to Python asynchronously
so `before_remove` listeners and back handlers can decide whether to
remove a route.

The `header_left` and `header_right` elements render within their
route's providers and navigation context. Their native views are
installed in UIKit navigation items or the Android toolbar.

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

Navigators draw their chrome from the app's
[`Theme`][pythonnative.Theme], the same one your components read with
[`use_theme`][pythonnative.use_theme]. There's no separate navigation
theme:

| Token | Used for |
| --- | --- |
| `colors.primary` | Back button, header buttons, the selected tab, and the active drawer row |
| `colors.surface` | Header, tab bar, and drawer panel backgrounds |
| `colors.background` | Screen backgrounds |
| `colors.text` | Header titles and drawer labels |
| `colors.border` | Hairlines under the header and above the tab bar |
| `colors.error` | Tab badges |

Without a provider, navigators follow the system appearance with
[`LIGHT_THEME`][pythonnative.LIGHT_THEME] and
[`DARK_THEME`][pythonnative.DARK_THEME]. To brand them, wrap the
container in a [`ThemeProvider`][pythonnative.ThemeProvider]:

```python
from dataclasses import replace

LIGHT = replace(pn.LIGHT_THEME, colors=replace(pn.LIGHT_THEME.colors, primary="#FF2D55"))
DARK = replace(pn.DARK_THEME, colors=replace(pn.DARK_THEME.colors, primary="#FF375F"))


@pn.component
def App() -> pn.Node:
    return pn.ThemeProvider(pn.NavigationContainer(Root), light=LIGHT, dark=DARK)
```

Explicit `header_tint_color`, `header_style`, `header_title_style`, and
`tab_bar_style` keys win over the theme. See the
[Styling guide](styling.md#themes) for defining themes and adding
tokens.

## Testing

Use `render`, `press`, and `back` to exercise complete navigation flows
in one tree. `FakeHost` supplies lifecycle focus and restoration state
when needed.

```python
from pythonnative.testing import render


def test_home_opens_item() -> None:
    result = render(App())
    result.press(result.get_by_text("Open item 42"))
    assert result.get_by_text("Item 42 (details)")
    assert result.back()
    assert result.get_by_text("Open item 42")
```

## Next steps

- See worked navigation examples: [Examples/Navigation](../examples/navigation.md).
- Browse the API: [Navigation](../api/navigation.md).
- Learn how focus interacts with effects: [Lifecycle](../concepts/lifecycle.md).
