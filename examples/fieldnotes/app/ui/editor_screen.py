"""Writing a new entry, or changing an existing one."""

from __future__ import annotations

from typing import Callable, Literal, Optional

import pythonnative as pn
from pythonnative.navigation import NavigationEvent
from pythonnative.runtime import run_application_task

from ..geo import locate, place_from
from ..journal import journal
from ..models import CONDITIONS, Entry, EntryDraft, Place, format_coordinate, parse_tags
from . import entry_screen
from .theme import Styles
from .widgets import ActionButton, Banner, Field, PrimaryButton, Section

LocationStatus = Literal["idle", "locating", "unavailable"]


async def locate_saved_entry(entry_id: str, name: str) -> None:
    """Finish a location lookup for an entry saved before its fix arrived.

    Someone in the field can write a line faster than a cold GPS can find them.
    This runs as an application task, so it outlives the editor that started it.

    Args:
        entry_id: The entry just saved.
        name: The place name that was typed, if any.
    """
    position = await locate()
    if position is None:
        return
    entry = journal.snapshot.find(entry_id)
    if entry is not None and entry.place is None:
        await journal.set_place(entry_id, place_from(position, name=name))


@pn.component
def EditorScreen(entry_id: Optional[str] = None) -> pn.Node:
    """Edit an entry's fields.

    Args:
        entry_id: The entry to change, or ``None`` to start a new one.
    """
    entry: Optional[Entry] = pn.use_store(journal.store, lambda state: state.find(entry_id) if entry_id else None)
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)

    title, set_title = pn.use_state(entry.title if entry else "")
    body, set_body = pn.use_state(entry.body if entry else "")
    tags, set_tags = pn.use_state(" ".join(entry.tags) if entry else "")
    conditions, set_conditions = pn.use_state(entry.conditions if entry else CONDITIONS[0])
    place, set_place = pn.use_state(entry.place if entry else None)
    place_name, set_place_name = pn.use_state(entry.place.name if entry and entry.place else "")
    location, set_location = pn.use_state("idle" if entry_id else "locating")
    locating_attempt, set_locating_attempt = pn.use_state(0 if entry_id else 1)
    base_version, set_base_version = pn.use_state(entry.updated_at if entry else 0.0)
    problem, set_problem = pn.use_state("")
    finished = pn.use_ref(False)

    async def find_location() -> None:
        if not locating_attempt:
            return
        set_location("locating")
        position = await locate()
        if position is None:
            set_location("unavailable")
            return
        set_place(place_from(position))
        set_location("idle")

    pn.use_effect(find_location, [locating_attempt])

    draft_place: Optional[Place] = None
    if place is not None:
        draft_place = Place(place.latitude, place.longitude, place.accuracy, place_name.strip())
    draft = EntryDraft(
        title=title.strip(),
        body=body.strip(),
        tags=parse_tags(tags),
        conditions=conditions,
        place=draft_place,
    )
    original = (
        EntryDraft(entry.title, entry.body, entry.tags, entry.conditions, entry.place)
        if entry is not None
        else EntryDraft(conditions=conditions, place=draft_place)
    )
    edited = draft != original

    def guard() -> Callable[[], None]:
        async def confirm_discard() -> None:
            discard = await pn.Alert.confirm(
                "Discard changes?",
                "What you've written here hasn't been saved.",
                confirm_label="Discard",
                cancel_label="Keep editing",
            )
            if discard:
                finished.current = True
                navigation.go_back()

        def before_remove(event: NavigationEvent) -> None:
            if edited and not finished.current:
                event.prevent_default()
                pn.run_async(confirm_discard())

        return navigation.add_listener("before_remove", before_remove)

    pn.use_effect(guard, [navigation, edited])

    async def save() -> None:
        set_problem("")
        if pn.Platform.OS == "android":
            # UIKit does this as the screen goes. Android leaves the keyboard over the next one.
            pn.Keyboard.dismiss()
        try:
            if entry_id is None:
                saved = await journal.create_entry(draft)
                if draft.place is None and location == "locating":
                    run_application_task(locate_saved_entry(saved.id, place_name.strip()))
            else:
                await journal.update_entry(entry_id, draft)
        except Exception as error:
            set_problem(f"Couldn't save: {error}")
            return
        finished.current = True
        if entry_id is None:
            navigation.replace(entry_screen.EntryScreen(id=saved.id))
        else:
            navigation.go_back()

    # In the header too, since the keyboard covers the one at the bottom while writing.
    pn.use_screen_options(
        title="Edit entry" if entry_id else "New entry",
        header_right=pn.Button("Save", on_press=save, disabled=draft.is_empty),
    )

    def use_latest() -> None:
        if entry is None:
            return
        set_title(entry.title)
        set_body(entry.body)
        set_tags(" ".join(entry.tags))
        set_conditions(entry.conditions)
        set_place(entry.place)
        set_place_name(entry.place.name if entry.place else "")
        set_base_version(entry.updated_at)

    # Someone else's edit reached this entry while it's open. Saving would overwrite
    # theirs, since the newest write wins, so say so while there's still a choice.
    conflicting = entry is not None and entry.updated_at != base_version

    if location == "locating":
        location_line = "Finding where you are..."
    elif place is not None:
        location_line = format_coordinate(place.latitude, place.longitude)
    elif location == "unavailable":
        location_line = "No location. Check that location access is on, or add one later."
    else:
        location_line = "No location"

    return pn.KeyboardAvoidingView(
        pn.ScrollView(
            pn.Column(
                (
                    Banner(
                        "This entry changed on another device.",
                        "warning",
                        action=pn.Button("Use latest", on_press=use_latest),
                    )
                    if conflicting
                    else None
                ),
                Banner(problem, "error") if problem else None,
                Field("Title", title, set_title, placeholder="Heron at the old mill"),
                Field("Notes", body, set_body, placeholder="What did you notice?", multiline=True),
                Field("Tags", tags, set_tags, placeholder="birds river", auto_capitalize="none"),
                pn.Column(
                    pn.Text("Conditions", style=styles.caption),
                    pn.SegmentedControl(
                        segments=list(CONDITIONS),
                        selected_index=CONDITIONS.index(conditions) if conditions in CONDITIONS else 0,
                        on_change=lambda index: set_conditions(CONDITIONS[index]),
                        tint_color=styles.colors.primary,
                        accessibility_label="Conditions",
                    ),
                    style=pn.style(gap=4),
                ),
                Section(
                    "Where",
                    pn.Text(location_line, style=styles.body),
                    Field("Place name", place_name, set_place_name, placeholder="North ridge") if place else None,
                    pn.View(
                        ActionButton(
                            "Locate me",
                            "locate",
                            lambda: set_locating_attempt(locating_attempt + 1),
                            disabled=location == "locating",
                        ),
                        ActionButton("Remove", "x", lambda: set_place(None)) if place else None,
                        style=pn.style(flex_direction="row", gap=8),
                    ),
                ),
                PrimaryButton("Save entry", save, disabled=draft.is_empty),
                style=styles.content,
            ),
            style=styles.screen,
        ),
        style=styles.screen,
    )
