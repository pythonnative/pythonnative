"""Demo screen for [`pn.use_mutation`][pythonnative.use_mutation].

A fake "submit" mutation resolves to the value it was called with.
Maestro taps the submit button and asserts the result line.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


async def _submit(payload: str) -> str:
    await asyncio.sleep(0.15)
    return f"echo:{payload}"


@pn.component
def UseMutationDemo() -> pn.Element:
    """Render a submit button that fires a use_mutation call."""
    state, run = pn.use_mutation(_submit)

    if state.loading:
        status = "submitting"
    elif state.error is not None:
        status = f"error: {state.error}"
    else:
        status = "idle"

    return demo_screen(
        "use_mutation",
        "use_mutation tracks loading, error, and last data fields.",
        section(
            "Mutation",
            result_text("Status", status),
            result_text("Last data", state.data or "(none)"),
            pn.Button("Submit hello", on_click=lambda: run("hello")),
            hint("Tap submit; Maestro asserts 'Last data: echo:hello'."),
        ),
    )
