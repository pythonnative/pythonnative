"""Demo screen for [`pn.NavigationRef`][pythonnative.NavigationRef].

:mod:`app.navigation_ref` creates the [`NavigationRef`][pythonnative.NavigationRef]
that ``main.py`` binds to the root container. This demo reads it from
plain module code (no hook) and drives the root stack through it: the
"Navigate via ref" button opens the Route Params demo with a typed
parameter (``nav_ref.navigate(ParamsPassingDemo(value="from-ref"))``),
which that screen mirrors, and its "Back to list" button pops back here.
"""

from __future__ import annotations

import pythonnative as pn
from app.navigation_ref import nav_ref
from app.screens.navigation.params_passing import ParamsPassingDemo
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


def _navigate_via_ref() -> None:
    if nav_ref.is_ready():
        nav_ref.navigate(ParamsPassingDemo(value="from-ref"))


@pn.component
def NavigationRefDemo() -> pn.Node:
    """Render the ref's readiness and current route and navigate through it."""
    ready = nav_ref.is_ready()
    handle = nav_ref.current
    state = nav_ref.get_state() if ready else None

    return DemoScreen(
        "Navigation ref",
        "Drive the root stack from outside components through a NavigationRef.",
        DemoSection(
            "NavigationRef",
            ResultText("Ref ready", "yes" if ready else "no"),
            ResultText("Current route", handle.route.name if handle is not None else "(none)"),
            ResultText("Root routes", len(state.routes) if state is not None else 0),
            ResultText("Can go back", "yes" if handle is not None and handle.can_go_back() else "no"),
            ButtonsRow(pn.Button("Navigate via ref", on_press=_navigate_via_ref)),
            Hint("Maestro navigates via the ref, asserts the params readout, then pops back here."),
        ),
    )
