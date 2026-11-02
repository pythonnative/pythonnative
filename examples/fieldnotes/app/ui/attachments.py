"""An entry's attachments: the buttons that add them, and how each kind appears."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import pythonnative as pn
from pythonnative.audio import Recorder, Sound
from pythonnative.native_modules import NativeModuleError
from pythonnative.pickers import PickedFile, pick_images, pick_videos

from ..journal import FREE_ATTACHMENTS, AttachmentLimitReached, journal
from ..models import Attachment, Entry, format_duration
from .capture_screen import CaptureScreen
from .media_screen import MediaScreen
from .pro_screen import ProScreen
from .theme import Styles
from .widgets import ActionButton, Banner, PrimaryButton, slots

METERING_FLOOR = -60.0
"""Decibels treated as silence on the level meter. Below this, nobody's talking."""


def level_fraction(decibels: float) -> float:
    """Map an input level to the meter's 0 to 1 range.

    Args:
        decibels: The recorder's level, relative to full scale.

    Returns:
        The fraction of the meter to fill.
    """
    return min(1.0, max(0.0, (decibels - METERING_FLOOR) / -METERING_FLOOR))


async def attach_picked(entry_id: str, files: list[PickedFile], kind: str) -> str:
    """Attach what a picker returned.

    Args:
        entry_id: The entry.
        files: What the user chose. An empty list means they canceled.
        kind: ``"photo"`` or ``"video"``.

    Returns:
        A message about anything that didn't fit, or an empty string.
    """
    for picked in files:
        try:
            await journal.add_attachment(
                entry_id,
                "video" if kind == "video" else "photo",
                picked.path,
                mime_type=picked.mime_type,
                name=picked.name,
            )
        except AttachmentLimitReached as error:
            return f"{error} Pro removes the limit."
    return ""


