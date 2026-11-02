"""One entry, with everything attached to it."""

from __future__ import annotations

from datetime import datetime
from functools import partial
from typing import Optional

import pythonnative as pn
from pythonnative.native_modules import NativeModuleError
from pythonnative.runtime import run_application_task

from ..geo import locate, place_from
from ..journal import journal
from ..models import Entry, format_coordinate, format_day, format_moment, format_time
from ..reminders import PRESETS, Preset, cancel_reminder, entry_url, schedule_reminder
from . import editor_screen
from .attachments import AddAttachments, AttachmentTile, VoiceNotePlayer
from .theme import Styles
from .widgets import ActionButton, Banner, Chip, EmptyState, Section, slots


async def delete_with_reminder(entry: Entry) -> None:
    """Delete an entry, and the reminder that would otherwise point at nothing."""
    if entry.remind_at is not None:
        await cancel_reminder(journal, entry.id)
    await journal.delete_entry(entry.id)


@pn.component
def ReminderSection(entry: Entry) -> pn.Node:
    """Come back to this entry later: a notification whose tap reopens it."""
    styles = pn.use_styles(Styles)
    notice, set_notice = pn.use_state("")

    async def remind(preset: Preset) -> None:
        set_notice("")
        try:
            allowed = await schedule_reminder(journal, entry, preset.delay(datetime.now()))
        except NativeModuleError as error:
            set_notice(f"Couldn't set a reminder: {error.message}")
            return
        if not allowed:
            set_notice("Notifications are off for Field Notes. You can turn them on in Settings.")

    async def cancel() -> None:
        await cancel_reminder(journal, entry.id)

    if entry.remind_at is not None:
        current: pn.Node = pn.View(
            pn.Text(f"Reminder set for {format_moment(entry.remind_at)}", style=[styles.body, styles.grow]),
            ActionButton("Cancel reminder", "bell-off", cancel),
            style=styles.wrap,
        )
    else:
        current = pn.View(
            *(Chip(preset.label, on_press=partial(remind, preset)).with_key(preset.label) for preset in PRESETS),
            style=styles.wrap,
        )
    return Section("Remind me", current, Banner(notice, "warning") if notice else None)


@pn.component
def PlaceSection(entry: Entry) -> pn.Node:
    """Where this was written, and a way to add that if the first fix never came."""
    styles = pn.use_styles(Styles)
    navigation = pn.use_navigation()
    locating, set_locating = pn.use_state(False)
    failed, set_failed = pn.use_state(False)

    async def add_location() -> None:
        set_locating(True)
        set_failed(False)
        position = await locate()
        set_locating(False)
        if position is None:
            set_failed(True)
            return
        await journal.set_place(entry.id, place_from(position))

    def show_on_map() -> None:
        from .map_screen import MapScreen

        navigation.navigate(MapScreen(focus=entry.id))

    place = entry.place
    if place is None:
        return Section(
            "Where",
            pn.Text(
                "Couldn't get a location." if failed else "This entry has no location.",
                style=styles.body,
            ),
            ActionButton(
                "Finding you..." if locating else "Add my location", "locate", add_location, disabled=locating
            ),
        )
    return Section(
        "Where",
        pn.Text(place.name, style=styles.body) if place.name else None,
        pn.Text(format_coordinate(place.latitude, place.longitude), style=styles.caption),
        ActionButton("Show on map", "map-pin", show_on_map),
    )


@pn.component
def EntryContent(entry: Entry) -> pn.Node:
    """The entry itself, split out so the screen can handle a missing entry first."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    transfer_error = pn.use_store(journal.store, lambda state: state.transfer_error)

    pn.use_screen_options(
        title=format_day(entry.created_at),
        header_right=pn.Button("Edit", on_press=lambda: navigation.push(editor_screen.EditorScreen(entry_id=entry.id))),
    )

    async def share() -> None:
        await pn.Share.share(
            title=entry.display_title,
            message=f"{entry.display_title}\n\n{entry.body}".strip(),
        )

    async def delete() -> None:
        if await pn.Alert.confirm(
            "Delete this entry?",
            "It's removed from this device and from your other devices, with its attachments.",
            confirm_label="Delete",
            cancel_label="Keep",
        ):
            # This screen is about to go away, and its tasks with it. The deletion shouldn't.
            run_application_task(delete_with_reminder(entry))
            navigation.go_back()

    visuals = [item for item in entry.attachments if item.kind in ("photo", "video")]
    voices = entry.of_kind("voice")
    edited = entry.updated_at > entry.created_at + 1
    return pn.ScrollView(
        pn.Column(
            *slots(
                title=pn.Text(entry.display_title, style=styles.title, accessibility_role="header"),
                meta=pn.Text(
                    f"{format_time(entry.created_at)}  ·  {entry.conditions}" + ("  ·  Edited" if edited else ""),
                    style=styles.caption,
                ),
                tags=(
                    pn.View(*(Chip(f"#{tag}").with_key(tag) for tag in entry.tags), style=styles.wrap)
                    if entry.tags
                    else None
                ),
                body=pn.Text(entry.body, style=styles.body, selectable=True) if entry.body else None,
                attachments=Section(
                    "Attachments",
                    *slots(
                        visuals=(
                            pn.View(
                                *(
                                    AttachmentTile(attachment=item, entry_id=entry.id).with_key(item.id)
                                    for item in visuals
                                ),
                                style=styles.wrap,
                            )
                            if visuals
                            else None
                        ),
                        voices=(
                            pn.Column(
                                *(
                                    VoiceNotePlayer(attachment=item).with_key(item.id)
                                    for item in voices
                                    if item.is_local
                                ),
                                style=pn.style(gap=8),
                            )
                            if voices
                            else None
                        ),
                        transfer=Banner(transfer_error, "warning") if transfer_error else None,
                        add=AddAttachments(entry=entry),
                    ),
                ),
                place=PlaceSection(entry=entry),
                reminder=ReminderSection(entry=entry),
                actions=pn.View(
                    ActionButton("Share", "share-2", share),
                    ActionButton("Delete", "trash", delete),
                    style=styles.wrap,
                ),
                link=pn.Text(entry_url(entry.id), style=styles.caption, selectable=True),
            ),
            style=styles.content,
        ),
        style=styles.screen,
    )


@pn.component
def EntryScreen(id: str) -> pn.Node:
    """Show one entry.

    A deep link can name an entry that was deleted, or that never existed, so this
    screen has to make sense with nothing to show.

    Args:
        id: The entry's ID, which is also the last part of its deep link.
    """
    entry: Optional[Entry] = pn.use_store(journal.store, lambda state: state.find(id))
    loading = pn.use_store(journal.store, lambda state: state.loading)
    styles = pn.use_styles(Styles)
    if entry is None:
        return pn.Column(
            (
                pn.ActivityIndicator()
                if loading
                else EmptyState("book-open", "Entry not found", "It may have been deleted on another device.")
            ),
            style=[styles.screen, {"justify_content": "center"}],
        )
    return EntryContent(entry=entry)
