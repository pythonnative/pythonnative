"""E2E suite entry point.

Wires every demo screen from :mod:`app.registry` into the root
[`Stack.Navigator`][pythonnative.create_stack_navigator]. The first
route, ``"Home"``, is a categorized list of buttons that opens the
rest of the demos. Each demo screen owns its own back navigation via
[`use_navigation().go_back()`][pythonnative.use_navigation].

The stack-only architecture keeps the navigation surface flat and
predictable for automated tests: every demo is reachable in exactly
one push, and every back press lands the user back on ``"Home"``.
"""

from __future__ import annotations

import pythonnative as pn
from app.registry import DEMOS
from app.screens.category import CategoryListScreen
from app.screens.home import HomeScreen

print("[e2e-suite] main module imported")

Stack = pn.create_stack_navigator()


@pn.component
def App() -> pn.Element:
    """Root component: a Stack with Home, every Category screen, and every demo."""
    return pn.NavigationContainer(
        Stack.Navigator(
            Stack.Screen("Home", component=HomeScreen, options={"title": "PythonNative E2E Suite"}),
            Stack.Screen(
                "Category",
                component=CategoryListScreen,
                options={"title": "Category"},
            ),
            *(Stack.Screen(demo.id, component=demo.component, options={"title": demo.title}) for demo in DEMOS),
        )
    )
