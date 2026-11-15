"""One attachment, full size: a photo to look at, or a video to play."""

from __future__ import annotations

from typing import Optional

import pythonnative as pn
from pythonnative.video import Video, VideoInfo

from ..journal import journal
from ..models import Attachment, format_duration, format_size
from .theme import Styles
from .widgets import ActionButton, Banner, EmptyState


@pn.component
def VideoPlayer(attachment: Attachment) -> pn.Node:
    """The native player, with a line under it saying how far along it is."""
    styles = pn.use_styles(Styles)
    player = pn.use_ref()
    initial_info: Optional[VideoInfo] = None
    info, set_info = pn.use_state(initial_info)
    position, set_position = pn.use_state(0.0)
    ended, set_ended = pn.use_state(False)
    problem, set_problem = pn.use_state("")

    def ready(details: VideoInfo) -> None:
        set_info(details)

    def progress(seconds: float, duration: float) -> None:
        set_position(seconds)
        set_ended(False)

    def restart() -> None:
        if player.current is not None:
            player.current.seek(0)
            player.current.play()

    if ended and info:
        line = f"Played to the end. {format_duration(info.duration)} long."
    elif info:
        line = f"{format_duration(position)} of {format_duration(info.duration)}"
    else:
        line = "Loading the video..."
    return pn.Column(
        Video(
            source=journal.file_path(attachment),
            controls=True,
            ref=player,
            on_ready=ready,
            on_progress=progress,
            on_end=lambda: set_ended(True),
            on_error=set_problem,
            style=pn.style(aspect_ratio=16 / 9, background_color="#000000"),
        ),
        Banner(f"This video can't play: {problem}", "error") if problem else None,
        pn.Text(line, style=styles.caption),
        ActionButton("Play from the start", "rotate-ccw", restart, disabled=info is None),
        style=pn.style(gap=8),
    )


@pn.component
def MediaScreen(entry_id: str, attachment_id: str) -> pn.Node:
    """Show one attachment and offer to remove it.

    Args:
        entry_id: The entry it's on.
        attachment_id: The attachment.
    """
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)

    attachment = pn.use_store(
        journal.store,
        lambda state: entry.attachment(attachment_id) if (entry := state.find(entry_id)) is not None else None,
    )
    pn.use_screen_options(title="Video" if attachment and attachment.kind == "video" else "Photo")

    if attachment is None:
        return pn.Column(
            EmptyState("image", "It's gone", "This attachment was removed, maybe on another device."),
            style=styles.screen,
        )

    async def remove(item: Attachment) -> None:
        if await pn.Alert.confirm(
            "Remove this attachment?",
            "The file is deleted from this device and from your other devices.",
            confirm_label="Remove",
            cancel_label="Keep",
        ):
            await journal.remove_attachment(item)
            navigation.go_back()

    if not attachment.is_local:
        content: pn.Node = EmptyState("cloud", "Not here yet", "This file is still on its way from your sync server.")
    elif attachment.kind == "video":
        content = VideoPlayer(attachment)
    else:
        content = pn.Image(
            journal.file_path(attachment),
            scale_type="contain",
            accessibility_label=attachment.name,
            style=pn.style(height=420, border_radius=8),
        )

    return pn.ScrollView(
        pn.Column(
            content,
            pn.Text(f"{attachment.name}  ·  {format_size(attachment.size)}", style=styles.caption),
            pn.Text(
                "Backed up on your sync server." if attachment.remote_path else "Only on this device so far.",
                style=styles.caption,
            ),
            ActionButton("Remove", "trash", lambda: remove(attachment)),
            style=styles.content,
        ),
        style=styles.screen,
    )
