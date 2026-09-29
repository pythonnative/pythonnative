"""Navigation: stack, tab, and drawer navigators with a React Navigation-style API.

```python
import pythonnative as pn

Stack = pn.create_stack_navigator()
nav_ref = pn.create_navigation_ref()

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
            Stack.Group(
                Stack.Screen("Detail", DetailScreen, options=lambda route: {"title": f"Item {route.params['id']}"}),
                screen_options={"presentation": "modal"},
            ),
            screen_options={"header_large_title": True},
        ),
        ref=nav_ref,
    )
```

Public surface (all re-exported from ``pythonnative``):

- Factories: [`create_stack_navigator`][pythonnative.create_stack_navigator],
  [`create_tab_navigator`][pythonnative.create_tab_navigator],
  [`create_drawer_navigator`][pythonnative.create_drawer_navigator],
  [`create_navigation_ref`][pythonnative.create_navigation_ref],
  [`NavigationContainer`][pythonnative.NavigationContainer].
- Hooks: [`use_navigation`][pythonnative.use_navigation],
  [`use_route`][pythonnative.use_route],
  [`use_is_focused`][pythonnative.use_is_focused],
  [`use_focus_effect`][pythonnative.use_focus_effect],
  [`use_navigation_theme`][pythonnative.use_navigation_theme].
- Types: [`Navigation`][pythonnative.Navigation],
  [`NavigationRef`][pythonnative.NavigationRef],
  [`Route`][pythonnative.navigation.Route],
  [`NavigationState`][pythonnative.navigation.NavigationState],
  [`ScreenOptions`][pythonnative.ScreenOptions],
  [`TabBarStyle`][pythonnative.TabBarStyle],
  [`NavigationTheme`][pythonnative.NavigationTheme],
  [`NavigationColors`][pythonnative.NavigationColors],
  [`LinkingConfig`][pythonnative.LinkingConfig].
- Themes: [`DEFAULT_NAVIGATION_THEME`][pythonnative.DEFAULT_NAVIGATION_THEME],
  [`DARK_NAVIGATION_THEME`][pythonnative.DARK_NAVIGATION_THEME].
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
from .ref import NavigationRef, create_navigation_ref
from .screen import HeaderSlot, ScreenDef, ScreenGroup, ScreenOptions, TabBarStyle
from .state import NavigationState, Route, RouteParams
from .theme import (
    DARK_NAVIGATION_THEME,
    DEFAULT_NAVIGATION_THEME,
    NavigationColors,
    NavigationTheme,
    NavigationThemeContext,
    use_navigation_theme,
)

__all__ = [
    "DARK_NAVIGATION_THEME",
    "DEFAULT_NAVIGATION_THEME",
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
    "NavigationColors",
    "NavigationContainer",
    "NavigationContext",
    "NavigationEvent",
    "NavigationRef",
    "NavigationState",
    "NavigationTheme",
    "NavigationThemeContext",
    "NavigatorCore",
    "Route",
    "RouteParams",
    "ScreenDef",
    "ScreenGroup",
    "ScreenOptions",
    "StackNavigator",
    "TabBarStyle",
    "TabNavigation",
    "TabNavigator",
    "create_drawer_navigator",
    "create_navigation_ref",
    "create_stack_navigator",
    "create_tab_navigator",
    "use_focus_effect",
    "use_is_focused",
    "use_navigation",
    "use_navigation_theme",
    "use_route",
]
