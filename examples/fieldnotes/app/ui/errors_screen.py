"""The on-disk error log, for when someone asks what went wrong."""

from __future__ import annotations

import pythonnative as pn

from ..errorlog import ErrorRecord
from ..journal import journal
from ..models import format_moment
from .theme import Styles
from .widgets import ActionButton, EmptyState


def record_key(record: ErrorRecord, index: int) -> str:
    return f"{record.at}-{index}"


def render_record(record: ErrorRecord, index: int) -> pn.Element:
    return ErrorRow(record)


@pn.component
def ErrorRow(record: ErrorRecord) -> pn.Node:
    """One error: what it was and when. Pressing it shows the traceback."""
    styles = pn.use_styles(Styles)
    expanded, set_expanded = pn.use_state(False)
    return pn.Pressable(
        pn.Text(f"{record.kind}: {record.message}", style=[styles.label, {"max_lines": 3}]),
        pn.Text(f"{format_moment(record.at)}  ·  {record.phase}", style=styles.caption),
        pn.Text(record.trace, style=[styles.caption, {"font_size": 11}], selectable=True) if expanded else None,
        on_press=lambda: set_expanded(not expanded),
        accessibility_label=f"{record.kind}: {record.message}",
        accessibility_role="button",
        style=styles.entry_row_column,
    )


@pn.component
def ErrorLogScreen() -> pn.Node:
    """List what's in the log, newest first."""
    styles = pn.use_styles(Styles)
    count = pn.use_store(journal.store, lambda state: state.logged_errors)
    records = pn.use_memo(journal.errors.read, [count])

    pn.use_screen_options(title="Error log")

    return pn.Column(
        pn.View(
            ActionButton("Clear", "trash", journal.errors.clear, disabled=not records),
            style=[styles.wrap, {"padding": 16}],
        ),
        pn.FlatList(
            data=records,
            key_extractor=record_key,
            render_item=render_record,
            estimated_item_height=80,
            list_empty=EmptyState("circle-check", "No errors", "Nothing has gone wrong on this device."),
            style=styles.grow,
        ),
        style=styles.screen,
    )
