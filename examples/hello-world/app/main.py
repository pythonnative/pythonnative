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
from app.screens.data import DataScreen
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
    """Tabbed root screen: Home, Layout, List, Settings.

    Each tab opts into a native system icon via ``tab_bar_icon``: an
    SF Symbol on iOS and an ``android.R.drawable.*`` resource on
    Android. The framework renders text-only if a name doesn't
    resolve on a given platform, so adding a new tab is safe even
    before its icons are picked.
    """
    return Tab.Navigator(
        Tab.Screen(
            "Home",
            component=HomeScreen,
            options={
                "title": "Home",
                "tab_bar_icon": {"ios": "house.fill", "android": "ic_menu_compass"},
            },
        ),
        Tab.Screen(
            "Layout",
            component=LayoutScreen,
            options={
                "title": "Layout",
                "tab_bar_icon": {"ios": "square.grid.2x2.fill", "android": "ic_menu_gallery"},
            },
        ),
        Tab.Screen(
            "List",
            component=ListScreen,
            options={
                "title": "List",
                "tab_bar_icon": {"ios": "list.bullet", "android": "ic_menu_sort_by_size"},
            },
        ),
        Tab.Screen(
            "Settings",
            component=SettingsScreen,
            options={
                "title": "Settings",
                "tab_bar_icon": {"ios": "gearshape.fill", "android": "ic_menu_preferences"},
            },
        ),
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
            Stack.Screen("Data", component=DataScreen, options={"title": "Async Demo"}),
        )
    )
