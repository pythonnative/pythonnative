"""Demo screen for [`pn.Suspense`][pythonnative.Suspense] and async components.

An ``async def`` component awaits a fake fetch; the enclosing Suspense
boundary shows a fallback until the data arrives. A "Reload" button
remounts the async subtree (fresh key), so the fallback-then-content
cycle can be replayed.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


async def _fetch_greeting(round_number: int) -> str:
    await asyncio.sleep(0.8)
    return f"hello-{round_number}"


@pn.component
async def _Greeting(round_number: int = 1) -> pn.Element:
    """Async component: the body awaits data before returning its tree."""
    value = await _fetch_greeting(round_number)
    return result_text("Data", value)


@pn.component
def SuspenseDemo() -> pn.Element:
    """Show a Suspense fallback while an async component loads."""
    round_number, set_round = pn.use_state(1)

    return demo_screen(
        "Suspense",
        "An async def component suspends until its data arrives; Suspense shows the fallback meanwhile.",
        section(
            "Async content",
            pn.Suspense(
                _Greeting(round_number=round_number, key=str(round_number)),
                fallback=result_text("Data", "loading"),
            ),
            pn.Button("Reload", on_press=lambda: set_round(round_number + 1)),
            hint("Maestro waits for 'Data: hello-1', taps Reload, then waits for 'Data: hello-2'."),
        ),
    )
