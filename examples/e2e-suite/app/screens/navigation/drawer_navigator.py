"""Demo screen for [`pn.DrawerNavigator`][pythonnative.DrawerNavigator].

A module-level drawer navigator with two screens, rendered inside the
demo body. The "Go to One" / "Go to Two" controls deliberately live in
the demo body, *outside* the navigator's swappable screens, and drive
navigation through the drawer handle published on a context.

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

from typing import Callable, Optional

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint
from pythonnative.navigation import DrawerNavigation

HandleRef = pn.Ref[Optional[DrawerNavigation]]
"""Carries the drawer's handle from inside the navigator out to the persistent buttons."""

# ``use_navigation`` only resolves the drawer's handle inside the drawer's
# screens; the demo body provides this ref so the active screen can publish
# its handle for the buttons' press handlers.
_HandleBus: pn.Context[Optional[HandleRef]] = pn.create_context(None)


def use_publish_drawer() -> Optional[DrawerNavigation]:
    """Publish this screen's drawer handle on the bus while it's focused, and return it."""
    nav = pn.use_navigation()
    bus = pn.use_context(_HandleBus)
    drawer = nav if isinstance(nav, DrawerNavigation) else None

    def publish() -> None:
        if bus is not None:
            bus.current = drawer

    pn.use_focus_effect(publish, [bus, drawer])
    return drawer


@pn.component
def DrawerOne() -> pn.Node:
    """The drawer's first screen."""
    drawer = use_publish_drawer()
    return pn.Column(
        pn.Text("Drawer screen One", style=pn.style(font_size=18, font_weight="700")),
        pn.Button("Open drawer", on_press=drawer.open_drawer) if drawer is not None else None,
        style=pn.style(gap=8, padding=16),
    )


@pn.component
def DrawerTwo() -> pn.Node:
    """The drawer's second screen."""
    drawer = use_publish_drawer()
    return pn.Column(
        pn.Text("Drawer screen Two", style=pn.style(font_size=18, font_weight="700")),
        pn.Button("Open drawer", on_press=drawer.open_drawer) if drawer is not None else None,
        style=pn.style(gap=8, padding=16),
    )


DemoDrawer = pn.DrawerNavigator(
    pn.Screen(DrawerOne, name="One", title="One"),
    pn.Screen(DrawerTwo, name="Two", title="Two"),
)
"""The drawer rendered inside the demo body."""


@pn.component
def DrawerNavigatorDemo() -> pn.Node:
    """Render the drawer navigator with persistent navigation controls."""
    bus: HandleRef = pn.use_ref(None)

    def go_to(target: pn.Component[[]]) -> Callable[[], None]:
        def _handler() -> None:
            if bus.current is not None:
                bus.current.jump_to(target)

        return _handler

    return DemoScreen(
        "Drawer Navigator",
        "Drawer with two screens; navigation driven from persistent controls.",
        DemoSection(
            "Drawer (nested)",
            pn.View(
                _HandleBus.Provider(DemoDrawer(), value=bus),
                style=pn.style(height=260, border_radius=8, background_color="#F8FAFC"),
            ),
            ButtonsRow(
                pn.Button("Go to One", on_press=go_to(DrawerOne)),
                pn.Button("Go to Two", on_press=go_to(DrawerTwo)),
            ),
            Hint(
                "'Go to One' / 'Go to Two' live outside the swapped screens (like a "
                "tab bar) so navigating never tears down the control that triggered it."
            ),
        ),
    )
