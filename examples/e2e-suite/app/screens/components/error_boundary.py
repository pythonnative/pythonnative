"""Demo screen for [`pn.ErrorBoundary`][pythonnative.ErrorBoundary].

A child component throws unconditionally; the boundary should
intercept the error and render a stable fallback message. Maestro
asserts the fallback is visible.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


@pn.component
def Crasher() -> pn.Node:
    """A child component that raises on render so the boundary fires."""
    raise RuntimeError("Crasher: intentional render error for ErrorBoundary demo")


@pn.component
def ErrorBoundaryDemo() -> pn.Node:
    """Render an ErrorBoundary wrapping a deliberately-crashing child."""
    return DemoScreen(
        "ErrorBoundary",
        "The crashing child should be replaced by the fallback below.",
        DemoSection(
            "Boundary",
            pn.ErrorBoundary(
                Crasher(),
                fallback=pn.Text(
                    "Caught render error",
                    style=pn.style(color="#B91C1C", font_weight="700", font_size=16),
                ),
            ),
            Hint("Maestro asserts 'Caught render error' is visible."),
        ),
    )
