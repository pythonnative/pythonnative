"""Demo screen for [`pn.use_memo`][pythonnative.use_memo].

A memoized factory tracks how many times it ran. The factory only
fires when its dependency array changes, so flows can confirm the
``use_memo`` cache works by toggling a button that doesn't change
the dep.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseMemoDemo() -> pn.Element:
    """Render a memo whose factory bumps a counter only on dep change."""
    runs = pn.use_ref(0)
    dep, set_dep = pn.use_state(0)
    other, set_other = pn.use_state(0)

    def _expensive() -> int:
        runs["current"] += 1
        return dep * 2

    memoized = pn.use_memo(_expensive, [dep])

    return demo_screen(
        "use_memo",
        "Factory only re-runs when its dep array changes.",
        section(
            "Memo",
            result_text("Factory runs", runs["current"]),
            result_text("Memo value", memoized),
            result_text("Other state", other),
            buttons_row(
                pn.Button("Change dep", on_click=lambda: set_dep(dep + 1)),
                pn.Button("Change other", on_click=lambda: set_other(other + 1)),
            ),
            hint("Tap 'Change other' — factory runs stays the same. " "Tap 'Change dep' — factory runs goes up."),
        ),
    )
