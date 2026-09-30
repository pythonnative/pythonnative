"""Demo screen for [`pn.use_callback`][pythonnative.use_callback].

The hook returns a stable reference for a callback as long as its
deps don't change. We expose this by tracking the identity of the
returned function across renders.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseCallbackDemo() -> pn.Node:
    """Render a stable-identity callback compared across renders."""
    dep, set_dep = pn.use_state(0)
    other, set_other = pn.use_state(0)
    last_id = pn.use_ref(None)
    changes = pn.use_ref(0)

    cb = pn.use_callback(lambda: None, [dep])

    if last_id.current is None:
        last_id.current = id(cb)
    elif last_id.current != id(cb):
        changes.current += 1
        last_id.current = id(cb)

    return DemoScreen(
        "use_callback",
        "Function identity stays stable until dep changes.",
        DemoSection(
            "Identity tracking",
            ResultText("Identity changes", changes.current),
            ResultText("Dep value", dep),
            ResultText("Other value", other),
            ButtonsRow(
                pn.Button("Change dep", on_press=lambda: set_dep(dep + 1)),
                pn.Button("Change other", on_press=lambda: set_other(other + 1)),
            ),
            Hint("Tapping 'Change other' must NOT bump 'Identity changes'. Tapping 'Change dep' bumps it by 1."),
        ),
    )
