"""Demo screen for typed route params and [`pn.use_route`][pythonnative.use_route].

A screen's parameters are its route params: ``ParamsPassingDemo`` takes
an optional ``value``, and ``nav.push(ParamsPassingDemo(value="alpha"))``
pushes a new entry whose params the type checker verifies. The demo
pushes itself with new params and shows both the typed argument and the
untyped params dict ``use_route()`` reports for the same route. ``push``
is used rather than ``navigate`` because ``navigate`` would merge the
params into the current entry instead of adding one, and the flow pops
back through the pushed entries.
"""

from __future__ import annotations

from typing import Optional

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def ParamsPassingDemo(value: Optional[str] = None) -> pn.Node:
    """Render the ``value`` param, as an argument and as ``use_route`` reports it."""
    route = pn.use_route()
    nav = pn.use_navigation()

    given = sorted(name for name, param in route.params.items() if param is not None)

    def push_with(next_value: str) -> None:
        nav.push(ParamsPassingDemo(value=next_value))

    return DemoScreen(
        "Route Params",
        "A screen's parameters are its route params; pushing with new params updates the readout.",
        DemoSection(
            "Route info",
            ResultText("Param 'value'", value or "(none)"),
            ResultText("Route name", route.name),
            ResultText("Route params", ", ".join(given) or "(none)"),
            ButtonsRow(
                pn.Button("Push value=alpha", on_press=lambda: push_with("alpha")),
                pn.Button("Push value=beta", on_press=lambda: push_with("beta")),
            ),
            Hint(
                "Maestro taps 'Push value=alpha' and asserts \"Param 'value': alpha\". "
                "Then taps the second button and asserts the param flipped to 'beta'."
            ),
        ),
    )
