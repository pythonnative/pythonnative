"""Demo screen for [`CameraView`][pythonnative.camera.CameraView] and [`Camera`][pythonnative.camera.Camera].

The readouts mirror every event: ``on_ready``, ``on_error``, and ``on_barcode``.
The buttons exercise the handle's ``take_picture``, ``start_recording``, and
``stop_recording``, and the ``facing``, ``flash``, and ``zoom`` props. The iOS
simulator has no camera, so there the view shows its placeholder, ``on_error``
reports ``unavailable``, and the handle raises ``not_ready``.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Literal

from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.camera import Barcode, Camera, CameraError, CameraView
from pythonnative.native_modules.registry import NativeModuleError

_INITIAL_FACING: Literal["back", "front"] = "back"
_INITIAL_FLASH: Literal["off", "on", "auto", "torch"] = "off"


@pn.component
def CameraDemo() -> pn.Node:
    """Render a live preview, its event readouts, and the controls that drive it."""
    camera = pn.use_ref()
    ready, set_ready = pn.use_state(False)
    error, set_error = pn.use_state("none")
    barcode, set_barcode = pn.use_state("none")
    result, set_result = pn.use_state("none")
    facing, set_facing = pn.use_state(_INITIAL_FACING)
    flash, set_flash = pn.use_state(_INITIAL_FLASH)
    zoom, set_zoom = pn.use_state(1.0)

    def guarded(work: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[None]]:
        async def run() -> None:
            try:
                set_result(await work())
            except NativeModuleError as failure:
                set_result(f"error {failure.code}")

        return run

    async def picture() -> str:
        photo = await camera.current.take_picture(quality=0.8)
        return f"picture {'saved' if photo.path else 'empty'}, {photo.width} by {photo.height}"

    async def start() -> str:
        await camera.current.start_recording(audio=False)
        return "recording"

    async def stop() -> str:
        recording = await camera.current.stop_recording()
        return f"video {'saved' if recording.path else 'empty'}"

    async def system_screen() -> str:
        path = await Camera.take_photo(quality=0.8)
        return "system photo saved" if path else "system photo canceled"

    def on_error(failure: CameraError) -> None:
        set_ready(False)
        set_error(failure.code)

    def on_barcode(found: Barcode) -> None:
        set_barcode(f"{found.type} {found.data}")

    return DemoScreen(
        "Camera",
        "CameraView with a handle, barcode scanning, and the system camera screen.",
        DemoSection(
            "CameraView",
            CameraView(
                ref=camera,
                facing=facing,
                flash=flash,
                zoom=zoom,
                barcode_types=["qr", "ean13", "code128"],
                on_ready=lambda: set_ready(True),
                on_error=on_error,
                on_barcode=on_barcode,
                style=pn.style(height=220),
            ),
            ResultText("Camera ready", "yes" if ready else "no"),
            ResultText("Camera error", error),
            ResultText("Last barcode", barcode),
            ResultText("Last result", result),
            pn.Button("Take picture", on_press=guarded(picture)),
            pn.Button("Start recording", on_press=guarded(start)),
            pn.Button("Stop recording", on_press=guarded(stop)),
        ),
        DemoSection(
            "Props",
            ResultText("Facing", facing),
            pn.Button("Flip camera", on_press=lambda: set_facing("front" if facing == "back" else "back")),
            ResultText("Flash", flash),
            pn.Button("Toggle torch", on_press=lambda: set_flash("off" if flash == "torch" else "torch")),
            ResultText("Zoom", zoom),
            pn.Button("Toggle zoom", on_press=lambda: set_zoom(1.0 if zoom == 2.0 else 2.0)),
        ),
        DemoSection(
            "System screen",
            Hint("The iOS simulator has no camera, so this reports a cancel there."),
            pn.Button("Open system camera", on_press=guarded(system_screen)),
        ),
    )
