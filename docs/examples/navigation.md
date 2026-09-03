# Navigation

Three small examples that show off the available navigators (stack,
tab, drawer) and how to navigate between screens with
[`use_navigation`][pythonnative.use_navigation] and read the current
route with [`use_route`][pythonnative.use_route].

For the conceptual model and the full API, see the
[Navigation guide](../guides/navigation.md) and the
[Navigation API reference](../api/navigation.md).

## Stack navigator

A pushable, poppable stack. The default for "go from screen A to
screen B with a back button".

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()


@pn.component
def HomeScreen():
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Home", style={"font_size": 28, "bold": True}),
        pn.Button(
            "View profile",
            on_press=lambda: nav.navigate("Profile", user_id=42),
        ),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def ProfileScreen():
    route = pn.use_route()
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text(f"User #{route.params['user_id']}", style={"font_size": 24}),
        pn.Button("Back", on_press=nav.go_back),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen, title="Home"),
            Stack.Screen("Profile", ProfileScreen, title="Profile"),
        )
    )
```

`nav.navigate("Profile", user_id=42)` pushes onto the stack (or
returns to an existing `Profile` entry); `nav.push(...)` always adds a
new one; `nav.go_back()` pops one frame. To replace the entire stack
(e.g., after login), use `nav.reset("Home")`.

## Tab navigator

A persistent tab bar at the bottom (iOS) or top (Android), with one
screen per tab. Each tab keeps its own state across switches.

```python
Tabs = pn.create_tab_navigator()


@pn.component
def Feed():
    return pn.Text("Feed", style={"padding": 16, "font_size": 24})


@pn.component
def Search():
    q, set_q = pn.use_state("")
    return pn.Column(
        pn.TextInput(value=q, on_change=set_q, placeholder="Search..."),
        pn.Text(f"Results for: {q}"),
        style={"spacing": 12, "padding": 16},
    )


@pn.component
def Settings():
    return pn.Text("Settings", style={"padding": 16, "font_size": 24})


@pn.component
def App():
    return pn.NavigationContainer(
        Tabs.Navigator(
            Tabs.Screen(name="Feed", component=Feed),
            Tabs.Screen(name="Search", component=Search),
            Tabs.Screen(name="Settings", component=Settings),
        )
    )
```

The search box keeps its query when the user switches to **Settings**
and back; tab screens are not unmounted on blur unless the navigator
is configured otherwise.

## Drawer navigator

A side drawer for primary navigation in larger apps.

```python
Drawer = pn.create_drawer_navigator()


@pn.component
def Inbox():
    return pn.Text("Inbox", style={"padding": 16, "font_size": 24})


@pn.component
def Sent():
    return pn.Text("Sent", style={"padding": 16, "font_size": 24})


@pn.component
def App():
    return pn.NavigationContainer(
        Drawer.Navigator(
            Drawer.Screen(name="Inbox", component=Inbox),
            Drawer.Screen(name="Sent", component=Sent),
        )
    )
```

The drawer opens via a swipe from the leading edge or
`nav.toggle_drawer()` from inside any screen.

## Nesting

Navigators compose. A typical pattern is a tab navigator at the top
with a stack navigator inside each tab:

```python
@pn.component
def App():
    return pn.NavigationContainer(
        Tabs.Navigator(
            Tabs.Screen(name="Home", component=HomeStack),
            Tabs.Screen(name="Profile", component=ProfileStack),
        )
    )


@pn.component
def HomeStack():
    return Stack.Navigator(
        Stack.Screen(name="Feed", component=Feed),
        Stack.Screen(name="Post", component=Post),
    )
```

Pushing onto the inner stack leaves the tab bar visible; switching
tabs preserves each stack's own history.

## Focus-aware effects

When you need to start something only while a screen is on screen
(camera, GPS, animation), use
[`use_focus_effect`][pythonnative.use_focus_effect]:

```python
@pn.component
def CameraScreen():
    pn.use_focus_effect(
        lambda: (start_camera(), stop_camera)[1],
        deps=[],
    )
    return pn.View()
```

The cleanup runs as soon as the user navigates away, even if the
screen stays mounted.

## Next steps

- Reference: [Navigation API](../api/navigation.md).
- Patterns and lifecycle: [Navigation guide](../guides/navigation.md).
- Render lists inside a tab: [Lists](lists.md).
