"""Demo screen for [`pn.use_resource`][pythonnative.use_resource].

A resource fetches an item keyed by its id. Reading it suspends the
first render (the Suspense fallback shows); changing the id on an
already-mounted component keeps the previous item on screen until the
new fetch resolves (no fallback flash).
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


async def _fetch_item(item_id: int) -> str:
    await asyncio.sleep(0.5)
    return f"item-{item_id}"


@pn.component
def _ItemCard(item_id: int = 1) -> pn.Element:
    resource = pn.use_resource(lambda: _fetch_item(item_id), [item_id])
    return result_text("Item", resource.read())


@pn.component
def UseResourceDemo() -> pn.Element:
    """Fetch-on-render with caching; deps changes refetch."""
    item_id, set_item_id = pn.use_state(1)

    return demo_screen(
        "use_resource",
        "use_resource starts a fetch during render and caches it; read() suspends until the data is ready.",
        section(
            "Resource",
            pn.Suspense(
                _ItemCard(item_id=item_id),
                fallback=result_text("Item", "loading"),
            ),
            pn.Button("Next item", on_press=lambda: set_item_id(item_id + 1)),
            hint("Maestro waits for 'Item: item-1', taps Next item, then waits for 'Item: item-2'."),
        ),
    )
