"""Navigation: typed stack, tab, and drawer navigators.

Screens are ordinary components whose parameters are their route
params; navigators are module-level values listing them:

```python
import pythonnative as pn


@pn.component
def HomeScreen() -> pn.Node:
    nav = pn.use_navigation()
    return pn.Button("Open 42", on_press=lambda: nav.push(ItemScreen(id=42)))


@pn.component
def ItemScreen(id: int) -> pn.Node:
    pn.use_screen_options(title=f"Item {id}")
    return pn.Text(f"Item {id}")


Root = pn.StackNavigator(
    pn.Screen(HomeScreen, title="Home"),
    pn.Screen(ItemScreen, path="items/{id}"),
    screen_options=pn.ScreenOptions(header_large_title=True),
)
nav_ref = pn.NavigationRef()


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, link_prefixes=["myapp://"], ref=nav_ref)
```

``nav.push(ItemScreen(id=42))`` builds the destination with the screen
component's own signature, so a missing or mistyped param is a type
error. Public surface (all re-exported from ``pythonnative``):

- Navigators: [`StackNavigator`][pythonnative.StackNavigator],
  [`TabNavigator`][pythonnative.TabNavigator],
  [`DrawerNavigator`][pythonnative.DrawerNavigator],
  [`Screen`][pythonnative.Screen], [`Group`][pythonnative.Group], and
  [`NavigationContainer`][pythonnative.NavigationContainer].
- Hooks: [`use_navigation`][pythonnative.use_navigation],
  [`use_route`][pythonnative.use_route],
  [`use_screen_options`][pythonnative.use_screen_options],
  [`use_is_focused`][pythonnative.use_is_focused], and
  [`use_focus_effect`][pythonnative.use_focus_effect].
- Types: [`Navigation`][pythonnative.Navigation],
  [`NavigationRef`][pythonnative.NavigationRef],
  [`Route`][pythonnative.navigation.Route],
  [`NavigationState`][pythonnative.navigation.NavigationState],
  [`ScreenOptions`][pythonnative.ScreenOptions], and
  [`TabBarStyle`][pythonnative.TabBarStyle].
"""

from .container import ContainerContext, NavigationContainer
from .handle import (
    DrawerNavigation,
    EventName,
    FocusContext,
    HostNavigator,
    Navigation,
    NavigationContext,
    NavigationEvent,
    NavigatorCore,
    TabNavigation,
)
from .hooks import use_focus_effect, use_is_focused, use_navigation, use_route
from .host import NAV_STATE_ARG, HostContext, HostRoot
from .linking import LinkTable
from .navigators import DrawerNavigator, Navigator, StackNavigator, TabNavigator, use_screen_options
from .ref import NavigationRef
from .screen import Group, Screen, ScreenOptions, ScreenTarget, TabBarStyle
from .state import NavigationState, Route

__all__ = [
    "NAV_STATE_ARG",
    "ContainerContext",
    "DrawerNavigation",
    "DrawerNavigator",
    "EventName",
    "FocusContext",
    "Group",
    "HostContext",
    "HostNavigator",
    "HostRoot",
    "LinkTable",
    "Navigation",
    "NavigationContainer",
    "NavigationContext",
    "NavigationEvent",
    "NavigationRef",
    "NavigationState",
    "Navigator",
    "NavigatorCore",
    "Route",
    "Screen",
    "ScreenOptions",
    "ScreenTarget",
    "StackNavigator",
    "TabBarStyle",
    "TabNavigation",
    "TabNavigator",
    "use_focus_effect",
    "use_is_focused",
    "use_navigation",
    "use_route",
    "use_screen_options",
]
