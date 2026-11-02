"""Exercise the reference field journal: its data, its screens, its sync, and its failure paths.

These run the real app against a real SQLite file and a real localhost server. Only
the hardware is fake, through each capability's own off-device fallback.
"""

import asyncio
import importlib
import importlib.util
import json
import sqlite3
import sys
import threading
import time
import types
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

import pythonnative as pn
from pythonnative import background
from pythonnative.native_modules.app_state import dispatch_app_state
from pythonnative.native_modules.registry import (
    NativeModuleError,
    emit,
    register_python_module,
    unregister_python_module,
)
from pythonnative.purchases import Product, fake_store
from pythonnative.query import _reset_for_tests
from pythonnative.testing import RenderResult, render, wait_for

ROOT = Path(__file__).parents[1] / "examples/fieldnotes"
PACKAGE = "pn_reference_fieldnotes"
OSLO = {"latitude": 59.9139, "longitude": 10.7522, "accuracy": 12.0}


@dataclass
class Modules:
    """The app's modules, imported fresh for one test."""

    main: types.ModuleType
    models: types.ModuleType
    protocol: types.ModuleType
    repository: types.ModuleType
    database: types.ModuleType
    syncing: types.ModuleType
    reminders: types.ModuleType
    geo: types.ModuleType
    pro: types.ModuleType
    services: types.ModuleType
    journal_module: types.ModuleType
    fallback: types.ModuleType
    settings_screen: types.ModuleType
    journal_screen: types.ModuleType
    attachments: types.ModuleType
    map_screen: types.ModuleType

    @property
    def journal(self) -> Any:
        return self.journal_module.journal


@pytest.fixture
def fieldnotes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Modules]:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "app")]
    monkeypatch.setitem(sys.modules, PACKAGE, package)
    monkeypatch.setattr(pn.FileSystem, "app_dir", staticmethod(lambda: str(tmp_path)))
    _reset_for_tests()
    fake_store.reset()

    def load(name: str) -> types.ModuleType:
        return importlib.import_module(f"{PACKAGE}.{name}")

    modules = Modules(
        main=load("main"),
        models=load("models"),
        protocol=load("protocol"),
        repository=load("repository"),
        database=load("database"),
        syncing=load("syncing"),
        reminders=load("reminders"),
        geo=load("geo"),
        pro=load("pro"),
        services=load("services"),
        journal_module=load("journal"),
        fallback=load("ui.fallback"),
        settings_screen=load("ui.settings_screen"),
        journal_screen=load("ui.journal_screen"),
        attachments=load("ui.attachments"),
        map_screen=load("ui.map_screen"),
    )
    yield modules
    pn.set_error_handler(None)
    pn.set_error_fallback(None)
    pn.appearance.set_color_scheme(None)
    repository = modules.journal._repository
    if repository is not None:
        repository.database.close()
    _reset_for_tests()
    fake_store.reset()
    for name in list(sys.modules):
        if name.startswith(f"{PACKAGE}."):
            sys.modules.pop(name)


def open_journal(app: Modules) -> Any:
    pn.run_blocking(app.journal.load())
    return app.journal


def draft(app: Modules, **fields: Any) -> Any:
    return app.models.EntryDraft(**fields)


def write_file(path: Path, data: bytes = b"\xff\xd8sample") -> str:
    path.write_bytes(data)
    return str(path)


# ---------------------------------------------------------------------------
# The repository and its schema
# ---------------------------------------------------------------------------


def test_schema_migrates_from_each_older_version(fieldnotes: Modules, tmp_path: Path) -> None:
    database = fieldnotes.database
    connection = sqlite3.connect(tmp_path / "old.db")
    connection.create_function("folded", 1, str.casefold)
    connection.executescript(f"BEGIN; {database.MIGRATIONS[0]} PRAGMA user_version = 1; COMMIT;")
    database.migrate(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == len(database.MIGRATIONS)
    assert connection.execute("SELECT count(*) FROM reminders").fetchone()[0] == 0
    # Running it again on the latest version does nothing.
    database.migrate(connection)
    connection.close()


def test_entries_round_trip_through_a_reopened_file(fieldnotes: Modules, tmp_path: Path) -> None:
    models = fieldnotes.models
    path = tmp_path / "journal.db"
    first = fieldnotes.repository.Repository(fieldnotes.database.Database(path))
    place = models.Place(59.9, 10.7, 5.0, "Harbor")
    entry = pn.run_blocking(
        first.create(
            "a1",
            models.EntryDraft("Heron", "By the mill", ("birds", "river"), "Rain", place),
            now=100.0,
            device="here",
        )
    )
    assert entry.dirty and entry.tags == ("birds", "river")
    first.database.close()

    second = fieldnotes.repository.Repository(fieldnotes.database.Database(path))
    [read] = pn.run_blocking(second.list_entries())
    assert (read.title, read.body, read.conditions) == ("Heron", "By the mill", "Rain")
    assert read.tags == ("birds", "river")
    assert read.place == place
    assert read.created_at == 100.0
    second.database.close()


def test_updates_replace_tags_and_keep_the_creation_time(fieldnotes: Modules, tmp_path: Path) -> None:
    models = fieldnotes.models
    repository = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "j.db"))
    pn.run_blocking(repository.create("a", models.EntryDraft("One", tags=("old",)), now=1.0, device="d"))
    updated = pn.run_blocking(repository.update("a", models.EntryDraft("Two", tags=("new",)), now=2.0, device="d"))
    assert (updated.title, updated.tags, updated.created_at, updated.updated_at) == ("Two", ("new",), 1.0, 2.0)
    with pytest.raises(LookupError):
        pn.run_blocking(repository.update("missing", models.EntryDraft("x"), now=3.0, device="d"))
    repository.database.close()


def test_a_deleted_entry_leaves_a_tombstone_for_sync(fieldnotes: Modules, tmp_path: Path) -> None:
    models = fieldnotes.models
    repository = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "j.db"))
    pn.run_blocking(repository.create("a", models.EntryDraft("Gone"), now=1.0, device="d"))
    pn.run_blocking(repository.delete("a", now=2.0, device="d"))
    assert pn.run_blocking(repository.list_entries()) == ()
    [wire] = pn.run_blocking(repository.dirty_wire_entries())
    assert (wire.id, wire.deleted_at) == ("a", 2.0)
    repository.database.close()


def test_settings_keep_defaults_and_ignore_unknown_keys(fieldnotes: Modules, tmp_path: Path) -> None:
    repository = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "j.db"))
    assert pn.run_blocking(repository.load_settings()).background_sync is True
    pn.run_blocking(repository.save_settings({"lock_enabled": True, "from_a_future_version": 1}))
    settings = pn.run_blocking(repository.load_settings())
    assert settings.lock_enabled is True
    repository.database.close()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.fixture
