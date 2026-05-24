"""Demo screen for [`pn.create_tab_navigator`][pythonnative.create_tab_navigator].

A nested Tab navigator with three labelled tabs lives inside the
current Stack screen. Maestro asserts that tab switching reveals the
expected body text on each tab.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

_Tab = pn.create_tab_navigator()


@pn.component
def _TabAlpha() -> pn.Element:
    return pn.Column(
        pn.Text("Tab Alpha body", style=pn.style(font_size=18, font_weight="700")),
        pn.Text("This is the Alpha tab content.", style=pn.style(color="#475569")),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def _TabBeta() -> pn.Element:
    return pn.Column(
        pn.Text("Tab Beta body", style=pn.style(font_size=18, font_weight="700")),
        pn.Text("This is the Beta tab content.", style=pn.style(color="#475569")),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def _TabGamma() -> pn.Element:
    return pn.Column(
        pn.Text("Tab Gamma body", style=pn.style(font_size=18, font_weight="700")),
        pn.Text("This is the Gamma tab content.", style=pn.style(color="#475569")),
        style=pn.style(spacing=8, padding=16),
    )


@pn.component
def TabNavigatorDemo() -> pn.Element:
    """Render a nested Tab navigator with three labelled tabs."""
    return demo_screen(
        "Tab Navigator",
        "Nested Tab navigator with three tabs. Tap each to reveal its body.",
        section(
            "Tabs (nested)",
            pn.View(
                _Tab.Navigator(
                    _Tab.Screen("Alpha", component=_TabAlpha, options={"title": "Alpha"}),
                    _Tab.Screen("Beta", component=_TabBeta, options={"title": "Beta"}),
                    _Tab.Screen("Gamma", component=_TabGamma, options={"title": "Gamma"}),
                ),
                style=pn.style(height=320, border_radius=8, background_color="#F8FAFC"),
            ),
            hint("Maestro asserts each tab's body after tapping its label."),
        ),
    )
