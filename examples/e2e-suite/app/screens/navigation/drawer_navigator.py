"""Demo screen for [`pn.create_drawer_navigator`][pythonnative.create_drawer_navigator].

A nested Drawer navigator with two screens. The "Go to One" / "Go to Two"
controls deliberately live in the demo body, *outside* the navigator's
swappable screens, and drive navigation through the drawer handle published
on a context.

Why not put the buttons inside the screens? Navigating tears down the
currently mounted screen subtree. A control that lives *inside* that subtree
therefore destroys itself the moment it fires. On some iOS simulators that
self-teardown leaves UIKit's touch delivery in a bad state and the *next*
tap is dropped, so the second navigation silently no-ops. The tab navigator
never hits this because its `TabBar` is persistent; this demo mirrors that by
keeping the navigation controls persistent too. See
``tests/e2e/AGENTS.md`` ("Controls that trigger their own teardown").
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, section

_Drawer = pn.create_drawer_navigator()

# Carries the drawer's navigation handle from inside the navigator (where
# ``use_navigation`` resolves it) out to the persistent buttons in the demo
# body. The value is the ``use_ref`` cell created by the demo component, so
# writes from the active screen are visible to the buttons' click handlers.
_NavBus = pn.create_context(None)


@pn.component
def _DrawerOne() -> pn.Element:
    nav = pn.use_navigation()
    bus = pn.use_context(_NavBus)
    if bus is not None:
        bus.current = nav
    return pn.Column(
        pn.Text("Drawer screen One", style=pn.style(font_size=18, font_weight="700")),
        pn.Button("Open drawer", on_press=nav.open_drawer),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def _DrawerTwo() -> pn.Element:
    nav = pn.use_navigation()
    bus = pn.use_context(_NavBus)
    if bus is not None:
        bus.current = nav
    return pn.Column(
        pn.Text("Drawer screen Two", style=pn.style(font_size=18, font_weight="700")),
        pn.Button("Open drawer", on_press=nav.open_drawer),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def DrawerNavigatorDemo() -> pn.Element:
    """Render a nested Drawer navigator with two screens."""
    bus = pn.use_ref(None)

    def _nav_to(route: str):
        def _handler() -> None:
            handle = bus.current
            if handle is not None:
                handle.navigate(route)

        return _handler

    return demo_screen(
        "Drawer Navigator",
        "Drawer with two screens; navigation driven from persistent controls.",
        section(
            "Drawer (nested)",
            pn.View(
                pn.Provider(
                    _NavBus,
                    bus,
                    _Drawer.Navigator(
                        _Drawer.Screen("One", component=_DrawerOne, options={"title": "One"}),
                        _Drawer.Screen("Two", component=_DrawerTwo, options={"title": "Two"}),
                    ),
                ),
                style=pn.style(height=260, border_radius=8, background_color="#F8FAFC"),
            ),
            buttons_row(
                pn.Button("Go to One", on_press=_nav_to("One")),
                pn.Button("Go to Two", on_press=_nav_to("Two")),
            ),
            hint(
                "'Go to One' / 'Go to Two' live outside the swapped screens (like a "
                "tab bar) so navigating never tears down the control that triggered it."
            ),
        ),
    )
