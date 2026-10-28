"""Demo screen for [`pn.run_async`][pythonnative.run_async].

A button kicks an async coroutine that flips a result line after a
short sleep. Confirms the runtime's asyncio loop is wired up.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def RunAsyncDemo() -> pn.Node:
    """Render a button that schedules an async coroutine via run_async."""
    last, set_last = pn.use_state("idle")

    async def _job() -> None:
        set_last("running")
        await asyncio.sleep(0.2)
        set_last("done")

    return DemoScreen(
        "run_async",
        "Fire-and-forget a coroutine on the framework asyncio loop.",
        DemoSection(
            "Async job",
            ResultText("Status", last),
            pn.Button("Run async job", on_press=lambda: pn.run_async(_job())),
            Hint("Maestro taps the button and waits for 'Status: done'."),
        ),
    )
