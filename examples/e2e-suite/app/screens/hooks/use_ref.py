"""Demo screen for [`pn.use_ref`][pythonnative.use_ref].

``use_ref`` provides a mutable container whose changes don't trigger
a re-render. The demo combines a ref-backed counter with a
re-render trigger so Maestro can observe two distinct values: the
"silent" ref value (only visible on re-render) and the render-tracked
state value.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseRefDemo() -> pn.Node:
    """Render a ref-driven counter and a render-trigger counter."""
    silent = pn.use_ref(0)
    renders, set_renders = pn.use_state(0)

    def bump_silent() -> None:
        silent.current += 1

    def force_render() -> None:
        set_renders(renders + 1)

    return DemoScreen(
        "use_ref",
        "Compare a silent ref counter to a re-render-driving state counter.",
        DemoSection(
            "Counters",
            ResultText("Silent ref value", silent.current),
            ResultText("Renders", renders),
            ButtonsRow(
                pn.Button("Bump silent", on_press=bump_silent),
                pn.Button("Force render", on_press=force_render),
            ),
            Hint(
                "Bump silent N times: 'Silent ref value' stays 0 until a "
                "render happens. Tap 'Force render' to surface the new value."
            ),
        ),
    )
