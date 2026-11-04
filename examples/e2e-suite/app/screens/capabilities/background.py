"""Demo screen for [`pythonnative.background`][pythonnative.background].

``e2e_sync`` is declared at import, which the registry's import of this module
guarantees. "Run now" calls its Python function in-process. "Schedule" asks the
system for real, and shows what it answers: Android accepts, and an iOS simulator
always refuses with ``unavailable``. Nothing here waits for the system to start
the task, which no flow could do. See the capability guide for how to force that.
"""

from __future__ import annotations

from datetime import timedelta

from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative import background
from pythonnative.native_modules.registry import NativeModuleError

_runs = 0


@background.task("e2e_sync", every=timedelta(minutes=15))
async def _sync() -> background.Result:
    global _runs
    _runs += 1
    return background.Result.SUCCESS


def _row() -> background.TaskStatus:
    return next(row for row in background.status() if row.name == "e2e_sync")


@pn.component
def BackgroundDemo() -> pn.Node:
    """Render controls and readouts for one declared task."""
    row, set_row = pn.use_state(_row)
    result, set_result = pn.use_state("none")
    runs, set_runs = pn.use_state(_runs)
    answer, set_answer = pn.use_state("none")

    async def run_now() -> None:
        outcome = await background.run_now("e2e_sync")
        set_result(outcome.value)
        set_runs(_runs)

    def schedule() -> None:
        try:
            background.schedule("e2e_sync")
            set_answer("accepted")
        except NativeModuleError as error:
            set_answer(error.code or "failed")
        set_row(_row())

    def cancel() -> None:
        background.cancel("e2e_sync")
        set_answer("canceled")
        set_row(_row())

    return DemoScreen(
        "Background",
        "@background.task, schedule, cancel, status, and run_now.",
        DemoSection(
            "Task e2e_sync",
            ResultText("Every", f"{int(row.every.total_seconds() / 60)} minutes" if row.every else "unknown"),
            ResultText("Run now result", result),
            ResultText("Runs", runs),
            pn.Button("Run now", on_press=run_now),
        ),
        DemoSection(
            "System scheduler",
            ResultText("Schedule answer", answer),
            ResultText("Scheduled", "yes" if row.scheduled else "no"),
            ButtonsRow(
                pn.Button("Schedule", on_press=schedule),
                pn.Button("Cancel task", on_press=cancel),
            ),
            Hint("An iOS simulator always refuses to schedule. Devices and Android accept."),
        ),
    )
