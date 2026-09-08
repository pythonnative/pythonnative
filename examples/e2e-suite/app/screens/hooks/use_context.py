"""Demo screen for [`pn.use_context`][pythonnative.use_context],
[`pn.create_context`][pythonnative.create_context], and
[`Context.Provider`][pythonnative.Context.Provider].

A trivial theme context with a Provider at the top and a consumer
child shows the value flowing through the tree. A button at the
top swaps the provided value so flows can verify reactive updates.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_ThemeContext = pn.create_context("light")


@pn.component
def _Consumer() -> pn.Element:
    """Read and render the current theme value."""
    theme = pn.use_context(_ThemeContext)
    return pn.Text(
        f"Consumer sees: {theme}",
        style=pn.style(font_weight="600", color="#0F172A"),
    )


@pn.component
def UseContextDemo() -> pn.Element:
    """Render a Provider with two values, swapping between them on tap."""
    theme, set_theme = pn.use_state("light")

    return demo_screen(
        "use_context",
        "A Provider passes a value to a deeply nested consumer.",
        section(
            "Theme context",
            result_text("Current theme", theme),
            _ThemeContext.Provider(theme, _Consumer()),
            buttons_row(
                pn.Button("Set light", on_press=lambda: set_theme("light")),
                pn.Button("Set dark", on_press=lambda: set_theme("dark")),
            ),
            hint("Tap 'Set dark' and the consumer line should show 'dark'."),
        ),
    )
