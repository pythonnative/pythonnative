"""A complete offline inbox built from Python function components."""

import asyncio
from dataclasses import replace

from inbox_extension import InboxBadge, InboxBatch, InboxRecord, InboxTools

import pythonnative as pn
from pythonnative.hooks import Context

from .repository import Issue, Repository, Snapshot

RepositoryContext: Context[Repository | None] = pn.create_context(None)
ThemeContext = pn.create_context("#FFFFFF")
Stack = pn.create_stack_navigator()


def use_repository() -> tuple[Repository, Snapshot]:
    repository = pn.use_context(RepositoryContext)
    if repository is None:
        raise RuntimeError("The inbox requires a repository provider")
    snapshot = pn.use_subscription(repository.subscribe, lambda: repository.snapshot)
    return repository, snapshot


@pn.component
def IssueRow(issue: Issue) -> pn.Element:
    navigation = pn.use_navigation()
    background = pn.use_context(ThemeContext)
    return pn.Pressable(
        pn.Column(
            pn.Text(issue.title, style={"bold": True, "font_size": 17}),
            pn.Text(issue.body, style={"font_size": 14, "color": "#52606D"}),
            pn.Text("Closed" if issue.closed else "Open", style={"color": "#2563EB"}),
            style={
                "padding": 16,
                "gap": 6,
                "background_color": background,
                "border_bottom_width": 1,
                "border_color": "#DEE4EA",
            },
        ),
        on_press=lambda: navigation.push("Issue", id=issue.id),
        accessibility_label=issue.title,
    )


def issue_key(issue: Issue, index: int) -> int:
    return issue.id


def render_issue(issue: Issue, index: int) -> pn.Element:
    return IssueRow(issue)


@pn.component
def Inbox() -> pn.Element:
    repository, snapshot = use_repository()
    search, set_search = pn.use_state("")
    deferred = pn.use_deferred_value(search)
    only_open, set_only_open = pn.use_state(False)
    status, set_status = pn.use_state("")

    def subscribe_extension():
        if pn.Platform.OS in {"ios", "android"}:

            def prepared(batch: InboxBatch) -> None:
                set_status(batch.message)

            return InboxTools.on_prepared(prepared)

    pn.use_effect(subscribe_extension, [])

    async def prepare_extension() -> None:
        if pn.Platform.OS in {"ios", "android"}:
            # Replacing the snapshot or leaving this screen cancels the native
            # work through the generated adapter's cancellation callback.
            records = [
                InboxRecord(str(row.id), row.title, ("closed" if row.closed else "open",)) for row in snapshot.issues
            ]
            batch = await InboxTools.prepare(records=records)
            assert all(isinstance(row, InboxRecord) for row in batch.records)
            set_status(batch.message)

    pn.use_effect(prepare_extension, [snapshot.revision])

    async def cancel_preparation(count: int) -> None:
        assert count == len(snapshot.issues)
        delivered = []
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
            cancelled_event = any(row.identifier == "cancel-check" for batch in delivered for row in batch.records)
            set_status("Cancellation failed" if cancelled_event else "Preparation cancelled")
        finally:
            work.cancel()
            unsubscribe()

    async def filter_issues() -> list[Issue]:
        # Real cooperative async work with cancellation while typing.
        selected: list[Issue] = []
        for start in range(0, len(snapshot.issues), 100):
            selected.extend(
                row
                for row in snapshot.issues[start : start + 100]
                if deferred.casefold() in (row.title + row.body).casefold() and (not only_open or not row.closed)
            )
            await asyncio.sleep(0)
        return selected

    query: pn.QueryResult[list[Issue]] = pn.use_query(
        filter_issues, [snapshot.revision, deferred, only_open], initial=[]
    )
    return pn.Column(
        pn.TextInput(
            value=search,
            on_change=set_search,
            placeholder="Search 2,000 issues",
            accessibility_label="Search issues",
            return_key_type="done",
        ),
        pn.Row(
            pn.Text("Open issues only"),
            pn.Switch(value=only_open, on_change=set_only_open),
            style={"gap": 12, "padding": 12},
        ),
        pn.Text(snapshot.error or f"{len(query.data or [])} issues", style={"padding": 12}),
        pn.Text(status) if status else None,
        InboxBadge(count=len(snapshot.issues), on_press=cancel_preparation, style={"margin": 8}) if status else None,
        pn.FlatList(
            data=query.data or [],
            key_extractor=issue_key,
            render_item=render_issue,
            estimated_item_height=130,
            refresh_control=pn.RefreshControl(refreshing=snapshot.loading, on_refresh=repository.load),
            list_empty=pn.Text("Loading..." if snapshot.loading or query.loading else "No matching issues"),
            style={"flex": 1},
        ),
        style={"flex": 1},
    )


@pn.component
def Detail() -> pn.Element:
    repository, snapshot = use_repository()
    route = pn.use_route()
    issue = next((row for row in snapshot.issues if row.id == route.params["id"]), None)
    title, set_title = pn.use_state(issue.title if issue else "")
    saving, set_saving = pn.use_state(False)
    navigation = pn.use_navigation()

    async def save() -> None:
        set_saving(True)
        try:
            await repository.update(replace(issue, title=title))
            navigation.go_back()
        finally:
            set_saving(False)

    async def toggle() -> None:
        await repository.update(replace(issue, closed=not issue.closed))

    if issue is None:
        return pn.Text("Issue unavailable")
    return pn.ScrollView(
        pn.Column(
            pn.Text(f"Issue #{issue.id}", style={"font_size": 24, "bold": True}),
            pn.TextInput(value=title, on_change=set_title, accessibility_label="Issue title", return_key_type="done"),
            pn.Text(issue.body),
            pn.Button("Reopen" if issue.closed else "Close issue", on_press=toggle),
            pn.Button("Saving..." if saving else "Save", on_press=save, disabled=saving or not title.strip()),
            pn.Text(snapshot.error),
            style={"padding": 20, "gap": 16},
        )
    )


@pn.component
def App() -> pn.Element:
    repository = pn.use_memo(Repository, [])
    pn.use_effect(repository.load, [])
    return RepositoryContext.Provider(
        repository,
        ThemeContext.Provider(
            "#FFFFFF",
            pn.NavigationContainer(
                Stack.Navigator(
                    Stack.Screen("Inbox", Inbox, title="Inbox"),
                    Stack.Screen("Issue", Detail, title="Issue"),
                )
            ),
        ),
    )
