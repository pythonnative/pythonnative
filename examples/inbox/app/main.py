"""A complete offline inbox built from Python function components."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace

from inbox_extension import InboxBadge, InboxBatch, InboxRecord, InboxTools

import pythonnative as pn

from .repository import Issue, Repository

repository = Repository()
"""The one repository every screen shares; it outlives screen pushes and recycled rows."""


class Styles:
    """Theme-derived styles, built once per theme by ``pn.use_styles``."""

    def __init__(self, theme: pn.Theme) -> None:
        colors, space = theme.colors, theme.spacing
        self.screen = pn.style(flex=1, background_color=colors.background)
        self.field = pn.style(
            padding=12,
            border_radius=theme.radii.md,
            background_color=colors.surface,
            color=colors.text,
            font_size=16,
        )
        self.search = pn.style(margin=space.md, margin_bottom=0)
        self.toolbar = pn.style(gap=12, padding=12, align_items="center")
        self.status: pn.Style = {**theme.typography.caption, "color": colors.text_secondary, "padding": 12}
        self.label: pn.Style = {**theme.typography.body, "color": colors.text}
        self.row = pn.style(
            padding=space.md,
            gap=6,
            background_color=colors.surface,
            border_bottom_width=1,
            border_color=colors.border,
        )
        self.row_title: pn.Style = {"bold": True, "font_size": 17, "color": colors.text}
        self.row_body: pn.Style = {"font_size": 14, "color": colors.text_secondary}
        self.row_state: pn.Style = {"color": colors.primary}
        self.detail = pn.style(padding=20, gap=space.md)
        self.heading: pn.Style = {**theme.typography.title, "color": colors.text}
        self.error: pn.Style = {**theme.typography.body, "color": colors.error}


def has_native_extension() -> bool:
    """Whether the extension's badge and service exist here; they're implemented on iOS and Android only."""
    return pn.Platform.OS in {"ios", "android"}


@pn.component
def IssueRow(issue: Issue) -> pn.Node:
    navigation = pn.use_navigation()
    styles = pn.use_styles(Styles)
    return pn.Pressable(
        pn.Column(
            pn.Text(issue.title, style=styles.row_title),
            pn.Text(issue.body, style=styles.row_body),
            pn.Text("Closed" if issue.closed else "Open", style=styles.row_state),
            style=styles.row,
        ),
        on_press=lambda: navigation.push(IssueScreen(issue_id=issue.id)),
        accessibility_label=issue.title,
    )


# FlatList rebuilds its rows when these callables change, so they live at
# module level rather than being recreated on every render.
def issue_key(issue: Issue, index: int) -> str:
    return issue.id


def render_issue(issue: Issue, index: int) -> pn.Element:
    return IssueRow(issue)


def use_extension_status(issues: tuple[Issue, ...]) -> tuple[str, Callable[[str], None]]:
    """Hand the issues to the native extension and return its latest message."""
    status, set_status = pn.use_state("")

    def listen() -> Callable[[], None] | None:
        if not has_native_extension():
            return None

        def prepared(batch: InboxBatch) -> None:
            set_status(batch.message)

        return InboxTools.on_prepared(prepared)

    pn.use_effect(listen, [])

    async def prepare() -> None:
        if not has_native_extension():
            return
        # New issues or leaving the screen cancel this effect, which cancels the
        # native work through the generated adapter's cancellation callback.
        records = [InboxRecord(issue.id, issue.title, ("closed" if issue.closed else "open",)) for issue in issues]
        batch = await InboxTools.prepare(records=records)
        assert all(isinstance(record, InboxRecord) for record in batch.records), "records decode to dataclasses"
        set_status(batch.message)

    pn.use_effect(prepare, [issues])
    return status, set_status


async def check_cancellation() -> str:
    """Start native work, cancel it, and report whether its result was suppressed."""
    delivered: list[InboxBatch] = []
    unsubscribe = InboxTools.on_prepared(delivered.append)
    work = asyncio.create_task(InboxTools.prepare(records=[InboxRecord("cancel-check", "Cancelled")], delay_ms=100))
    try:
        await asyncio.sleep(0)
        work.cancel()
        try:
            await work
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.2)
    finally:
        work.cancel()
        unsubscribe()
    leaked = any(record.identifier == "cancel-check" for batch in delivered for record in batch.records)
    return "Cancellation failed" if leaked else "Preparation cancelled"


@pn.component
def InboxScreen() -> pn.Node:
    snapshot = pn.use_store(repository.store)
    styles = pn.use_styles(Styles)
    search, set_search = pn.use_state("")
    deferred = pn.use_deferred_value(search)
    only_open, set_only_open = pn.use_state(False)
    issues = snapshot.issues
    status, set_status = use_extension_status(issues)

    async def filter_issues() -> list[Issue]:
        text = deferred.casefold()
        selected: list[Issue] = []
        for start in range(0, len(issues), 100):
            selected.extend(issue for issue in issues[start : start + 100] if issue.matches(text, only_open=only_open))
            # Yield between chunks so a newer keystroke can cancel this pass.
            await asyncio.sleep(0)
        return selected

    filtered: pn.QueryResult[list[Issue]] = pn.use_query(filter_issues, [issues, deferred, only_open], initial=[])
    matches = filtered.data or []
    show_all = not deferred and not only_open

    async def on_badge_press(count: int) -> None:
        # The badge echoes its count back through a typed native event.
        if count != len(issues):
            set_status(f"Badge reported {count} of {len(issues)} issues")
            return
        set_status(await check_cancellation())

    return pn.Column(
        pn.TextInput(
            value=search,
            on_change=set_search,
            placeholder="Search 2,000 issues",
            accessibility_label="Search issues",
            return_key_type="done",
            style=[styles.field, styles.search],
        ),
        pn.Row(
            pn.Text("Open issues only", style=styles.label),
            pn.Switch(value=only_open, on_change=set_only_open),
            style=styles.toolbar,
        ),
        pn.Text(snapshot.error or f"{len(matches)} issues", style=styles.status),
        pn.Text(status, style=styles.status) if status else None,
        InboxBadge(count=len(issues), on_press=on_badge_press, style={"margin": 8}) if status else None,
        pn.FlatList(
            # The unfiltered list reads the ListData, which patches single rows.
            data=repository.issues if show_all else matches,
            key_extractor=None if show_all else issue_key,
            render_item=render_issue,
            estimated_item_height=130,
            refresh_control=pn.RefreshControl(refreshing=snapshot.loading, on_refresh=repository.load),
            list_empty=pn.Text(
                "Loading..." if snapshot.loading or filtered.loading else "No matching issues",
                style=styles.status,
            ),
            style={"flex": 1},
        ),
        style=styles.screen,
    )


@pn.component
def IssueScreen(issue_id: str) -> pn.Node:
    issue = pn.use_store(repository.store, lambda snapshot: snapshot.find(issue_id))
    error = pn.use_store(repository.store, lambda snapshot: snapshot.error)
    styles = pn.use_styles(Styles)
    navigation = pn.use_navigation()
    title, set_title = pn.use_state(issue.title if issue else "")
    saving, set_saving = pn.use_state(False)

    if issue is None:
        return pn.Text("Issue unavailable", style=styles.error)

    async def save() -> None:
        set_saving(True)
        try:
            await repository.save(replace(issue, title=title))
        except Exception:
            return  # The repository rolled back; its error shows below.
        finally:
            set_saving(False)
        navigation.go_back()

    async def toggle() -> None:
        with suppress(Exception):  # A failed save rolls back and shows its error below.
            await repository.save(replace(issue, closed=not issue.closed))

    return pn.ScrollView(
        pn.Column(
            pn.Text(f"Issue #{issue.id}", style=styles.heading),
            pn.TextInput(
                value=title,
                on_change=set_title,
                accessibility_label="Issue title",
                return_key_type="done",
                style=styles.field,
            ),
            pn.Text(issue.body, style=styles.label),
            pn.Button("Reopen" if issue.closed else "Close issue", on_press=toggle),
            pn.Button("Saving..." if saving else "Save", on_press=save, disabled=saving or not title.strip()),
            pn.Text(error, style=styles.error) if error else None,
            style=styles.detail,
        ),
        style=styles.screen,
    )


Root = pn.StackNavigator(
    pn.Screen(InboxScreen, title="Inbox"),
    pn.Screen(IssueScreen, title="Issue"),
)


@pn.component
def App() -> pn.Node:
    pn.use_effect(repository.load, [])
    return pn.NavigationContainer(Root)
