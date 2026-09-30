"""Hello-world demo: native stack and tab navigation, a theme with dark mode, and persisted settings.

This module is the app's map. Navigators are module-level values:

- ``Tabs`` holds the four home tabs (Home, Layout, List, Settings).
- ``Root`` is a stack whose first screen is ``Tabs``; the Showcase,
  Forms, and Async Demo screens push on top of it.

Because ``Tabs`` is listed as a screen of ``Root`` (static nesting),
``nav.push(ShowcaseScreen(...))`` works from inside any tab: the tab
navigator doesn't know that screen, so it hands the push to the stack.
Each push creates a real ``UIViewController`` or ``Fragment`` with
system transitions and swipe-back, all driven by this one Python
interpreter.

Each screen lives in its own file under ``screens/``; ``theme.py``
holds the light and dark themes and the shared styles, and
``preferences.py`` holds the saved appearance setting. The native
templates load this module by path (``"app.main"``) and render its
top-level ``App``.
"""

import pythonnative as pn
from app.preferences import AppearanceContext, use_saved_appearance
from app.screens.data import DataScreen
from app.screens.forms import FormsScreen
from app.screens.home import HomeScreen
from app.screens.layout import LayoutScreen
from app.screens.list import ListScreen
from app.screens.settings import SettingsScreen
from app.screens.showcase import ShowcaseScreen
from app.theme import DARK_THEME, LIGHT_THEME

# Tab icons are bundled vector icons (the names ``pn.Icon`` accepts), so the
# tab bar looks the same on iOS and Android. Pass ``pn.asset("images/x.png")``
# instead for a custom bitmap.
Tabs = pn.TabNavigator(
    pn.Screen(HomeScreen, title="Home", tab_bar_icon="house"),
    pn.Screen(LayoutScreen, title="Layout", tab_bar_icon="layout-grid"),
    pn.Screen(ListScreen, title="List", tab_bar_icon="list"),
    pn.Screen(SettingsScreen, title="Settings", tab_bar_icon="settings"),
    name="Tabs",
)

Root = pn.StackNavigator(
    pn.Screen(Tabs, title="Hello World"),
    pn.Screen(ShowcaseScreen, title="Showcase"),
    pn.Screen(FormsScreen, title="Forms"),
    pn.Screen(DataScreen, title="Async Demo"),
)


@pn.component
def App() -> pn.Node:
    """Root component: the saved appearance, the theme, and the navigators.

    ``ThemeProvider`` picks ``LIGHT_THEME`` or ``DARK_THEME`` from the
    effective color scheme (the system's, unless the Settings tab
    overrides it), and the navigators draw their bars from it too.
    """
    appearance = use_saved_appearance()
    return AppearanceContext.Provider(
        pn.ThemeProvider(pn.NavigationContainer(Root), light=LIGHT_THEME, dark=DARK_THEME),
        value=appearance,
    )
