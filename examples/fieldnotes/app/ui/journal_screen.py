"""The first tab: every entry, newest first, with search."""

from __future__ import annotations

from functools import partial

import pythonnative as pn

from ..journal import journal
from ..models import Entry, SyncStatus, format_day
from .editor_screen import EditorScreen
from .entry_screen import EntryScreen
from .theme import Styles
from .widgets import ActionButton, Chip, EmptyState, ScreenHeader


def entry_key(entry: Entry, index: int) -> str:
    return entry.id


def render_entry(entry: Entry, index: int) -> pn.Element:
    return EntryRow(entry)


# FlatList rebuilds its rows when these callables change, so they live at module
# level rather than being recreated on every render.


def sync_summary(server_url: str, status: SyncStatus) -> str:
    """Say in a few words whether this journal is reaching anyone.

    Args:
        server_url: The configured server, or empty for none.
        status: What the connection is doing.

    Returns:
        A short line for the journal's header.
    """
    if not server_url:
        return "Offline. Your journal stays on this device."
    if status.phase == "connected":
        return "Live. Edits sync as you make them."
    if status.phase == "waiting":
        return f"Offline. Reconnecting in {status.retry_in:.0f} seconds."
    return "Connecting to your sync server..."


@pn.component
def EntryRow(entry: Entry) -> pn.Node:
    """One entry in the list: its first photo, title, excerpt, and where and when."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    photos = [photo for photo in entry.of_kind("photo") if photo.is_local]
    details = [format_day(entry.created_at)]
    if entry.place is not None:
        details.append(entry.place.label)
    if entry.attachments:
        count = len(entry.attachments)
        details.append(f"{count} attachment" + ("" if count == 1 else "s"))
    return pn.Pressable(
        pn.Image(journal.file_path(photos[0]), scale_type="cover", style=styles.thumbnail) if photos else None,
        pn.Column(
            pn.Text(entry.display_title, style=[styles.label, {"max_lines": 1}]),
            pn.Text(entry.excerpt, style=[styles.caption, {"max_lines": 2}]) if entry.excerpt else None,
            pn.Text("  ·  ".join(details), style=[styles.caption, {"max_lines": 1}]),
            style=[styles.grow, {"gap": 4}],
        ),
        on_press=lambda: navigation.push(EntryScreen(id=entry.id)),
        accessibility_label=entry.display_title,
        accessibility_role="button",
        style=styles.entry_row,
    )


@pn.component
def JournalScreen() -> pn.Node:
    """Search and browse the journal."""
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    entries = pn.use_store(journal.store, lambda state: state.entries)
    loading = pn.use_store(journal.store, lambda state: state.loading)
    tags = pn.use_store(journal.store, lambda state: state.tags)
    server_url = pn.use_store(journal.store, lambda state: state.settings.server_url)
    sync = pn.use_store(journal.store, lambda state: state.sync)
    search, set_search = pn.use_state("")
    deferred = pn.use_deferred_value(search)

    # A newer keystroke cancels this query, and new entries re-run it. An empty
    # search doesn't wait for it, so the list never flashes empty.
    results: pn.QueryResult[tuple[Entry, ...]] = pn.use_query(
        lambda: journal.search(deferred), [deferred, entries], initial=()
    )
    searching = bool(deferred.strip())
    shown = (results.data or ()) if searching else entries

    def toggle_tag(tag: str) -> None:
        token = f"#{tag}"
        words = search.split()
        set_search(" ".join(word for word in words if word != token) if token in words else f"{search} {token}".strip())

    def new_entry() -> None:
        navigation.push(EditorScreen())

    if searching:
        empty = EmptyState("search", "No matches", "Try fewer words, or a tag like #birds.")
    elif loading:
        empty = pn.ActivityIndicator()
    else:
        empty = EmptyState(
            "notebook-pen",
            "An empty notebook",
            "Write down what you saw, where you saw it, and what it sounded like.",
        )

    return pn.SafeAreaView(
        ScreenHeader("Journal", ActionButton("New entry", "plus", new_entry)),
        pn.Column(
            pn.TextInput(
                value=search,
                on_change=set_search,
                placeholder="Search notes, places, and #tags",
                placeholder_color=styles.colors.text_secondary,
                accessibility_label="Search the journal",
                return_key_type="search",
                auto_capitalize="none",
                clear_button=True,
                style=styles.field,
            ),
            (
                pn.ScrollView(
                    pn.Row(
                        *(
                            Chip(
                                f"#{tag}", on_press=partial(toggle_tag, tag), active=f"#{tag}" in search.split()
                            ).with_key(tag)
                            for tag in tags[:12]
                        ),
                        style=pn.style(gap=8),
                    ),
                    horizontal=True,
                    shows_scroll_indicator=False,
                )
                if tags
                else None
            ),
            pn.Text(sync_summary(server_url, sync), style=styles.caption),
            style=pn.style(gap=8, padding_horizontal=16, padding_bottom=8),
        ),
        pn.FlatList(
            data=shown,
            key_extractor=entry_key,
            render_item=render_entry,
            estimated_item_height=96,
            list_empty=empty,
            style=styles.grow,
        ),
        edges=("top",),
        style=styles.screen,
    )
