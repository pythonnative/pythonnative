"""Demo screen for async [`pn.use_effect`][pythonnative.use_effect] callbacks.

``use_effect`` accepts ``async def`` callbacks directly: the coroutine
runs as a task on the framework loop and is cancelled automatically on
unmount or deps change. This demo's effect waits 200 ms before flipping
a "completed" flag. Maestro asserts the initial "loading" line, then
re-asserts after the effect resolves.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def AsyncEffectDemo() -> pn.Element:
    """Run an async effect that flips a 'done' flag after a short delay."""
    done, set_done = pn.use_state(False)

    async def _eventually_done() -> None:
        await asyncio.sleep(0.2)
        set_done(True)

    pn.use_effect(_eventually_done, [])

    return demo_screen(
        "async use_effect",
        "An async def effect resolves after a short delay and flips the status line.",
        section(
            "Status",
            result_text("Status", "done" if done else "loading"),
            hint("Maestro waits for 'Status: done' (timeout 5s)."),
        ),
    )
