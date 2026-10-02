"""Demo screen for [`pn.lazy`][pythonnative.lazy].

A lazily-defined component whose loader resolves after a short delay.
The first render suspends (the Suspense fallback shows); once the
loader finishes, the loaded component renders and stays cached for
subsequent renders.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def _HeavyWidget() -> pn.Node:
    return ResultText("Widget", "loaded")


async def _load_widget() -> pn.Component[[]]:
    await asyncio.sleep(0.6)
    return _HeavyWidget


_LazyWidget = pn.lazy(_load_widget)


@pn.component
def LazyDemo() -> pn.Node:
    """Render a code-split component behind a Suspense boundary."""
    return DemoScreen(
        "lazy",
        "pn.lazy defers loading a component until its first render; Suspense covers the load.",
        DemoSection(
            "Lazy component",
            pn.Suspense(
                _LazyWidget(),
                fallback=ResultText("Widget", "loading"),
            ),
            Hint("Maestro waits for 'Widget: loaded' after the loader resolves."),
        ),
    )
