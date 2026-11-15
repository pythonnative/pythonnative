"""Demo screen for preemptible transitions and [`pn.start_transition`][pythonnative.start_transition].

"Render 120 rows" starts a transition whose rows are deliberately slow.
While it renders, the demo queues an urgent update (the way the bridge
queues a tap), so the transition is abandoned, the urgent update
commits first, and the rows render again. The screen reports whether
the urgent update landed before the rows.
"""

from __future__ import annotations

import time
from typing import Callable

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText
from pythonnative import scheduler


@pn.component
def SlowRow(index: int, version: int, interrupt: Callable[[], None]) -> pn.Node:
    """A row that takes about a millisecond to render, and interrupts its first new render."""
    if index == 10 and version > 0:
        interrupt()
    deadline = time.perf_counter() + 0.001
    while time.perf_counter() < deadline:
        pass
    return pn.Text(f"Row {index} v{version}")


@pn.component
def PreemptionDemo() -> pn.Node:
    """Render a slow list in a transition and interrupt it with an urgent update."""
    version, set_version = pn.use_state(0)
    taps, set_taps = pn.use_state(0)
    order = pn.use_ref("waiting")
    # A plain set, not a ref: a preempted render's ref writes roll back with it.
    interrupted: set[int] = pn.use_memo(set, [])

    if taps > 0 and order.current == "waiting":
        order.current = "urgent first" if version < taps else "rows first"

    def interrupt() -> None:
        # Fired from a row's render: what a tap arriving mid-render looks like.
        if version not in interrupted:
            interrupted.add(version)
            scheduler.queue_urgent(lambda: set_taps(lambda count: count + 1))

    def start() -> None:
        order.current = "waiting"
        pn.start_transition(lambda: set_version(version + 1))

    return DemoScreen(
        "Preemption",
        "A transition yields to urgent input: the tap commits first, then the rows render again.",
        DemoSection(
            "Transition",
            ResultText("Taps", taps),
            ResultText("Rows version", version),
            ResultText("Order", order.current),
            pn.Button("Render 120 rows", on_press=start),
        ),
        DemoSection("Rows", [SlowRow(i, version, interrupt).with_key(str(i)) for i in range(120)]),
        Hint("Maestro taps Render and waits for 'Rows version: 1' and 'Order: urgent first'."),
    )
