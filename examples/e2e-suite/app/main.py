"""E2E suite entry point.

:data:`Root` is a module-level [`StackNavigator`][pythonnative.StackNavigator]
built from :mod:`app.registry`. Its first screen, ``"Home"``, is a list
of categories; each category screen lists its demos and pushes them
with ``nav.push(Demo())``. Every demo is a [`Screen`][pythonnative.Screen]
named after its registry ``id``, so route names stay stable for the
Maestro flows and for tests that read ``nav.route.name``. Each demo
screen owns its own back navigation via
[`use_navigation().go_back()`][pythonnative.use_navigation].

The stack-only architecture keeps the navigation surface flat and
predictable for automated tests: every demo is reachable in exactly
one push, and every back press lands the user back on the category
list.

Two root-level facilities exist for the navigation demos: the container
binds the app-wide [`NavigationRef`][pythonnative.NavigationRef] from
:mod:`app.navigation_ref`, and a [`ThemeProvider`][pythonnative.ThemeProvider]
supplies the suite themes from :mod:`app.app_theme`, which the
navigator chrome follows when a demo flips the color scheme. The
presentation demo's extra screens (each with a ``presentation`` or
``animation`` option) are registered on the root stack too, so the
native stack presents them.
"""

from __future__ import annotations

import pythonnative as pn
from app.app_theme import SUITE_DARK, SUITE_LIGHT
from app.navigation_ref import nav_ref
from app.registry import DEMOS
from app.screens.category import CategoryListScreen
from app.screens.home import HomeScreen
from app.screens.navigation.presentation import PRESENTATION_VARIANTS

print("[e2e-suite] main module imported")

Root = pn.StackNavigator(
    pn.Screen(HomeScreen, name="Home", title="PythonNative E2E Suite"),
    pn.Screen(CategoryListScreen, name="Category", title="Category"),
    *(pn.Screen(demo.component, name=demo.id, title=demo.title) for demo in DEMOS),
    *(pn.Screen(variant.component, name=variant.route, **variant.options) for variant in PRESENTATION_VARIANTS),
)
"""The root stack: home, the category list, every demo, and the presented screens."""


@pn.component
def App() -> pn.Node:
    """Root component: the themed navigation container around :data:`Root`."""
    return pn.ThemeProvider(
        pn.NavigationContainer(Root, ref=nav_ref),
        light=SUITE_LIGHT,
        dark=SUITE_DARK,
    )
