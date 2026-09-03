"""Navigation: stack, tab, and drawer navigators with a React Navigation-style API.

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()

@pn.component
def HomeScreen():
    nav = pn.use_navigation()
    return pn.Button("Open 42", on_press=lambda: nav.navigate("Detail", id=42))

@pn.component
def DetailScreen():
    route = pn.use_route()
    return pn.Text(f"Item {route.params['id']}")

@pn.component
def App():
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", HomeScreen, title="Home"),
            Stack.Screen("Detail", DetailScreen, options=lambda route: {"title": f"Item {route.params['id']}"}),
        )
    )
```

Public surface (all re-exported from ``pythonnative``):

- Factories: [`create_stack_navigator`][pythonnative.create_stack_navigator],
  [`create_tab_navigator`][pythonnative.create_tab_navigator],
  [`create_drawer_navigator`][pythonnative.create_drawer_navigator],
  [`NavigationContainer`][pythonnative.NavigationContainer].
- Hooks: [`use_navigation`][pythonnative.use_navigation],
  [`use_route`][pythonnative.use_route],
  [`use_is_focused`][pythonnative.use_is_focused],
  [`use_focus_effect`][pythonnative.use_focus_effect].
- Types: [`Navigation`][pythonnative.Navigation],
  [`Route`][pythonnative.navigation.Route],
  [`NavigationState`][pythonnative.navigation.NavigationState],
  [`ScreenOptions`][pythonnative.ScreenOptions],
  [`LinkingConfig`][pythonnative.LinkingConfig].
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
from .linking import LinkingConfig
from .navigators import (
    DrawerNavigator,
    StackNavigator,
    TabNavigator,
    create_drawer_navigator,
    create_stack_navigator,
    create_tab_navigator,
)
from .screen import HeaderSlot, ScreenDef, ScreenOptions
from .state import NavigationState, Route

__all__ = [
    "NAV_STATE_ARG",
    "ContainerContext",
    "DrawerNavigation",
    "DrawerNavigator",
    "EventName",
    "FocusContext",
    "HeaderSlot",
    "HostContext",
    "HostNavigator",
    "HostRoot",
    "LinkingConfig",
    "Navigation",
    "NavigationContainer",
    "NavigationContext",
    "NavigationEvent",
    "NavigationState",
    "NavigatorCore",
    "Route",
    "ScreenDef",
    "ScreenOptions",
    "StackNavigator",
    "TabNavigation",
    "TabNavigator",
    "create_drawer_navigator",
    "create_stack_navigator",
    "create_tab_navigator",
    "use_focus_effect",
    "use_is_focused",
    "use_navigation",
    "use_route",
]
