"""Demo screen for [`pn.use_memo`][pythonnative.use_memo].

A memoized factory tracks how many times it ran. The factory only
fires when its dependency array changes, so flows can confirm the
``use_memo`` cache works by toggling a button that doesn't change
the dep.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseMemoDemo() -> pn.Node:
    """Render a memo whose factory bumps a counter only on dep change."""
    runs = pn.use_ref(0)
    dep, set_dep = pn.use_state(0)
    other, set_other = pn.use_state(0)

    def _expensive() -> int:
        runs.current += 1
        return dep * 2

    memoized = pn.use_memo(_expensive, [dep])

    return DemoScreen(
        "use_memo",
        "Factory only re-runs when its dep array changes.",
        DemoSection(
            "Memo",
            ResultText("Factory runs", runs.current),
            ResultText("Memo value", memoized),
            ResultText("Other state", other),
            ButtonsRow(
                pn.Button("Change dep", on_press=lambda: set_dep(dep + 1)),
                pn.Button("Change other", on_press=lambda: set_other(other + 1)),
            ),
            Hint("Tap 'Change other': factory runs stays the same. Tap 'Change dep': factory runs goes up."),
        ),
    )
