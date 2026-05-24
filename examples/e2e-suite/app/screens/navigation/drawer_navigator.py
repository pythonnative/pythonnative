"""Demo screen for [`pn.create_drawer_navigator`][pythonnative.create_drawer_navigator].

A nested Drawer navigator with two screens. We expose an explicit
"Open drawer" button rather than relying on swipe gestures so Maestro
can drive the demo deterministically.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

_Drawer = pn.create_drawer_navigator()


@pn.component
def _DrawerOne() -> pn.Element:
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Drawer screen One", style=pn.style(font_size=18, font_weight="700")),
        pn.Button("Open drawer", on_click=nav.open_drawer),
        pn.Button("Go to Two", on_click=lambda: nav.navigate("Two")),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def _DrawerTwo() -> pn.Element:
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Drawer screen Two", style=pn.style(font_size=18, font_weight="700")),
        pn.Button("Open drawer", on_click=nav.open_drawer),
        pn.Button("Go to One", on_click=lambda: nav.navigate("One")),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def DrawerNavigatorDemo() -> pn.Element:
    """Render a nested Drawer navigator with two screens."""
    return demo_screen(
        "Drawer Navigator",
        "Drawer with two screens; explicit Open drawer button.",
        section(
            "Drawer (nested)",
            pn.View(
                _Drawer.Navigator(
                    _Drawer.Screen("One", component=_DrawerOne, options={"title": "One"}),
                    _Drawer.Screen("Two", component=_DrawerTwo, options={"title": "Two"}),
                ),
                style=pn.style(height=320, border_radius=8, background_color="#F8FAFC"),
            ),
            hint("Maestro taps 'Go to Two' and asserts 'Drawer screen Two' is visible."),
        ),
    )