@pn.component
def AddAttachments(entry: Entry) -> pn.Node:
    """The row of ways to add to an entry, and what happens when it's full."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    is_pro = pn.use_store(journal.store, lambda state: state.is_pro)
    notice, set_notice = pn.use_state("")
    recording, set_recording = pn.use_state(False)

    full = not is_pro and len(entry.attachments) >= FREE_ATTACHMENTS
    room = 0 if is_pro else max(0, FREE_ATTACHMENTS - len(entry.attachments))

    async def choose_photos() -> None:
        set_notice("")
        try:
            set_notice(await attach_picked(entry.id, await pick_images(limit=room, quality=0.8), "photo"))
        except (NativeModuleError, OSError) as error:
            set_notice(f"Couldn't add photos: {error}")

    async def choose_video() -> None:
        set_notice("")
        try:
            set_notice(await attach_picked(entry.id, await pick_videos(limit=1), "video"))
        except (NativeModuleError, OSError) as error:
            set_notice(f"Couldn't add the video: {error}")

    return pn.Column(
        *slots(
            buttons=pn.View(
                ActionButton(
                    "Camera", "camera", lambda: navigation.push(CaptureScreen(entry_id=entry.id)), disabled=full
                ),
                ActionButton("Photos", "images", choose_photos, disabled=full),
                ActionButton("Video", "film", choose_video, disabled=full),
                ActionButton("Voice", "mic", lambda: set_recording(True), disabled=full or recording),
                style=styles.wrap,
            ),
            recorder=VoiceRecorder(entry_id=entry.id, on_close=lambda: set_recording(False)) if recording else None,
            notice=Banner(notice, "warning") if notice else None,
            pro=(
                pn.View(
                    pn.Text(
                        f"{FREE_ATTACHMENTS} of {FREE_ATTACHMENTS} attachments used.",
                        style=[styles.caption, styles.grow],
                    ),
                    pn.Button("Get Pro", on_press=lambda: navigation.push(ProScreen())),
                    style=styles.spread,
                )
                if full
                else None
            ),
        ),
        style=pn.style(gap=8),
    )


@pn.component
def VoiceRecorder(entry_id: str, on_close: Callable[[], None]) -> pn.Node:
    """Record a voice note: start, pause and resume, then keep it or throw it away."""
    styles = pn.use_styles(Styles)
    recorder: pn.Ref[Optional[Recorder]] = pn.use_ref(None)
    phase, set_phase = pn.use_state("starting")
    level, set_level = pn.use_state(0.0)
    elapsed, set_elapsed = pn.use_state(0.0)
    problem, set_problem = pn.use_state("")

    async def start() -> None:
        # On a simulator this can take 20 seconds to report it can't reach an audio input.
        try:
            recorder.current = await Recorder.start(quality="high")
        except NativeModuleError as error:
            set_problem(_recording_problem(error))
            set_phase("failed")
            return
        set_phase("recording")

    def stop_on_unmount() -> Callable[[], None]:
        def stop() -> None:
            # Leaving the screen mid-note throws it away, and frees the microphone.
            active, recorder.current = recorder.current, None
            if active is not None:
                pn.run_async(active.stop())

        return stop

    pn.use_effect(start, [])
    pn.use_effect(stop_on_unmount, [])

    async def meter() -> None:
        while phase == "recording":
            active = recorder.current
            if active is None:
                return
            set_level(level_fraction(active.metering()))
            set_elapsed(lambda seconds: seconds + 0.2)
            await asyncio.sleep(0.2)

    pn.use_effect(meter, [phase])

    def toggle_pause() -> None:
        active = recorder.current
        if active is None:
            return
        if phase == "recording":
            active.pause()
            set_phase("paused")
        else:
            active.resume()
            set_phase("recording")

    async def keep() -> None:
        active, recorder.current = recorder.current, None
        if active is None:
            return
        set_phase("saving")
        try:
            result = await active.stop()
            await journal.add_attachment(
                entry_id, "voice", result.path, mime_type="audio/mp4", duration=result.duration
            )
        except (NativeModuleError, OSError, AttachmentLimitReached) as error:
            set_problem(f"Couldn't keep the recording: {error}")
            set_phase("failed")
            return
        on_close()

    labels = {
        "starting": "Starting the microphone...",
        "recording": f"Recording  {format_duration(elapsed)}",
        "paused": f"Paused  {format_duration(elapsed)}",
        "saving": "Saving...",
        "failed": problem,
    }
    live = phase in ("recording", "paused")
    return pn.Column(
        *slots(
            label=pn.Text(labels[phase], style=styles.error_text if phase == "failed" else styles.label),
            meter=pn.ProgressBar(value=level, color=styles.accent) if live else None,
            actions=pn.View(
                *slots(
                    pause=(
                        ActionButton("Resume" if phase == "paused" else "Pause", "pause", toggle_pause)
                        if live
                        else None
                    ),
                    # This stays mounted while saving: unmounting it would cancel keep().
                    keep=(
                        PrimaryButton("Keep note", keep, disabled=phase == "saving")
                        if live or phase == "saving"
                        else None
                    ),
                    close=ActionButton("Close" if phase == "failed" else "Discard", "x", on_close),
                ),
                style=styles.wrap,
            ),
        ),
        style=[styles.card, {"gap": 8}],
    )


def _recording_problem(error: NativeModuleError) -> str:
    return {
        "permission_denied": "Microphone access is off. You can turn it on in Settings.",
        "recording_failed": "The microphone didn't start. A simulator may not have an audio input.",
        "missing_usage_string": "This build doesn't declare the microphone permission.",
    }.get(error.code or "", f"The microphone didn't start: {error}")


@pn.component
def VoiceNotePlayer(attachment: Attachment) -> pn.Node:
    """Play one voice note inline, loading it the first time it's asked for."""
    styles = pn.use_styles(Styles)
    sound: pn.Ref[Optional[Sound]] = pn.use_ref(None)
    playing, set_playing = pn.use_state(False)
    position, set_position = pn.use_state(0.0)
    duration, set_duration = pn.use_state(attachment.duration)
    problem, set_problem = pn.use_state("")

    def unload_on_unmount() -> Callable[[], None]:
        def unload() -> None:
            loaded, sound.current = sound.current, None
            if loaded is not None:
                loaded.unload()

        return unload

    pn.use_effect(unload_on_unmount, [])

    async def follow() -> None:
        while playing and sound.current is not None:
            set_position(sound.current.position)
            await asyncio.sleep(0.25)

    pn.use_effect(follow, [playing])

    def finished() -> None:
        set_playing(False)
        set_position(0.0)

    async def toggle() -> None:
        set_problem("")
        if sound.current is None:
            try:
                loaded = await Sound.load(journal.file_path(attachment))
            except NativeModuleError as error:
                set_problem(f"Couldn't play this note: {error}")
                return
            loaded.on_end(finished)
            sound.current = loaded
            if loaded.duration:
                set_duration(loaded.duration)
        if playing:
            sound.current.pause()
            set_playing(False)
        else:
            sound.current.play()
            set_playing(True)

    return pn.View(
        pn.Pressable(
            pn.Icon("pause" if playing else "play", size=22, color=styles.colors.primary),
            on_press=toggle,
            accessibility_label=f"{'Pause' if playing else 'Play'} voice note",
            accessibility_role="button",
            style=styles.action,
        ),
        pn.Column(
            pn.Text(problem or "Voice note", style=styles.error_text if problem else styles.label),
            pn.ProgressBar(value=position / duration if duration else 0.0, color=styles.accent),
            pn.Text(f"{format_duration(position)} of {format_duration(duration)}", style=styles.caption),
            style=[styles.grow, {"gap": 4}],
        ),
        style=styles.row,
    )


@pn.component
def AttachmentTile(attachment: Attachment, entry_id: str) -> pn.Node:
    """A photo or video in an entry's grid. Pressing it opens it full size."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    progress = pn.use_store(journal.store, lambda state: state.transfers.get(attachment.id))

    def open_it() -> None:
        navigation.push(MediaScreen(entry_id=entry_id, attachment_id=attachment.id))

    if not attachment.is_local:
        content: pn.Node = pn.Column(
            pn.Icon("cloud", size=24, color=styles.colors.text_secondary),
            pn.Text("Downloading" if progress is not None else "On server", style=styles.caption),
            style=styles.tile,
        )
    elif attachment.kind == "photo":
        content = pn.Image(journal.file_path(attachment), scale_type="cover", style=styles.photo)
    else:
        content = pn.Column(
            pn.Icon("video", size=28, color=styles.colors.primary),
            pn.Text("Play video", style=styles.caption),
            style=styles.tile,
        )
    return pn.Column(
        pn.Pressable(
            content,
            on_press=open_it,
            accessibility_label=f"{attachment.kind.capitalize()} attachment",
            accessibility_role="button",
        ),
        (
            pn.ProgressBar(value=progress, color=styles.accent, style=pn.style(width=104))
            if progress is not None
            else None
        ),
        style=pn.style(gap=4),
    )
