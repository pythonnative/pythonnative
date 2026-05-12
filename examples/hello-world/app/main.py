"""Hello-world demo: native-backed stack + tab navigation.

This module is the app's navigation map. It defines:

- A root [`Stack`][pythonnative.create_stack_navigator] with three
  routes (``Tabs`` -> ``Showcase`` -> ``Forms``).
- A nested [`Tab`][pythonnative.create_tab_navigator] navigator
  that holds the four home tabs (Home, Layout, List, Settings).

Each screen lives in its own file under ``screens/`` so this file
stays focused on the navigation structure. When the user taps
"View Showcase" from inside a tab, the root stack pushes a real
``UIViewController`` / ``Fragment`` so they get system-grade slide
transitions and swipe-back. Each push reuses this Python
interpreter; only the reconciler tree for the new screen is created.

The native templates load this module by path (``"app.main"``) and
look up the top-level ``App`` attribute.
"""

import pythonnative as pn
from app.screens.forms import FormsScreen
from app.screens.home import HomeScreen
from app.screens.layout import LayoutScreen
from app.screens.list import ListScreen
from app.screens.settings import SettingsScreen
from app.screens.showcase import ShowcaseScreen

print("[hello-world] main module imported")

Stack = pn.create_stack_navigator()
Tab = pn.create_tab_navigator()


@pn.component
def MainTabs() -> pn.Element:
    """Tabbed root screen: Home, Layout, List, Settings."""
    return Tab.Navigator(
        Tab.Screen("Home", component=HomeScreen, options={"title": "Home"}),
        Tab.Screen("Layout", component=LayoutScreen, options={"title": "Layout"}),
        Tab.Screen("List", component=ListScreen, options={"title": "List"}),
        Tab.Screen("Settings", component=SettingsScreen, options={"title": "Settings"}),
    )


@pn.component
def App() -> pn.Element:
    """Root component for the hello-world demo.

    A [`Stack`][pythonnative.create_stack_navigator] wraps the tabbed
    home screen so the demo can push the showcase / forms screens onto
    the native navigation stack. ``options["title"]`` is mirrored to
    the platform navigation bar.
    """
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Tabs", component=MainTabs, options={"title": "Hello World"}),
            Stack.Screen("Showcase", component=ShowcaseScreen, options={"title": "Showcase"}),
            Stack.Screen("Forms", component=FormsScreen, options={"title": "Forms"}),
        )
    )
