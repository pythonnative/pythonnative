"""Demo screen for [`pn.TabNavigator`][pythonnative.TabNavigator] and static nesting.

:data:`DemoTabs` is a module-level tab navigator with three labelled
tabs, rendered inside the current stack screen. The Gamma tab is itself
a [`StackNavigator`][pythonnative.StackNavigator] listed as a screen, so
it's *statically* nested: the Alpha tab's "Open Gamma detail" button
calls ``nav.navigate(GammaDetail(item=7))``, and the navigator finds the
detail screen inside the nested stack, switches to the Gamma tab, and
pushes it. Maestro asserts that tab switching reveals the expected body
text on each tab.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint

_TITLE = pn.style(font_size=18, font_weight="700")
_BODY = pn.style(color="#475569")
_PAGE = pn.style(gap=8, padding=16)


@pn.component
def TabAlpha() -> pn.Node:
    """The first tab; it can open a screen inside the nested Gamma stack."""
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text("Tab Alpha body", style=_TITLE),
        pn.Text("This is the Alpha tab content.", style=_BODY),
        pn.Button("Open Gamma detail", on_press=lambda: nav.navigate(GammaDetail(item=7))),
        style=_PAGE,
    )


@pn.component
def TabBeta() -> pn.Node:
    """The second tab."""
    return pn.Column(
        pn.Text("Tab Beta body", style=_TITLE),
        pn.Text("This is the Beta tab content.", style=_BODY),
        style=_PAGE,
    )


@pn.component
def GammaHome() -> pn.Node:
    """The Gamma stack's first screen."""
    return pn.Column(
        pn.Text("Tab Gamma body", style=_TITLE),
        pn.Text("This tab is a stack navigator nested in the tabs.", style=_BODY),
        style=_PAGE,
    )


@pn.component
def GammaDetail(item: int) -> pn.Node:
    """A Gamma stack screen with a typed param, reached from the Alpha tab."""
    nav = pn.use_navigation()
    return pn.Column(
        pn.Text(f"Gamma detail: {item}", style=_TITLE),
        pn.Button("Back to Gamma", on_press=nav.go_back),
        style=_PAGE,
    )


GammaStack = pn.StackNavigator(
    pn.Screen(GammaHome, name="GammaHome"),
    pn.Screen(GammaDetail, name="GammaDetail"),
    screen_options=pn.ScreenOptions(header_shown=False),
    name="Gamma",
)
"""The stack rendered by the Gamma tab."""

DemoTabs = pn.TabNavigator(
    pn.Screen(TabAlpha, name="Alpha", title="Alpha"),
    pn.Screen(TabBeta, name="Beta", title="Beta"),
    pn.Screen(GammaStack, title="Gamma"),
)
"""Three tabs; the last one is a statically nested stack."""


@pn.component
def TabNavigatorDemo() -> pn.Node:
    """Render the tab navigator inside the demo body."""
    return DemoScreen(
        "Tab Navigator",
        "Nested Tab navigator with three tabs. Tap each to reveal its body.",
        DemoSection(
            "Tabs (nested)",
            pn.View(
                DemoTabs(),
                style=pn.style(height=320, border_radius=8, background_color="#F8FAFC"),
            ),
            Hint("Maestro asserts each tab's body after tapping its label."),
            Hint("'Open Gamma detail' navigates into the stack nested in the Gamma tab."),
        ),
    )
