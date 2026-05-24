"""Demo screen for [`pn.run_async`][pythonnative.run_async].

A button kicks an async coroutine that flips a result line after a
short sleep. Confirms the runtime's asyncio loop is wired up.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def RunAsyncDemo() -> pn.Element:
    """Render a button that schedules an async coroutine via run_async."""
    last, set_last = pn.use_state("idle")

    async def _job() -> None:
        set_last("running")
        await asyncio.sleep(0.2)
        set_last("done")

    return demo_screen(
        "run_async",
        "Fire-and-forget a coroutine on the framework asyncio loop.",
        section(
            "Async job",
            result_text("Status", last),
            pn.Button("Run async job", on_click=lambda: pn.run_async(_job())),
            hint("Maestro taps the button and waits for 'Status: done'."),
        ),
    )
