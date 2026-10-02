"""Demo screen for [`pn.use_context`][pythonnative.use_context],
[`pn.create_context`][pythonnative.create_context], and
[`Context.Provider`][pythonnative.Context.Provider].

A trivial string context (a mode name, not a ``pn.Theme``) with a Provider at the top and a consumer
child shows the value flowing through the tree. A button at the
top swaps the provided value so flows can verify reactive updates.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_ModeContext = pn.create_context("light")


@pn.component
def _Consumer() -> pn.Node:
    """Read and render the current theme value."""
    theme = pn.use_context(_ModeContext)
    return pn.Text(
        f"Consumer sees: {theme}",
        style=pn.style(font_weight="600", color="#0F172A"),
    )


@pn.component
def UseContextDemo() -> pn.Node:
    """Render a Provider with two values, swapping between them on tap."""
    theme, set_theme = pn.use_state("light")

    return DemoScreen(
        "use_context",
        "A Provider passes a value to a deeply nested consumer.",
        DemoSection(
            "Theme context",
            ResultText("Current theme", theme),
            _ModeContext.Provider(_Consumer(), value=theme),
            ButtonsRow(
                pn.Button("Set light", on_press=lambda: set_theme("light")),
                pn.Button("Set dark", on_press=lambda: set_theme("dark")),
            ),
            Hint("Tap 'Set dark' and the consumer line should show 'dark'."),
        ),
    )
