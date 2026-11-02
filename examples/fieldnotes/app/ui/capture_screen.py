"""An in-app camera, for when a field note can't wait for the system's camera screen.

Photos and short clips land on the entry the screen was opened from. A level on the
preview shows how far the phone is from straight, which is hard to judge outdoors
at arm's length. On a device with no camera, the screen says so and offers the
system's camera screen and the photo library instead.
"""

from __future__ import annotations

from typing import Optional

import pythonnative as pn
from pythonnative.camera import Camera, CameraError, CameraView
from pythonnative.native_modules import NativeModuleError
from pythonnative.sensors import Accelerometer

from ..geo import tilt_degrees
from ..journal import AttachmentLimitReached, journal
from ..models import AttachmentKind
from .theme import Styles
from .widgets import ActionButton, Banner, PrimaryButton, slots

MODES = ["Photo", "Clip"]
CAMERA_PROBLEMS = {
    "unavailable": "This device has no camera here. Try the system camera, or add from your library.",
    "permission_denied": "Camera access is off. You can turn it on in Settings.",
}


def use_tilt() -> Optional[float]:
    """Follow how far the device is rolled from level, when it has an accelerometer.

    Returns:
        Degrees, or ``None`` when there's no sensor or the phone is lying flat.
    """
    level: Optional[float] = None
    tilt, set_tilt = pn.use_state(level)

    async def watch() -> None:
        if not Accelerometer.is_available():
            return
        async for reading in Accelerometer.readings(hz=10):
            degrees = tilt_degrees(reading.x, reading.y)
            set_tilt(None if degrees is None else round(degrees))

    pn.use_effect(watch, [])
    return tilt


@pn.component
def LevelBadge(tilt: float) -> pn.Node:
    """A small readout over the preview. It turns green when the horizon is straight."""
    styles = pn.use_styles(Styles)
    level = abs(tilt) <= 1
    return pn.View(
        pn.Text("Level" if level else f"{tilt:+.0f}°", style=pn.style(color="#FFFFFF", font_size=14)),
        style=pn.style(
            align_self="center",
            margin_top=12,
            padding_horizontal=12,
            padding_vertical=4,
            border_radius=999,
            background_color=styles.colors.success if level else "#00000099",
        ),
    )


@pn.component
def CaptureScreen(entry_id: str) -> pn.Node:
    """Take photos and clips for one entry.

    Args:
        entry_id: The entry they attach to.
    """
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    camera = pn.use_ref()
    tilt = use_tilt()
    mode, set_mode = pn.use_state(0)
    problem, set_problem = pn.use_state("")
    unavailable, set_unavailable = pn.use_state(False)
    recording, set_recording = pn.use_state(False)
    saved, set_saved = pn.use_state(0)

    pn.use_screen_options(title="Capture")

    async def attach(kind: AttachmentKind, path: str, mime_type: str, duration: float = 0.0) -> None:
        try:
            await journal.add_attachment(entry_id, kind, path, mime_type=mime_type, duration=duration)
        except AttachmentLimitReached as error:
            set_problem(f"{error} Pro removes the limit.")
            return
        set_saved(lambda count: count + 1)

    async def take_picture() -> None:
        set_problem("")
        try:
            photo = await camera.current.take_picture(quality=0.8)
        except NativeModuleError as error:
            set_problem(f"The picture didn't save: {error.message}")
            return
        await attach("photo", photo.path, "image/jpeg")

    async def toggle_clip() -> None:
        set_problem("")
        try:
            if recording:
                set_recording(False)
                clip = await camera.current.stop_recording()
                mime_type = "video/quicktime" if clip.path.endswith(".mov") else "video/mp4"
                await attach("video", clip.path, mime_type, clip.duration)
            else:
                await camera.current.start_recording()
                set_recording(True)
        except NativeModuleError as error:
            set_recording(False)
            set_problem(f"The clip didn't record: {error.message}")

    async def system_camera() -> None:
        set_problem("")
        try:
            path = await Camera.take_photo(quality=0.8)
        except NativeModuleError as error:
            set_problem(f"The camera didn't open: {error.message}")
            return
        if path is None:
            set_problem("No photo was taken. This device may not have a camera.")
            return
        await attach("photo", path, "image/jpeg")

    def camera_failed(error: CameraError) -> None:
        set_unavailable(error.code != "capture_failed")
        set_problem(
            CAMERA_PROBLEMS.get(error.code, "The camera stopped working. Try leaving this screen and coming back.")
        )

    shutter = "Take photo" if mode == 0 else "Stop clip" if recording else "Start clip"
    return pn.Column(
        CameraView(
            LevelBadge(tilt) if tilt is not None and not unavailable else None,
            ref=camera,
            on_error=camera_failed,
            accessibility_label="Camera preview",
            style=pn.style(flex=1),
        ),
        pn.Column(
            *slots(
                problem=Banner(problem, "warning") if problem else None,
                mode=pn.SegmentedControl(
                    segments=MODES,
                    selected_index=mode,
                    on_change=set_mode,
                    disabled=recording,
                    accessibility_label="Capture mode",
                ),
                saved=pn.Text(
                    f"{saved} added to this entry" if saved else "Saved straight to this entry.",
                    style=styles.caption,
                ),
                shutter=PrimaryButton(shutter, take_picture if mode == 0 else toggle_clip, disabled=unavailable),
                actions=pn.View(
                    *slots(
                        system=ActionButton("System camera", "camera", system_camera) if unavailable else None,
                        done=ActionButton("Done", "x", navigation.go_back),
                    ),
                    style=styles.wrap,
                ),
            ),
            style=styles.content,
        ),
        style=styles.screen,
    )
