"""E2E suite entry point.

Wires every demo screen from :mod:`app.registry` into the root
[`Stack.Navigator`][pythonnative.create_stack_navigator]. The first
route, ``"Home"``, is a categorized list of buttons that opens the
rest of the demos. Each demo screen owns its own back navigation via
[`use_navigation().go_back()`][pythonnative.use_navigation].

The stack-only architecture keeps the navigation surface flat and
predictable for automated tests: every demo is reachable in exactly
one push, and every back press lands the user back on ``"Home"``.

Two root-level facilities exist for the navigation demos: the container
binds the app-wide [`NavigationRef`][pythonnative.NavigationRef] from
:mod:`app.navigation_ref`, and its
[`NavigationTheme`][pythonnative.NavigationTheme] follows the switch in
:mod:`app.app_theme` so a demo can flip the whole app to the dark preset.
The presentation demo's extra routes (pushed with a ``presentation`` or
``animation`` option) are registered on the root stack too, so the
native stack presents them.
"""

from __future__ import annotations

import pythonnative as pn
from app.app_theme import ThemeSwitchContext, navigation_theme_for
from app.navigation_ref import nav_ref
from app.registry import DEMOS
from app.screens.category import CategoryListScreen
from app.screens.home import HomeScreen
from app.screens.navigation.presentation import PRESENTATION_VARIANTS

print("[e2e-suite] main module imported")

Stack = pn.create_stack_navigator()


@pn.component
def App() -> pn.Element:
    """Root component: a Stack with Home, every Category screen, and every demo."""
    theme_name, set_theme_name = pn.use_state("light")
    return ThemeSwitchContext.Provider(
        pn.NavigationContainer(
            Stack.Navigator(
                Stack.Screen("Home", component=HomeScreen, options={"title": "PythonNative E2E Suite"}),
                Stack.Screen(
                    "Category",
                    component=CategoryListScreen,
                    options={"title": "Category"},
                ),
                *(Stack.Screen(demo.id, component=demo.component, options={"title": demo.title}) for demo in DEMOS),
                *(
                    Stack.Screen(variant.route, component=variant.component, options=variant.options)
                    for variant in PRESENTATION_VARIANTS
                ),
            ),
            ref=nav_ref,
            theme=navigation_theme_for(theme_name),
        ),
        value=(theme_name, set_theme_name),
    )
