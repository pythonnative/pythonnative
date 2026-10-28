"""Demo screen for [`pn.use_query`][pythonnative.use_query].

A fake fetch resolves to a fixed string after ~300 ms. The demo shows
loading, success, and refetch, all three pieces of the
[`QueryResult`][pythonnative.QueryResult] API.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


async def _fake_fetch() -> str:
    await asyncio.sleep(0.3)
    return "fetched-value"


@pn.component
def UseQueryDemo() -> pn.Node:
    """Render the result of a use_query call plus a refetch button."""
    q = pn.use_query(_fake_fetch, [])

    if q.loading and q.data is None:
        status = "loading"
    elif q.error is not None:
        status = f"error: {q.error}"
    else:
        status = "ready"

    return DemoScreen(
        "use_query",
        "use_query manages loading, success, and refetch state.",
        DemoSection(
            "Query",
            ResultText("Status", status),
            ResultText("Data", q.data or "(none)"),
            pn.Button("Refetch", on_press=q.refetch),
            Hint("Maestro waits for 'Data: fetched-value' after the fetch resolves."),
        ),
    )
