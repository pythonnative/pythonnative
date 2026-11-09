"""Demo screen for [`pn.BottomSheet`][pythonnative.BottomSheet] and its handle.

The handle is a [`BottomSheetHandle`][pythonnative.BottomSheetHandle].

The sheet starts closed (``index=-1``) with two detents. "Open sheet"
calls ``ref.current.snap_to(0)``. Dragging the handle runs worklets on
the UI thread and settles on the detent the release projects to; the
sheet reports it through ``on_change`` (and ``on_close`` when dragged
below the lowest detent). The buttons inside the sheet drive the handle
(``expand``, ``collapse``, ``close``), which reports the same way once
the sheet settles, and "Last request" records each call.
"""

from __future__ import annotations

from typing import Any

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def BottomSheetDemo() -> pn.Node:
    """Open a two-detent sheet and drive it by drag and by its handle."""
    sheet = pn.use_ref(None)
    index, set_index = pn.use_state("closed")
    changes, set_changes = pn.use_state(0)
    request, set_request = pn.use_state("none")

    def on_change(position: int) -> None:
        set_index(str(position))
        set_changes(lambda n: n + 1)

    def on_close() -> None:
        set_index("closed")

    def call(name: str) -> None:
        handle: Any = sheet.current
        set_request(name)
        if name == "open":
            handle.snap_to(0)
        elif name == "expand":
            handle.expand()
        elif name == "collapse":
            handle.collapse()
        else:
            handle.close()

    return DemoScreen(
        "BottomSheet",
        "A sheet with two detents that follows the finger and snaps on release.",
        DemoSection(
            "Sheet state",
            ResultText("Sheet index", index),
            ResultText("Sheet changes", changes),
            ResultText("Last request", request),
            ButtonsRow(pn.Button("Open sheet", on_press=lambda: call("open"))),
            Hint("Maestro opens the sheet, drags its handle up, and asserts 'Sheet index: 1'."),
        ),
        pn.BottomSheet(
            pn.Column(
                pn.Text("Sheet content", style=pn.style(font_size=17, font_weight="700")),
                ButtonsRow(
                    pn.Button("Sheet expand", on_press=lambda: call("expand")),
                    pn.Button("Sheet collapse", on_press=lambda: call("collapse")),
                ),
                ButtonsRow(pn.Button("Sheet dismiss", on_press=lambda: call("close"))),
                style=pn.style(gap=12, padding=16),
            ),
            snap_points=(220, 420),
            index=-1,
            on_change=on_change,
            on_close=on_close,
            ref=sheet,
        ),
    )
