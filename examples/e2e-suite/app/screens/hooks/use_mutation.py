"""Demo screen for [`pn.use_mutation`][pythonnative.use_mutation].

A fake "submit" mutation resolves to the value it was called with.
Maestro taps the submit button and asserts the result line.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


async def _submit(payload: str) -> str:
    await asyncio.sleep(0.15)
    return f"echo:{payload}"


@pn.component
def UseMutationDemo() -> pn.Node:
    """Render a submit button that fires a use_mutation call."""
    state, run = pn.use_mutation(_submit)

    if state.loading:
        status = "submitting"
    elif state.error is not None:
        status = f"error: {state.error}"
    else:
        status = "idle"

    return DemoScreen(
        "use_mutation",
        "use_mutation tracks loading, error, and last data fields.",
        DemoSection(
            "Mutation",
            ResultText("Status", status),
            ResultText("Last data", state.data or "(none)"),
            pn.Button("Submit hello", on_press=lambda: run("hello")),
            Hint("Tap submit; Maestro asserts 'Last data: echo:hello'."),
        ),
    )
