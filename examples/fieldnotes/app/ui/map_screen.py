"""The second tab: a marker for every entry that knows where it was written."""

from __future__ import annotations

from functools import partial
from typing import Optional

import pythonnative as pn
from pythonnative.maps import Coordinate, MapView, Marker, Region

from ..geo import fit_region
from ..journal import journal
from ..models import Entry, format_day
from .entry_screen import EntryScreen
from .theme import Styles
from .widgets import ActionButton, Banner, EmptyState, ScreenHeader


def markers_for(entries: tuple[Entry, ...], color: str) -> list[Marker]:
    """Return one marker per located entry, identified by the entry's ID."""
    return [
        Marker(
            entry.id,
            Coordinate(entry.place.latitude, entry.place.longitude),
            title=entry.display_title,
            description=format_day(entry.created_at),
            color=color,
        )
        for entry in entries
        if entry.place is not None
    ]


@pn.component
def PlaceList(entries: tuple[Entry, ...]) -> pn.Node:
    """The same places as a list, which is all an Android build with no Maps key can show."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)

    def open_entry(entry_id: str) -> None:
        navigation.push(EntryScreen(id=entry_id))

    return pn.Column(
        *(
            pn.Pressable(
                pn.Text(entry.display_title, style=styles.label),
                pn.Text(entry.place.label if entry.place else "", style=styles.caption),
                on_press=partial(open_entry, entry.id),
                accessibility_label=f"Open {entry.display_title}",
                accessibility_role="button",
                style=styles.card,
                key=entry.id,
            )
            for entry in entries
        ),
        style=pn.style(gap=8, padding=16),
    )


@pn.component
def MapScreen(focus: Optional[str] = None) -> pn.Node:
    """Show the journal on a map.

    Args:
        focus: An entry to center on, when this screen was opened from one.
    """
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    entries = pn.use_store(journal.store, lambda state: state.entries)
    map_ref = pn.use_ref()
    problem, set_problem = pn.use_state("")

    located = tuple(entry for entry in entries if entry.place is not None)
    places = [entry.place for entry in located if entry.place is not None]
    # The map keeps its own camera after the first frame, so this only sets where it
    # starts. A ref holds the first frame's places, and the latest ones for fit_all.
    first_places = pn.use_ref(places)
    start = pn.use_memo(lambda: fit_region(first_places.current), [])
    located_now = pn.use_ref(located)
    located_now.current = located

    def fit_all() -> None:
        if map_ref.current is not None:
            map_ref.current.animate_to(fit_region(places))

    def center_on_focus() -> None:
        target = next((entry for entry in located_now.current if entry.id == focus), None)
        if target is not None and target.place is not None and map_ref.current is not None:
            center = Coordinate(target.place.latitude, target.place.longitude)
            map_ref.current.animate_to(Region(center, latitude_delta=0.05, longitude_delta=0.05))

    pn.use_effect(center_on_focus, [focus])

    count = len(entries)
    summary = f"{len(located)} of {count} entries have a location." if count else "Entries you write will appear here."
    return pn.SafeAreaView(
        ScreenHeader("Map", ActionButton("Fit all", "locate", fit_all, disabled=not located)),
        pn.Column(pn.Text(summary, style=styles.caption), style=pn.style(padding_horizontal=16, padding_bottom=8)),
        (
            pn.View(Banner(problem, "warning"), style=pn.style(padding_horizontal=16, padding_bottom=8))
            if problem
            else None
        ),
        # With no map to show, the same places are still worth listing.
        (
            pn.ScrollView(
                (
                    PlaceList(entries=located)
                    if located
                    else EmptyState("map-pin", "No places yet", "Entries record where they were written.")
                ),
                style=styles.grow,
            )
            if problem
            else None
        ),
        (
            MapView(
                ref=map_ref,
                initial_region=start,
                markers=markers_for(located, styles.accent),
                on_marker_press=lambda entry_id: navigation.push(EntryScreen(id=entry_id)),
                on_error=set_problem,
                accessibility_label="Map of your journal entries",
                style=styles.grow,
            )
            if not problem
            else None
        ),
        edges=("top",),
        style=styles.screen,
    )