def searchable(fieldnotes: Modules, tmp_path: Path) -> Iterator[Any]:
    models = fieldnotes.models
    repository = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "s.db"))
    rows = [
        ("a", models.EntryDraft("Heron at the mill", "Standing in the shallows", ("birds", "river"))),
        ("b", models.EntryDraft("Blåbær", "Picked by the trail", ("food",))),
        ("c", models.EntryDraft("100% cloud", "Nothing to see", ())),
        (
            "d",
            models.EntryDraft(
                "Ridge walk", "Long way up", ("hiking",), place=models.Place(1.0, 2.0, name="North Ridge")
            ),
        ),
    ]
    for index, (entry_id, row) in enumerate(rows):
        pn.run_blocking(repository.create(entry_id, row, now=float(index), device="d"))
    yield repository
    repository.database.close()


@pytest.mark.parametrize(
    "text, expected",
    [
        ("heron", ["a"]),
        ("HERON shallows", ["a"]),
        ("heron trail", []),
        ("blåbær", ["b"]),
        ("BLÅBÆR", ["b"]),
        ("#birds", ["a"]),
        ("#birds #food", []),
        ("mill #birds", ["a"]),
        ("north", ["d"]),
        ("hik", ["d"]),
        ("100%", ["c"]),
        ("%", ["c"]),
        ("_", []),
    ],
)
def test_search_finds_words_and_tags(fieldnotes: Modules, searchable: Any, text: str, expected: list[str]) -> None:
    query = fieldnotes.repository.parse_search(text)
    assert [entry.id for entry in pn.run_blocking(searchable.search(query))] == expected


def test_search_orders_newest_first_and_skips_deleted(fieldnotes: Modules, searchable: Any) -> None:
    query = fieldnotes.repository.parse_search("the")
    assert [entry.id for entry in pn.run_blocking(searchable.search(query))] == ["b", "a"]
    pn.run_blocking(searchable.delete("b", now=9.0, device="d"))
    assert [entry.id for entry in pn.run_blocking(searchable.search(query))] == ["a"]


def test_tags_normalize(fieldnotes: Modules) -> None:
    assert fieldnotes.models.parse_tags("#Birds, river  birds,#") == ("birds", "river")


# ---------------------------------------------------------------------------
# Create, edit, and browse, through the real screens
# ---------------------------------------------------------------------------


def go_to_tab(result: RenderResult, app: Modules, screen: str) -> None:
    """Switch tabs the way pressing the native tab bar does, which has no text to find here."""
    target = {"Settings": app.settings_screen.SettingsScreen, "Map": app.map_screen.MapScreen}[screen]
    result.act(lambda: app.main.navigation.navigate(target()))


def create_through_ui(result: RenderResult, title: str, body: str = "") -> None:
    result.press(result.get_by_label("New entry"))
    result.change_text(result.get_by_label("Title"), title)
    if body:
        result.change_text(result.get_by_label("Notes"), body)
    result.press(result.get_by_label("Save entry"))
    wait_for(lambda: result.get_by_text("Attachments"))


def test_create_edit_search_and_persist(fieldnotes: Modules, tmp_path: Path) -> None:
    register_python_module("Location", _FixedLocation(OSLO))
    result = render(fieldnotes.main.App())
    try:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        assert result.get_by_text("Offline. Your journal stays on this device.")

        create_through_ui(result, "Heron at the mill", "Standing in the shallows")
        assert wait_for(lambda: result.get_by_text("59.9139 N, 10.7522 E"))
        # The new entry replaced the editor, so back goes to the list, with it there.
        result.back()
        assert wait_for(lambda: result.get_by_label("Heron at the mill"))

        result.press(result.get_by_label("Heron at the mill"))
        result.press(result.get_by_text("Edit"))
        result.change_text(result.get_by_label("Title"), "Grey heron")
        result.change_text(result.get_by_label("Tags"), "#Birds river")
        result.press(result.get_by_label("Save entry"))
        assert wait_for(lambda: result.get_by_text("Grey heron"))
        assert result.get_by_text("#birds")
        result.back()

        result.change_text(result.get_by_label("Search the journal"), "nothing like this")
        assert wait_for(lambda: result.get_by_text("No matches"))
        result.change_text(result.get_by_label("Search the journal"), "shallows")
        assert wait_for(lambda: result.get_by_label("Grey heron"))
        result.press(result.get_by_label("#birds"))
        assert result.get_by_label("Search the journal").props["value"] == "shallows #birds"
        assert wait_for(lambda: result.get_by_label("Grey heron"))
    finally:
        result.unmount()
        unregister_python_module("Location")

    fresh = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "fieldnotes/journal.db"))
    [saved] = pn.run_blocking(fresh.list_entries())
    assert saved.title == "Grey heron" and saved.tags == ("birds", "river")
    assert saved.place is not None and saved.place.latitude == OSLO["latitude"]
    fresh.database.close()


def test_a_slow_fix_lands_on_the_saved_entry(fieldnotes: Modules) -> None:
    """Saving before the fix arrives shouldn't lose where the entry was written."""
    location = _FixedLocation(OSLO, delay=0.1)
    register_python_module("Location", location)
    result = render(fieldnotes.main.App())
    try:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        create_through_ui(result, "Quick note")
        assert wait_for(lambda: result.get_by_text("59.9139 N, 10.7522 E"), timeout=3)
    finally:
        result.unmount()
        unregister_python_module("Location")


def test_a_journal_saves_with_no_location_available(fieldnotes: Modules) -> None:
    result = render(fieldnotes.main.App())
    try:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        result.press(result.get_by_label("New entry"))
        assert wait_for(lambda: result.get_by_text("No location. Check that location access is on, or add one later."))
        result.change_text(result.get_by_label("Notes"), "Indoors today")
        result.press(result.get_by_label("Save entry"))
        assert wait_for(lambda: result.get_by_text("This entry has no location."))
    finally:
        result.unmount()


