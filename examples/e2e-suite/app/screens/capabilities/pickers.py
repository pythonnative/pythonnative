"""Demo screen for [`pythonnative.pickers`][pythonnative.pickers].

Each button opens a system picker and the readout shows what came back. A
cancel is an empty list, not an error, so the readout says "canceled".
``photo_library`` reports the status of the permission this plugin owns, which
the pickers themselves don't need.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, List

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText
from pythonnative.native_modules.registry import NativeModuleError
from pythonnative.pickers import PickedFile, pick_documents, pick_images, pick_videos


def _describe(files: List[PickedFile]) -> str:
    if not files:
        return "canceled"
    first = files[0]
    return f"{len(files)} file(s), first {first.name} ({first.mime_type}, {first.size} bytes)"


@pn.component
def PickersDemo() -> pn.Node:
    """Render one button per picker and a readout of the last result."""
    result, set_result = pn.use_state("none")
    status, set_status = pn.use_state("unknown")

    def guarded(work: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[None]]:
        async def run() -> None:
            try:
                set_result(_describe(await work()))
            except NativeModuleError as failure:
                set_result(f"error {failure.code}")

        return run

    async def check_library() -> None:
        set_status(await pn.Permissions.check("photo_library"))

    return DemoScreen(
        "Pickers",
        "pick_images, pick_videos, and pick_documents.",
        DemoSection(
            "System pickers",
            Hint("Cancel a picker to see that it returns an empty list."),
            ResultText("Last pick", result),
            pn.Button("Pick images", on_press=guarded(lambda: pick_images(limit=3))),
            pn.Button("Pick a video", on_press=guarded(pick_videos)),
            pn.Button("Pick a document", on_press=guarded(pick_documents)),
            pn.Button("Pick PDFs", on_press=guarded(lambda: pick_documents(types=["application/pdf"], multiple=True))),
        ),
        DemoSection(
            "Permission",
            ResultText("Photo library", status),
            pn.Button("Check photo library", on_press=check_library),
        ),
    )
