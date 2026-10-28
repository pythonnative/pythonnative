# Navigation

Small examples that show the three navigators (stack, tab, and drawer),
how screens receive their params as ordinary arguments, and how
navigators nest. Every screen is a `@pn.component`, and every navigator
is a module-level value rendered by
[`NavigationContainer`][pythonnative.NavigationContainer].

For the conceptual model and the full API, see the
[Navigation guide](../guides/navigation.md) and the
[Navigation API reference](../api/navigation.md).

## Run it

Create a project with `pn init navigation-demo`, then `cd navigation-demo`.
Replace `app/main.py` with the Stack, Tab, Drawer, or Nesting snippet
below. Each includes its imports and defines `App`, the project's root
component.

From the project root, run `pn preview` to open the app in your browser.
To run on a device or simulator, leave the preview running and use
`pn run android` or `pn run ios` in another terminal from the same
directory. See the [Browser preview guide](../guides/browser-preview.md)
and [Development workflow](../guides/dev-workflow.md) for more options.

## Stack navigator

A pushable, poppable stack: the default for "go from screen A to
screen B with a back button."

```python
import pythonnative as pn


@pn.component
def HomeScreen() -> pn.Node:
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Home", style={"font_size": 28, "bold": True}),
        pn.Button("View profile", on_press=lambda: nav.push(ProfileScreen(user_id=42))),
        style={"gap": 12, "padding": 16},
    )


@pn.component
def ProfileScreen(user_id: int) -> pn.Node:
    nav = pn.use_navigation()
    pn.use_screen_options(title=f"User {user_id}")
    return pn.Column(
        pn.Text(f"User #{user_id}", style={"font_size": 24}),
        pn.Button("Back", on_press=nav.go_back),
        style={"gap": 12, "padding": 16},
    )


Root = pn.StackNavigator(
    pn.Screen(HomeScreen, title="Home"),
    ProfileScreen,
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root)
```

`ProfileScreen(user_id=42)` is an ordinary call, so your editor
autocompletes `user_id` and your type checker rejects a missing or
misspelled param. `nav.push(...)` always adds a new screen,
`nav.navigate(...)` returns to an existing `ProfileScreen` if there is
one, and `nav.go_back()` pops one screen. To replace the entire history
(after signing in, for example), use `nav.reset(HomeScreen())`.

## Tab navigator

A persistent native tab bar, with one screen per tab. Each tab keeps
its own state across switches.

```python
import pythonnative as pn


@pn.component
def FeedScreen() -> pn.Node:
    return pn.Text("Feed", style={"padding": 16, "font_size": 24})


@pn.component
def SearchScreen() -> pn.Node:
    query, set_query = pn.use_state("")
    return pn.Column(
        pn.TextInput(value=query, on_change=set_query, placeholder="Search..."),
        pn.Text(f"Results for: {query}"),
        style={"gap": 12, "padding": 16},
    )


@pn.component
def SettingsScreen() -> pn.Node:
    return pn.Text("Settings", style={"padding": 16, "font_size": 24})


Tabs = pn.TabNavigator(
    pn.Screen(FeedScreen, title="Feed", tab_bar_icon="house"),
    pn.Screen(SearchScreen, title="Search", tab_bar_icon="search"),
    pn.Screen(SettingsScreen, title="Settings", tab_bar_icon="settings"),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Tabs)
```

The search box keeps its query when the user switches to **Settings**
and back: tab screens stay mounted unless a screen sets
`unmount_on_blur=True`. Tab screens must be callable without arguments,
so give any tab parameters defaults.

## Drawer navigator

A side drawer for primary navigation in larger apps.

