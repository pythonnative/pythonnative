"""Demo screen for [`pn.AsyncStorage`][pythonnative.AsyncStorage].

Saves a value under a stable key, then reads it back into a result
line. Every async operation flips the readout when it *completes*
("(written)" / "(cleared)") so Maestro can await each transition
instead of racing the storage I/O on slow CI runners.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_KEY = "e2e.async_storage_demo"


@pn.component
def AsyncStorageDemo() -> pn.Element:
    """Render write / read / clear buttons for an AsyncStorage entry."""
    value, set_value = pn.use_state("(unread)")

    async def _write() -> None:
        await pn.AsyncStorage.set(_KEY, "stored-value")
        set_value("(written)")

    async def _read() -> None:
        v = await pn.AsyncStorage.get(_KEY)
        set_value(v or "(none)")

    async def _clear() -> None:
        await pn.AsyncStorage.delete(_KEY)
        set_value("(cleared)")

    return demo_screen(
        "AsyncStorage",
        "Write a value, read it back, optionally clear it.",
        section(
            "Storage I/O",
            result_text("Read value", value),
            buttons_row(
                pn.Button("Write", on_click=lambda: pn.run_async(_write())),
                pn.Button("Read", on_click=lambda: pn.run_async(_read())),
                pn.Button("Clear", on_click=lambda: pn.run_async(_clear())),
            ),
            hint("Tap Write, then Read; assert 'Read value: stored-value'."),
        ),
    )
