"""Demo screen for navigation params and [`pn.use_route`][pythonnative.use_route].

The Stack screen for this demo (route id ``"params_passing"``) reads
its route params via ``pn.use_route()``. To exercise that without
needing a second Stack screen, the demo navigates back to its own
route id with new params and asserts the readout updates.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def ParamsPassingDemo() -> pn.Element:
    """Render the active route's params using ``use_route``."""
    params = pn.use_route()
    nav = pn.use_navigation()

    def push_with(value: str) -> None:
        nav.navigate("params_passing", {"value": value})

    return demo_screen(
        "Route Params",
        "use_route reads the active route's params; navigating with new params updates the readout.",
        section(
            "Route info",
            result_text("Param 'value'", params.get("value") or "(none)"),
            buttons_row(
                pn.Button("Push value=alpha", on_press=lambda: push_with("alpha")),
                pn.Button("Push value=beta", on_press=lambda: push_with("beta")),
            ),
            hint(
                "Maestro taps 'Push value=alpha' and asserts \"Param 'value': alpha\". "
                "Then taps the second button and asserts the param flipped to 'beta'."
            ),
        ),
    )
