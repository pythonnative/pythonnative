"""Demo screen for [`pn.lazy`][pythonnative.lazy].

A lazily-defined component whose loader resolves after a short delay.
The first render suspends (the Suspense fallback shows); once the
loader finishes, the loaded component renders and stays cached for
subsequent renders.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def _HeavyWidget() -> pn.Element:
    return result_text("Widget", "loaded")


async def _load_widget() -> Any:
    await asyncio.sleep(0.6)
    return _HeavyWidget


_LazyWidget = pn.lazy(_load_widget)


@pn.component
def LazyDemo() -> pn.Element:
    """Render a code-split component behind a Suspense boundary."""
    return demo_screen(
        "lazy",
        "pn.lazy defers loading a component until its first render; Suspense covers the load.",
        section(
            "Lazy component",
            pn.Suspense(
                _LazyWidget(),
                fallback=result_text("Widget", "loading"),
            ),
            hint("Maestro waits for 'Widget: loaded' after the loader resolves."),
        ),
    )