def test_discarding_an_edit_asks_first(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Keep me")))
    result = render(fieldnotes.main.App())
    try:
        result.press(wait_for(lambda: result.get_by_label("Keep me")))
        result.press(result.get_by_text("Edit"))
        result.change_text(result.get_by_label("Title"), "Changed")

        pn.Alert.set_test_response(0)  # Keep editing.
        result.back()
        result.settle()
        assert result.get_by_label("Title").props["value"] == "Changed"

        pn.Alert.set_test_response(1)  # Discard.
        result.back()
        assert wait_for(lambda: result.query_by_label("Title") is None)
        assert journal.snapshot.find(entry.id).title == "Keep me"
    finally:
        pn.Alert.set_test_response()
        result.unmount()


# ---------------------------------------------------------------------------
# Deep links
# ---------------------------------------------------------------------------


def test_paths_resolve_to_screens(fieldnotes: Modules) -> None:
    links = pn.navigation.LinkTable(fieldnotes.main.Root, fieldnotes.main.LINK_PREFIXES)
    state = links.state_from_url("fieldnotes://entries/abc123")
    assert state is not None
    assert (state.current.name, state.current.params) == ("EntryScreen", {"id": "abc123"})
    assert links.state_from_url("fieldnotes://new").current.name == "EditorScreen"
    assert links.state_from_url("elsewhere://entries/abc123") is None


def test_a_link_to_a_missing_entry_says_so(fieldnotes: Modules) -> None:
    open_journal(fieldnotes)
    saved = pn.navigation.LinkTable(fieldnotes.main.Root, fieldnotes.main.LINK_PREFIXES).state_from_url(
        "fieldnotes://entries/nope"
    )

    @pn.component
    def Harness() -> pn.Node:
        return pn.ThemeProvider(
            pn.NavigationContainer(fieldnotes.main.Root, initial_state=saved),
            light=fieldnotes.main.LIGHT,
            dark=fieldnotes.main.DARK,
        )

    with render(Harness()) as result:
        assert wait_for(lambda: result.get_by_text("Entry not found"))


def _response(url: Any, identifier: str = "entry-x") -> dict[str, Any]:
    return {"identifier": identifier, "title": "", "body": "", "data": {"url": url}, "action": "default"}


class _FakeNotifications:
    """The native module, with a launching tap and memory of what it scheduled."""

    def __init__(self, launch: Any = None, allowed: bool = True) -> None:
        self.launch = launch
        self.allowed = allowed
        self.scheduled: list[dict[str, Any]] = []
        self.canceled: list[str] = []

    def request_permission(self) -> bool:
        return self.allowed

    def schedule(self, title: str, body: str = "", **options: Any) -> bool:
        self.scheduled.append({"title": title, "body": body, **options})
        return self.allowed

    def cancel(self, identifier: str = "default") -> None:
        self.canceled.append(identifier)

    def cancel_all(self) -> None:
        pass

    def set_badge(self, count: int) -> None:
        pass

    def last_response(self) -> Any:
        return self.launch

    def set_listening(self, event: str, listening: bool) -> None:
        pass


def test_a_cold_start_tap_opens_the_entry_first(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Come back to me", body="The notes")))
    register_python_module("Notifications", _FakeNotifications(_response(f"fieldnotes://entries/{entry.id}")))
    try:
        with render(fieldnotes.main.App()) as result:
            assert wait_for(lambda: result.get_by_text("The notes"))
            assert result.back()
            assert wait_for(lambda: result.get_by_label("Come back to me"))
    finally:
        unregister_python_module("Notifications")


def test_a_tap_while_running_navigates(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Later", body="Tapped body")))
    register_python_module("Notifications", _FakeNotifications())
    try:
        with render(fieldnotes.main.App()) as result:
            wait_for(lambda: result.get_by_label("Later"))
            result.act(lambda: emit("Notifications", "response", _response(f"fieldnotes://entries/{entry.id}")))
            assert wait_for(lambda: result.get_by_text("Tapped body"))
    finally:
        unregister_python_module("Notifications")


@pytest.mark.parametrize(
    "url",
    ["fieldnotes://settings", "https://example.com/entries/abc", "fieldnotes://entries/../../etc", 42, None],
)
def test_a_forged_tap_opens_nothing(fieldnotes: Modules, url: Any) -> None:
    response = fieldnotes.main.Notifications  # noqa: F841 - the module exists, the tap is what's untrusted.
    from pythonnative.notifications import NotificationResponse

    assert fieldnotes.reminders.entry_id_from(NotificationResponse("x", data={"url": url})) is None


def test_reminders_schedule_with_a_deep_link_and_can_be_canceled(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Check the nest")))
    native = _FakeNotifications()
    register_python_module("Notifications", native)
    try:
        with render(fieldnotes.main.App()) as result:
            result.press(wait_for(lambda: result.get_by_label("Check the nest")))
            result.press(wait_for(lambda: result.get_by_label("In 1 hour")))
            assert wait_for(lambda: result.get_by_label("Cancel reminder"))
            [scheduled] = native.scheduled
            assert scheduled["title"] == "Check the nest"
            assert scheduled["data"] == {"url": f"fieldnotes://entries/{entry.id}"}
            assert scheduled["identifier"] == f"entry-{entry.id}"
            assert scheduled["delay_seconds"] == 3600.0

            result.press(result.get_by_label("Cancel reminder"))
            assert wait_for(lambda: result.get_by_label("In 1 hour"))
            assert native.canceled == [f"entry-{entry.id}"]
            assert journal.snapshot.find(entry.id).remind_at is None
    finally:
        unregister_python_module("Notifications")


def test_refused_notifications_are_explained(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Muted")))
    register_python_module("Notifications", _FakeNotifications(allowed=False))
    try:
        with render(fieldnotes.main.App()) as result:
            result.press(wait_for(lambda: result.get_by_label("Muted")))
            result.press(wait_for(lambda: result.get_by_label("Next week")))
            assert wait_for(lambda: result.get_by_text("Notifications are off", exact=False))
    finally:
        unregister_python_module("Notifications")


def test_past_reminders_clear_on_launch(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Past")))
    pn.run_blocking(journal.repository.set_reminder(entry.id, time.time() - 10))
    pn.run_blocking(journal.repository.clear_past_reminders(now=time.time()))
    assert pn.run_blocking(journal.repository.get(entry.id)).remind_at is None


# ---------------------------------------------------------------------------
# Attachments and the limit that Pro lifts
# ---------------------------------------------------------------------------


def test_attachments_move_into_the_journal_up_to_the_limit(fieldnotes: Modules, tmp_path: Path) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Photos")))
    for index in range(journal.FREE_ATTACHMENTS if hasattr(journal, "FREE_ATTACHMENTS") else 3):
        source = write_file(tmp_path / f"cache-{index}.jpg")
        attachment = pn.run_blocking(journal.add_attachment(entry.id, "photo", source, mime_type="image/jpeg"))
        assert not Path(source).exists(), "The file left the cache directory."
        assert Path(journal.file_path(attachment)).read_bytes() == b"\xff\xd8sample"
        assert not Path(attachment.path).is_absolute(), "An iOS container path changes between installs."

    with pytest.raises(fieldnotes.journal_module.AttachmentLimitReached):
        pn.run_blocking(
            journal.add_attachment(entry.id, "photo", write_file(tmp_path / "over.jpg"), mime_type="image/jpeg")
        )
    assert (tmp_path / "over.jpg").exists(), "A refused file stays where it was."

    pn.run_blocking(journal.update_settings(pro_owned=True))
    pn.run_blocking(
        journal.add_attachment(
            entry.id, "voice", write_file(tmp_path / "over.jpg"), mime_type="audio/mp4", duration=3.5
        )
    )
    updated = journal.snapshot.find(entry.id)
    assert len(updated.attachments) == 4
    assert updated.of_kind("voice")[0].duration == 3.5


def test_removing_an_attachment_deletes_its_file(fieldnotes: Modules, tmp_path: Path) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Photos")))
    attachment = pn.run_blocking(
        journal.add_attachment(entry.id, "photo", write_file(tmp_path / "a.jpg"), mime_type="image/jpeg")
    )
    path = Path(journal.file_path(attachment))
    pn.run_blocking(journal.remove_attachment(attachment))
    assert not path.exists()
    assert journal.snapshot.find(entry.id).attachments == ()


def test_a_full_entry_offers_pro(fieldnotes: Modules, tmp_path: Path) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Full")))
    for index in range(3):
        pn.run_blocking(
            journal.add_attachment(entry.id, "video", write_file(tmp_path / f"{index}.mp4"), mime_type="video/mp4")
        )
    with render(fieldnotes.main.App()) as result:
        result.press(wait_for(lambda: result.get_by_label("Full")))
        assert wait_for(lambda: result.get_by_text("3 of 3 attachments used."))
        result.press(result.get_by_text("Get Pro"))
        assert wait_for(lambda: result.get_by_text("One purchase, no subscription."))


def test_level_meter_and_level_reading(fieldnotes: Modules) -> None:
    fraction = fieldnotes.attachments.level_fraction
    assert (fraction(-160.0), fraction(-30.0), fraction(0.0)) == (0.0, 0.5, 1.0)
    tilt = fieldnotes.geo.tilt_degrees
    assert tilt(0.0, 9.81) == 0.0
    assert tilt(9.81, 0.0) == 90.0
    assert tilt(0.1, 0.1) is None, "Lying flat has no horizon."


def test_map_region_frames_places_across_the_date_line(fieldnotes: Modules) -> None:
    models, geo = fieldnotes.models, fieldnotes.geo
    assert geo.fit_region([]) == geo.WORLD
    single = geo.fit_region([models.Place(59.9, 10.7)])
    assert single.center.latitude == 59.9 and single.latitude_delta == 0.02
    both = geo.fit_region([models.Place(0.0, 179.0), models.Place(10.0, -179.0)], padding=1.0)
    assert both.center.latitude == 5.0
    assert abs(abs(both.center.longitude) - 180.0) < 1e-6
    assert abs(both.longitude_delta - 2.0) < 1e-6


# ---------------------------------------------------------------------------
# Sync against a real server on localhost
# ---------------------------------------------------------------------------


def _load_server() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("fieldnotes_server", ROOT / "server.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ServerThread:
    """The real dev server on its own thread and event loop."""

    def __init__(self, directory: Path) -> None:
        self.module = _load_server()
        self.directory = directory
        self.port = 0
        self.server: Any = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def _run(self, coroutine: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout=5)

    def start(self) -> "ServerThread":
        self.server = self.module.SyncServer(self.directory, port=self.port)
        self._run(self.server.start())
        self.port = self.server.port
        return self

    def stop(self) -> None:
        self._run(self.server.stop())

    def drop_clients(self) -> None:
        self.loop.call_soon_threadsafe(self.server.drop_clients)

    def close(self) -> None:
        self.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/sync"

    @property
    def clients(self) -> int:
        return len(self.server.clients)


@pytest.fixture
def server(tmp_path: Path) -> Iterator[ServerThread]:
    running = ServerThread(tmp_path / "server").start()
    yield running
    running.close()


def _fast_client(fieldnotes: Modules, journal: Any) -> Any:
    backoff = fieldnotes.syncing.Backoff(initial=0.05, maximum=0.2, jitter=0.0)
    return fieldnotes.syncing.SyncClient(journal, backoff=backoff, heartbeat=None, open_timeout=2.0)


async def _until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"Timed out waiting for {predicate}")
        await asyncio.sleep(0.01)


def test_backoff_doubles_to_a_ceiling_and_resets(fieldnotes: Modules) -> None:
    backoff = fieldnotes.syncing.Backoff(initial=1.0, maximum=8.0, jitter=0.5)
    delays = [backoff.next_delay(lambda: 1.0) for _ in range(5)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 8.0]
    backoff.reset()
    assert backoff.next_delay(lambda: 0.0) == 0.5, "Jitter takes up to half off."


def test_no_server_means_offline_and_no_connection(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    client = _fast_client(fieldnotes, journal)
    pn.run_blocking(client.run(""))
    assert journal.snapshot.sync.phase == "offline"


def test_reconnects_with_backoff_through_a_server_restart(fieldnotes: Modules, server: ServerThread) -> None:
    """Connect, lose the server, keep trying, and come back when it does, with the edit made meanwhile."""
    journal = open_journal(fieldnotes)
    client = _fast_client(fieldnotes, journal)
    phases: list[str] = []
    journal.store.subscribe(lambda: phases.append(journal.snapshot.sync.phase))

    async def scenario() -> None:
        task = asyncio.create_task(client.run(server.url))
        try:
            await _until(lambda: journal.snapshot.sync.phase == "connected")
            first = await journal.create_entry(draft(fieldnotes, title="Before the outage"))
            await _until(lambda: first.id in server.server.store.entries)

            await asyncio.to_thread(server.stop)
            await _until(lambda: journal.snapshot.sync.phase == "waiting")
            await _until(lambda: journal.snapshot.sync.attempt >= 3)
            assert "reach" in journal.snapshot.sync.detail or "drop" in journal.snapshot.sync.detail
            offline = await journal.create_entry(draft(fieldnotes, title="During the outage"))
            assert journal.snapshot.find(offline.id).dirty

            await asyncio.to_thread(server.start)
            await _until(lambda: journal.snapshot.sync.phase == "connected")
            assert client.backoff.failures == 0, "A working connection starts the backoff over."
            await _until(lambda: offline.id in server.server.store.entries)
            await _until(lambda: not journal.snapshot.find(offline.id).dirty)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    pn.run_blocking(scenario())
    assert "connecting" in phases and "waiting" in phases and "connected" in phases


def test_a_dropped_connection_reconnects(fieldnotes: Modules, server: ServerThread) -> None:
    journal = open_journal(fieldnotes)
    client = _fast_client(fieldnotes, journal)

    async def scenario() -> None:
        task = asyncio.create_task(client.run(server.url))
        try:
            await _until(lambda: server.clients == 1 and journal.snapshot.sync.phase == "connected")
            server.drop_clients()
            await _until(lambda: journal.snapshot.sync.phase != "connected")
            await _until(lambda: journal.snapshot.sync.phase == "connected")
            assert server.clients == 1
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    pn.run_blocking(scenario())


def test_retry_now_cuts_the_wait_short(fieldnotes: Modules, server: ServerThread) -> None:
    journal = open_journal(fieldnotes)
    backoff = fieldnotes.syncing.Backoff(initial=30.0, maximum=30.0, jitter=0.0)
    client = fieldnotes.syncing.SyncClient(journal, backoff=backoff, heartbeat=None, open_timeout=2.0)
    server.stop()

    async def scenario() -> None:
        task = asyncio.create_task(client.run(server.url))
        try:
            await _until(lambda: journal.snapshot.sync.phase == "waiting")
            assert journal.snapshot.sync.retry_in == 30.0
            await asyncio.to_thread(server.start)
            client.retry_now()
            await _until(lambda: journal.snapshot.sync.phase == "connected", timeout=3.0)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    pn.run_blocking(scenario())


def test_a_server_that_breaks_protocol_backs_off(fieldnotes: Modules) -> None:
    """A wrong address that answers with HTTP isn't a WebSocket, and shouldn't spin."""
    journal = open_journal(fieldnotes)
    client = _fast_client(fieldnotes, journal)

    async def http_only(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()

    async def scenario() -> None:
        listener = await asyncio.start_server(http_only, "127.0.0.1", 0)
        port = listener.sockets[0].getsockname()[1]
        task = asyncio.create_task(client.run(f"ws://127.0.0.1:{port}/sync"))
        try:
            await _until(lambda: journal.snapshot.sync.attempt >= 2)
            assert "refused" in journal.snapshot.sync.detail
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            listener.close()

    pn.run_blocking(scenario())


class _Peer:
    """A second device: its own journal file, talking to the same server."""

    def __init__(self, fieldnotes: Modules, tmp_path: Path) -> None:
        journal_module = fieldnotes.journal_module
        self.journal = journal_module.Journal()
        self.journal._repository = fieldnotes.repository.Repository(
            fieldnotes.database.Database(tmp_path / "peer" / "journal.db")
        )
        self.client = _fast_client(fieldnotes, self.journal)

    def close(self) -> None:
        self.journal.repository.database.close()


def test_two_devices_converge(fieldnotes: Modules, server: ServerThread, tmp_path: Path) -> None:
    journal = open_journal(fieldnotes)
    peer = _Peer(fieldnotes, tmp_path)
    pn.run_blocking(peer.journal.load())
    assert journal.settings.device_id != peer.journal.settings.device_id

    async def scenario() -> None:
        tasks = [
            asyncio.create_task(_fast_client(fieldnotes, journal).run(server.url)),
            asyncio.create_task(peer.client.run(server.url)),
        ]
        try:
            await _until(lambda: journal.snapshot.sync.phase == "connected")
            await _until(lambda: peer.journal.snapshot.sync.phase == "connected")

            mine = await journal.create_entry(draft(fieldnotes, title="Mine", body="First"))
            await _until(lambda: peer.journal.snapshot.find(mine.id) is not None)

            await peer.journal.update_entry(mine.id, draft(fieldnotes, title="Mine", body="Edited over there"))
            await _until(lambda: journal.snapshot.find(mine.id).body == "Edited over there")
            await _until(lambda: not peer.journal.snapshot.find(mine.id).dirty)

            await journal.delete_entry(mine.id)
            await _until(lambda: peer.journal.snapshot.find(mine.id) is None)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            peer.close()

    pn.run_blocking(scenario())


def test_the_newer_edit_wins_on_both_sides(fieldnotes: Modules, server: ServerThread, tmp_path: Path) -> None:
    """Two offline devices edit one entry. Whichever wrote last wins everywhere, regardless of who syncs first."""
    journal = open_journal(fieldnotes)
    peer = _Peer(fieldnotes, tmp_path)
    pn.run_blocking(peer.journal.load())

    async def scenario() -> None:
        entry = await journal.create_entry(draft(fieldnotes, title="Shared"))
        await _fast_client(fieldnotes, journal).sync_once(server.url)
        await _fast_client(fieldnotes, peer.journal).sync_once(server.url)
        assert peer.journal.snapshot.find(entry.id) is not None

        await journal.update_entry(entry.id, draft(fieldnotes, title="Older edit"))
        await asyncio.sleep(0.01)
        await peer.journal.update_entry(entry.id, draft(fieldnotes, title="Newer edit"))

        # The newer one reaches the server first, so the older one has to lose on arrival.
        await _fast_client(fieldnotes, peer.journal).sync_once(server.url)
        await _fast_client(fieldnotes, journal).sync_once(server.url)
        await _until(lambda: journal.snapshot.find(entry.id).title == "Newer edit")
        assert server.server.store.entries[entry.id]["title"] == "Newer edit"
        peer.close()

    pn.run_blocking(scenario())


def test_attachments_union_when_text_conflicts(fieldnotes: Modules, tmp_path: Path) -> None:
    models = fieldnotes.models
    repository = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "j.db"))
    wire = fieldnotes.protocol

    async def scenario() -> None:
        await repository.create("e", models.EntryDraft("Mine"), now=5.0, device="a")
        await repository.add_attachment(models.Attachment("mine", "e", "photo", "x/mine.jpg", "image/jpeg", "m"))
        remote = wire.WireEntry(
            id="e",
            title="Older, from them",
            body="",
            tags=(),
            conditions="",
            latitude=None,
            longitude=None,
            accuracy=None,
            place_name="",
            created_at=1.0,
            updated_at=2.0,
            device="b",
            attachments=(
                wire.WireAttachment("theirs", "photo", "image/jpeg", "t", 9, 0.0, 3.0, "/attachments/theirs"),
            ),
        )
        merge = await repository.apply_remote(remote)
        assert merge.changed
        entry = await repository.get("e")
        assert entry.title == "Mine", "The older text lost."
        assert {item.id for item in entry.attachments} == {"mine", "theirs"}, "Both photos stay."
        uploads, downloads = await repository.transfers_pending()
        assert [item.id for item in uploads] == ["mine"]
        assert [item.id for item in downloads] == ["theirs"]
        assert entry.dirty, "The server still hasn't heard about ours."

    pn.run_blocking(scenario())
    repository.database.close()


def test_a_late_ack_doesnt_clear_a_newer_change(fieldnotes: Modules, tmp_path: Path) -> None:
    models = fieldnotes.models
    repository = fieldnotes.repository.Repository(fieldnotes.database.Database(tmp_path / "j.db"))

    async def scenario() -> None:
        await repository.create("e", models.EntryDraft("One"), now=1.0, device="a")
        [pushed] = await repository.dirty_wire_entries()
        await repository.update("e", models.EntryDraft("Two"), now=2.0, device="a")
        await repository.mark_synced("e", pushed.change)
        assert (await repository.get("e")).dirty, "The second edit still has to go."
        [again] = await repository.dirty_wire_entries()
        await repository.mark_synced("e", again.change)
        assert not (await repository.get("e")).dirty

    pn.run_blocking(scenario())
    repository.database.close()


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("", ""),
        ("   ", ""),
        ("localhost:8770", "ws://localhost:8770/sync"),
        ("http://10.0.2.2:8770", "ws://10.0.2.2:8770/sync"),
        ("https://sync.example.com", "wss://sync.example.com/sync"),
        ("wss://sync.example.com/custom/", "wss://sync.example.com/custom"),
    ],
)
def test_server_addresses_normalize(fieldnotes: Modules, typed: str, expected: str) -> None:
    assert fieldnotes.protocol.normalize_server_url(typed) == expected


@pytest.mark.parametrize("typed", ["ftp://example.com", "http://", "host:notaport"])
def test_bad_server_addresses_are_rejected(fieldnotes: Modules, typed: str) -> None:
    with pytest.raises(ValueError):
        fieldnotes.protocol.normalize_server_url(typed)


def test_settings_connect_and_report_status(fieldnotes: Modules, server: ServerThread) -> None:
    with render(fieldnotes.main.App()) as result:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        go_to_tab(result, fieldnotes, "Settings")
        assert wait_for(lambda: result.get_by_text("Offline. No sync server", exact=False))

        result.change_text(result.get_by_label("Server address"), "not a server://")
        result.press(result.get_by_label("Save address"))
        assert wait_for(lambda: result.get_by_text("doesn't look like a server", exact=False))

        result.change_text(result.get_by_label("Server address"), f"127.0.0.1:{server.port}")
        result.press(result.get_by_label("Save address"))
        assert wait_for(lambda: result.get_by_text("Connected.", exact=False), timeout=3)
        assert server.clients == 1
    # Unmounting canceled the effect, which closed the socket.
    assert wait_for(lambda: server.clients == 0, timeout=3)


# ---------------------------------------------------------------------------
# Uploads and the background task
# ---------------------------------------------------------------------------


def test_uploads_report_progress_and_reach_another_device(
    fieldnotes: Modules, server: ServerThread, tmp_path: Path
) -> None:
    journal = open_journal(fieldnotes)
    payload = bytes(range(256)) * 2048  # 512 KB, so progress has several steps.
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="With a photo")))
    pn.run_blocking(
        journal.add_attachment(entry.id, "photo", write_file(tmp_path / "big.jpg", payload), mime_type="image/jpeg")
    )
    progress: list[float] = []
    journal.store.subscribe(lambda: progress.extend(journal.snapshot.transfers.values()))
    queue = fieldnotes.services.TransferQueue(journal)

    async def scenario() -> None:
        assert await queue.run(server.url) == 1
        await fieldnotes.syncing.SyncClient(journal).sync_once(server.url)

        peer = _Peer(fieldnotes, tmp_path)
        await peer.journal.load()
        await fieldnotes.syncing.SyncClient(peer.journal).sync_once(server.url)
        assert await fieldnotes.services.TransferQueue(peer.journal).run(server.url) == 1
        [received] = peer.journal.snapshot.find(entry.id).attachments
        peer_file = Path(peer.journal.repository.database.path).parent / received.path
        assert received.size == len(payload) and received.is_local
        # The peer's data directory is the shared test one, so the path comes from the journal.
        assert Path(peer.journal.file_path(received)).read_bytes() == payload
        assert peer_file.name == Path(received.path).name
        peer.close()

    pn.run_blocking(scenario())
    assert len(set(progress)) > 2, "Progress moved in steps."
    assert max(progress) == 1.0
    assert journal.snapshot.transfers == {}, "Nothing is left in flight."
    [attachment] = journal.snapshot.find(entry.id).attachments
    assert attachment.remote_path.startswith("/attachments/") and not attachment.needs_upload


def test_a_failed_upload_stays_queued_and_says_why(fieldnotes: Modules, tmp_path: Path) -> None:
    journal = open_journal(fieldnotes)
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Stranded")))
    pn.run_blocking(journal.add_attachment(entry.id, "photo", write_file(tmp_path / "a.jpg"), mime_type="image/jpeg"))
    queue = fieldnotes.services.TransferQueue(journal)
    assert pn.run_blocking(queue.run("ws://127.0.0.1:9/sync")) == 0
    assert "didn't transfer" in journal.snapshot.transfer_error
    [attachment] = journal.snapshot.find(entry.id).attachments
    assert attachment.needs_upload


def test_the_background_task_syncs_with_no_screen(fieldnotes: Modules, server: ServerThread, tmp_path: Path) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(journal.update_settings(server_url=server.url))
    entry = pn.run_blocking(journal.create_entry(draft(fieldnotes, title="While you slept")))
    pn.run_blocking(journal.add_attachment(entry.id, "photo", write_file(tmp_path / "a.jpg"), mime_type="image/jpeg"))

    assert pn.run_blocking(background.run_now(fieldnotes.services.TASK_NAME)) == background.Result.SUCCESS
    pn.run_blocking(fieldnotes.syncing.SyncClient(journal).sync_once(server.url))

    assert server.server.store.entries[entry.id]["title"] == "While you slept"
    assert not journal.snapshot.find(entry.id).dirty
    [attachment] = server.server.store.entries[entry.id]["attachments"]
    assert attachment["remote_path"] == f"/attachments/{attachment['id']}"
    assert server.server.store.attachment_path(attachment["id"]).read_bytes() == b"\xff\xd8sample"


def test_the_background_task_retries_when_the_server_is_down(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(journal.update_settings(server_url="ws://127.0.0.1:9/sync"))
    assert pn.run_blocking(background.run_now(fieldnotes.services.TASK_NAME)) == background.Result.RETRY


def test_the_background_task_is_quiet_with_no_server(fieldnotes: Modules) -> None:
    assert pn.run_blocking(background.run_now(fieldnotes.services.TASK_NAME)) == background.Result.SUCCESS


def test_a_refused_schedule_becomes_a_note(fieldnotes: Modules, monkeypatch: pytest.MonkeyPatch) -> None:
    journal = open_journal(fieldnotes)

    def refuse(name: str) -> None:
        raise NativeModuleError("Background", "schedule", "the simulator refuses", "unavailable")

    monkeypatch.setattr(background, "schedule", refuse)
    fieldnotes.services.apply_background_setting(True)
    assert "won't run background work" in journal.snapshot.background_note
    fieldnotes.services.apply_background_setting(False)
    assert journal.snapshot.background_note == ""


def test_the_toml_declares_exactly_what_the_app_uses() -> None:
    tomllib = importlib.import_module("tomllib")
    config = tomllib.loads((ROOT / "pythonnative.toml").read_text())
    used = set()
    for path in (ROOT / "app").rglob("*.py"):
        for line in path.read_text().splitlines():
            if line.startswith("from pythonnative."):
                used.add(line.split()[1].split(".")[1])
            elif line.startswith("from pythonnative import "):
                used.update(name.strip() for name in line.split("import")[1].split(","))
    capabilities = {
        "audio",
        "background",
        "biometrics",
        "camera",
        "location",
        "maps",
        "notifications",
        "pickers",
        "purchases",
        "push",
        "sensors",
        "video",
    }
    assert set(config["plugins"]["use"]) == used & capabilities
    assert "push" not in config["plugins"]["use"]
    assert config["app"]["url_schemes"] == ["fieldnotes"]
    assert "android_api_key" not in config["plugins"].get("maps", {})
    from PIL import Image

    with Image.open(ROOT / config["assets"]["icon"]) as icon:
        assert icon.size == (1024, 1024)


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------


def _sell_pro(fieldnotes: Modules) -> None:
    fake_store.set_products(
        [Product(fieldnotes.pro.PRODUCT_ID, "Pro", "Unlimited", Decimal("4.99"), "USD", "$4.99", "non_consumable")]
    )


def test_buying_pro_unlocks_and_finishes_the_transaction(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    _sell_pro(fieldnotes)
    with render(fieldnotes.main.App()) as result:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        go_to_tab(result, fieldnotes, "Settings")
        result.press(wait_for(lambda: result.get_by_label("See Pro")))
        button = wait_for(lambda: result.get_by_label("Unlock Pro for $4.99"))
        result.press(button)
        assert wait_for(lambda: result.get_by_text("Pro is unlocked. Thank you."))
    assert journal.snapshot.is_pro
    assert len(fake_store.finished) == 1, "An unfinished transaction would be delivered again."
    assert pn.run_blocking(journal.repository.load_settings()).pro_owned, "It's still unlocked on the next launch."


def test_a_canceled_purchase_changes_nothing(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    _sell_pro(fieldnotes)
    fake_store.set_outcome("cancelled")
    pn.run_blocking(fieldnotes.pro.pro.refresh())
    pn.run_blocking(fieldnotes.pro.pro.buy())
    assert not journal.snapshot.is_pro
    assert "canceled" in journal.snapshot.pro.message
    assert fake_store.finished == []


def test_a_pending_purchase_unlocks_when_it_arrives(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    _sell_pro(fieldnotes)
    fake_store.set_outcome("pending")
    stop = fieldnotes.pro.pro.listen()
    pn.run_blocking(fieldnotes.pro.pro.buy())
    assert not journal.snapshot.is_pro and "approval" in journal.snapshot.pro.message
    try:
        fake_store.push_update(fieldnotes.pro.PRODUCT_ID)
        assert wait_for(lambda: journal.snapshot.is_pro)
        assert wait_for(lambda: len(fake_store.finished) == 1)
    finally:
        stop()


def test_store_unavailable_is_a_clear_state(fieldnotes: Modules) -> None:
    open_journal(fieldnotes)
    fake_store.set_available(False)
    with render(fieldnotes.main.App()) as result:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        go_to_tab(result, fieldnotes, "Settings")
        result.press(wait_for(lambda: result.get_by_label("See Pro")))
        assert wait_for(lambda: result.get_by_text("The store isn't available on this device", exact=False))
        assert result.query_by_text("Unlock Pro", exact=False) is None
        assert result.get_by_label("Restore purchase").props["accessibility_state"]["disabled"] is True


def test_a_store_that_doesnt_sell_it_says_so(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(fieldnotes.pro.pro.refresh())
    assert journal.snapshot.pro.phase == "no_product"


def test_a_store_failure_is_explained(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    _sell_pro(fieldnotes)
    fake_store.set_outcome(NativeModuleError("Purchases", "purchase", "no connection", "unavailable"))
    pn.run_blocking(fieldnotes.pro.pro.buy())
    assert "Couldn't reach the store" in journal.snapshot.pro.message
    assert journal.snapshot.pro.busy is False, "The button comes back."


def test_restore_finds_what_was_bought(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    _sell_pro(fieldnotes)
    pn.run_blocking(fieldnotes.pro.pro.restore())
    assert "No earlier purchase" in journal.snapshot.pro.message
    pn.run_blocking(fieldnotes.pro.pro.buy())
    pn.run_blocking(journal.update_settings(pro_owned=False))
    pn.run_blocking(fieldnotes.pro.pro.restore())
    assert journal.snapshot.is_pro


# ---------------------------------------------------------------------------
# The error handler, the log, and the fallback
# ---------------------------------------------------------------------------


def _error_lines(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "fieldnotes/errors.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_an_event_error_reaches_the_log_and_the_screen(fieldnotes: Modules, tmp_path: Path) -> None:
    open_journal(fieldnotes)
    with render(fieldnotes.main.App()) as result:
        wait_for(lambda: result.get_by_text("An empty notebook"))
        go_to_tab(result, fieldnotes, "Settings")
        result.press(wait_for(lambda: result.get_by_label("Log a test error")))
        result.settle()
        assert wait_for(lambda: result.get_by_text("1"))

        [record] = _error_lines(tmp_path)
        assert record["kind"] == "TestError"
        assert record["phase"].startswith("event")
        assert "fail_in_handler" in record["trace"]

        result.press(result.get_by_label("Error log"))
        assert wait_for(lambda: result.get_by_text("TestError: This is a test of the error log."))
        result.press(result.get_by_label("Clear"))
        assert wait_for(lambda: result.get_by_text("No errors"))
    assert not (tmp_path / "fieldnotes/errors.jsonl").exists()


def test_the_log_keeps_its_size_and_survives_a_torn_line(fieldnotes: Modules, tmp_path: Path) -> None:
    errors = fieldnotes.main.journal.errors
    for number in range(450):
        errors.record(ValueError(f"number {number}"), "async")
    lines = (tmp_path / "fieldnotes/errors.jsonl").read_text().splitlines()
    assert len(lines) <= 400
    with (tmp_path / "fieldnotes/errors.jsonl").open("a") as file:
        file.write('{"at": 1, "pha')
    records = errors.read()
    assert records[0].message == "number 449", "Newest first, and the torn line is skipped."
    assert len(records) == 199


def test_the_fallback_explains_and_recovers(fieldnotes: Modules) -> None:
    """Render what a release build's root boundary would, with the app's fallback in place."""
    from pythonnative.components.structural import root_error_fallback

    state = {"fail": True}

    @pn.component
    def Page() -> pn.Node:
        if state["fail"]:
            raise fieldnotes.settings_screen.TestError()
        return pn.Text("Back to normal")

    assert fieldnotes.main.error_fallback is not None
    with render(pn.ErrorBoundary(Page(), fallback=root_error_fallback)) as result:
        assert wait_for(lambda: result.get_by_text("This page came apart"))
        assert result.get_by_text("TestError: This is a test of the error screen.")
        state["fail"] = False
        result.press(result.get_by_label("Try again"))
        assert wait_for(lambda: result.get_by_text("Back to normal"))


def test_a_database_that_wont_open_is_reported_not_fatal(fieldnotes: Modules, tmp_path: Path) -> None:
    (tmp_path / "fieldnotes").mkdir()
    (tmp_path / "fieldnotes/journal.db").write_bytes(b"this is not a database, and it's longer than a header " * 40)
    with render(fieldnotes.main.App()) as result:
        assert wait_for(lambda: result.get_by_text("Couldn't open the journal", exact=False))


# ---------------------------------------------------------------------------
# The lock
# ---------------------------------------------------------------------------


class _FakeBiometrics:
    def __init__(self, available: bool = True, answers: tuple[bool, ...] = (True,)) -> None:
        self.available = available
        self.answers = list(answers)
        self.asked = 0

    def is_available(self) -> bool:
        return self.available

    def authenticate(self, reason: str = "") -> bool:
        self.asked += 1
        return self.answers.pop(0)


def test_the_lock_covers_the_app_until_biometrics_succeed(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(journal.update_settings(lock_enabled=True))
    journal.set_locked(True)
    native = _FakeBiometrics(answers=(False, True))
    register_python_module("Biometrics", native)
    try:
        with render(fieldnotes.main.App()) as result:
            assert wait_for(lambda: result.get_by_text("That didn't work. Try again."))
            assert native.asked == 1, "It prompted on its own."
            result.press(result.get_by_label("Unlock"))
            assert wait_for(lambda: result.query_by_text("Field Notes is locked") is None)
            assert not journal.snapshot.locked
    finally:
        unregister_python_module("Biometrics")


def test_going_to_the_background_locks_again(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(journal.update_settings(lock_enabled=True))
    native = _FakeBiometrics(answers=(False,))
    register_python_module("Biometrics", native)
    try:
        with render(fieldnotes.main.App()) as result:
            result.act(lambda: dispatch_app_state("active"))
            assert not journal.snapshot.locked
            assert native.asked == 0, "A hidden lock screen doesn't prompt."
            result.act(lambda: dispatch_app_state("background"))
            assert wait_for(lambda: result.get_by_text("Field Notes is locked"))
            assert journal.snapshot.locked and native.asked == 1
    finally:
        unregister_python_module("Biometrics")


def test_a_lost_enrollment_doesnt_strand_the_journal(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    pn.run_blocking(journal.update_settings(lock_enabled=True))
    journal.set_locked(True)
    register_python_module("Biometrics", _FakeBiometrics(available=False))
    try:
        with render(fieldnotes.main.App()) as result:
            result.press(wait_for(lambda: result.get_by_label("Open anyway")))
            assert wait_for(lambda: not journal.snapshot.locked)
    finally:
        unregister_python_module("Biometrics")


# ---------------------------------------------------------------------------
# Location


class _FixedLocation:
    """The native module, with a fix that takes a moment to arrive."""

    def __init__(self, fix: dict[str, float], delay: float = 0.0) -> None:
        self.fix = fix
        self.delay = delay

    async def get_current(self, **options: Any) -> dict[str, float]:
        await asyncio.sleep(self.delay)
        return self.fix


# Map tab
# ---------------------------------------------------------------------------


def test_a_map_marker_opens_its_entry(fieldnotes: Modules) -> None:
    journal = open_journal(fieldnotes)
    models = fieldnotes.models
    entry = pn.run_blocking(
        journal.create_entry(draft(fieldnotes, title="At the summit", body="Clear", place=models.Place(61.0, 8.5)))
    )
    pn.run_blocking(journal.create_entry(draft(fieldnotes, title="Nowhere in particular")))
    with render(fieldnotes.main.App()) as result:
        wait_for(lambda: result.get_by_label("At the summit"))
        go_to_tab(result, fieldnotes, "Map")
        assert wait_for(lambda: result.get_by_text("1 of 2 entries have a location."))
        map_view = wait_for(lambda: result.get_by_label("Map of your journal entries"))
        assert [marker.id for marker in map_view.props["markers"]] == [entry.id]
        result.fire(map_view, "on_marker_press", entry.id)
        assert wait_for(lambda: result.get_by_text("Clear"))


def test_a_map_that_cant_load_shows_the_places_as_a_list(fieldnotes: Modules) -> None:
    """What an Android build with no Maps key does."""
    journal = open_journal(fieldnotes)
    pn.run_blocking(
        journal.create_entry(
            draft(
                fieldnotes,
                title="Summit",
                body="High up",
                place=fieldnotes.models.Place(61.0, 8.5, name="Galdhøpiggen"),
            )
        )
    )
    with render(fieldnotes.main.App()) as result:
        wait_for(lambda: result.get_by_label("Summit"))
        go_to_tab(result, fieldnotes, "Map")
        map_view = wait_for(lambda: result.get_by_label("Map of your journal entries"))
        result.fire(map_view, "on_error", "Add an API key to show this map.")
        assert wait_for(lambda: result.get_by_text("Add an API key to show this map."))
        assert result.get_by_text("Galdhøpiggen")
        result.press(result.get_by_label("Open Summit"))
        assert wait_for(lambda: result.get_by_text("High up"))
