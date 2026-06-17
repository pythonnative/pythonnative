"""Demo screen for [`pn.use_query`][pythonnative.use_query].

A fake fetch resolves to a fixed string after ~300 ms. The demo shows
loading, success, and refetch, all three pieces of the
[`QueryResult`][pythonnative.QueryResult] API.
"""

from __future__ import annotations

import asyncio

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


async def _fake_fetch() -> str:
    await asyncio.sleep(0.3)
    return "fetched-value"


@pn.component
def UseQueryDemo() -> pn.Element:
    """Render the result of a use_query call plus a refetch button."""
    q = pn.use_query(_fake_fetch, [])

    if q.loading and q.data is None:
        status = "loading"
    elif q.error is not None:
        status = f"error: {q.error}"
    else:
        status = "ready"

    return demo_screen(
        "use_query",
        "use_query manages loading, success, and refetch state.",
        section(
            "Query",
            result_text("Status", status),
            result_text("Data", q.data or "(none)"),
            pn.Button("Refetch", on_click=q.refetch),
            hint("Maestro waits for 'Data: fetched-value' after the fetch resolves."),
        ),
    )