```python
import pythonnative as pn
from pythonnative.navigation import DrawerNavigation


@pn.component
def MenuButton() -> pn.Node:
    nav = pn.use_navigation()
    assert isinstance(nav, DrawerNavigation)
    return pn.Button("Menu", on_press=nav.toggle_drawer)


@pn.component
def InboxScreen() -> pn.Node:
    return pn.Column(
        MenuButton(),
        pn.Text("Inbox", style={"font_size": 24}),
        style={"gap": 12, "padding": 16},
    )


@pn.component
def SentScreen() -> pn.Node:
    return pn.Column(
        MenuButton(),
        pn.Text("Sent", style={"font_size": 24}),
        style={"gap": 12, "padding": 16},
    )


Drawer = pn.DrawerNavigator(
    pn.Screen(InboxScreen, title="Inbox"),
    pn.Screen(SentScreen, title="Sent"),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Drawer)
```

The drawer is drawn in Python and has no navigation bar of its own, so
each screen renders its own **Menu** button. The drawer opens with a
swipe from the leading edge or with `toggle_drawer()` on the
[`DrawerNavigation`][pythonnative.navigation.DrawerNavigation] handle.
`use_navigation()` is typed as the base `Navigation`, so the
`isinstance` check narrows it to the drawer handle.

## Nesting

Navigators compose: a navigator is a valid screen of another
navigator. A common shape is a root stack whose first screen is a tab
navigator, so detail screens push over the tab bar:

```python
import pythonnative as pn


@pn.component
def PostLink(id: int) -> pn.Node:
    nav = pn.use_navigation()
    return pn.Button(f"Post {id}", on_press=lambda: nav.push(PostScreen(id=id)))


@pn.component
def FeedScreen() -> pn.Node:
    return pn.Column(
        *(PostLink(id=post_id).with_key(post_id) for post_id in range(1, 4)),
        style={"gap": 8, "padding": 16},
    )


@pn.component
def ProfileScreen(user: str = "me") -> pn.Node:
    return pn.Text(f"Profile: {user}", style={"padding": 16, "font_size": 24})


@pn.component
def PostScreen(id: int) -> pn.Node:
    nav = pn.use_navigation()
    pn.use_screen_options(title=f"Post {id}")
    return pn.Column(
        pn.Text(f"Post #{id} by ada"),
        pn.Button("View author", on_press=lambda: nav.navigate(ProfileScreen(user="ada"))),
        style={"gap": 12, "padding": 16},
    )


Tabs = pn.TabNavigator(
    pn.Screen(FeedScreen, title="Feed", tab_bar_icon="house", path="feed"),
    pn.Screen(ProfileScreen, title="Profile", tab_bar_icon="user", path="u/{user}"),
    name="Main",
)

Root = pn.StackNavigator(
    pn.Screen(Tabs, header_shown=False),
    pn.Screen(PostScreen, path="posts/{id}"),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, link_prefixes=["navdemo://"])
```

`nav.push(PostScreen(id=...))` from the feed tab reaches the root
stack, because a target the tab navigator doesn't know is handed to its
parent. **View author** navigates back down: the root stack finds
`ProfileScreen` inside `Tabs`, pops the post, and selects the profile
tab with `user="ada"`. The same static tree answers deep links, so
`navdemo://posts/2` opens `PostScreen(id=2)` above the feed and
`navdemo://u/ada` opens the profile tab.

## Focus-aware effects

When you need to run something only while a screen is visible (a
camera, GPS, or an animation), use
[`use_focus_effect`][pythonnative.use_focus_effect]:

```python
from collections.abc import Callable


@pn.component
def CameraScreen() -> pn.Node:
    def start() -> Callable[[], None]:
        start_camera()
        return stop_camera

    pn.use_focus_effect(start, [])
    return pn.View()
```

The cleanup runs as soon as the user navigates away, even if the
screen stays mounted.

To try this with the Tab navigator example, add `CameraScreen` and
stand-ins for `start_camera` and `stop_camera`, and replace
`pn.Screen(SettingsScreen, ...)` with
`pn.Screen(CameraScreen, title="Camera", tab_bar_icon="camera")`. Run
`pn preview`, then switch between the Camera and Feed tabs to trigger
the effect and its cleanup.

## Next steps

- Reference: [Navigation API](../api/navigation.md).
- Patterns and lifecycle: [Navigation guide](../guides/navigation.md).
- Render lists inside a tab: [Lists](lists.md).
