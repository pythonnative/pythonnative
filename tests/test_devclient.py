"""The on-device dev client: URL handling, overlay sync, and reload wiring."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator, List

import pytest

from pythonnative import devclient
from pythonnative.devserver import DevServer
from pythonnative.devserver.watcher import snapshot_sources
from pythonnative.hot_reload import configure_dev_environment


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _wait(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _write(root / "app" / "__init__.py", "")
    _write(root / "app" / "main.py", "VALUE = 1\n")
    _write(root / "app" / "assets" / "note.txt", "hi")
    return root


@pytest.fixture
def server(project: Path) -> Iterator[DevServer]:
    srv = DevServer(str(project), "app.main", host="127.0.0.1", port=0, watch=False, log=lambda _: None)
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


# ----------------------------------------------------------------------
# URLs
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("192.168.1.20", "ws://192.168.1.20:8765/ws?role=client"),
        ("192.168.1.20:9000", "ws://192.168.1.20:9000/ws?role=client"),
        ("http://mac.local:8765", "ws://mac.local:8765/ws?role=client"),
        ("http://mac.local:8765/", "ws://mac.local:8765/ws?role=client"),
        ("ws://10.0.2.2:8765/ws?role=client", "ws://10.0.2.2:8765/ws?role=client"),
        ("ws://10.0.2.2:8765/ws", "ws://10.0.2.2:8765/ws?role=client"),
        ("  localhost:8765  ", "ws://localhost:8765/ws?role=client"),
    ],
)
def test_normalize_server_url(typed: str, expected: str) -> None:
    assert devclient.normalize_server_url(typed) == expected


def test_normalize_server_url_rejects_empty() -> None:
    with pytest.raises(ValueError):
        devclient.normalize_server_url("   ")


def test_saved_server_url_round_trips_through_the_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    assert devclient.saved_server_url(str(overlay)) is None
    devclient._save_server_url(str(overlay), "ws://1.2.3.4:8765/ws?role=client")
    assert devclient.saved_server_url(str(overlay)) == "ws://1.2.3.4:8765/ws?role=client"
    (overlay / "server.json").write_text("not json", encoding="utf-8")
    assert devclient.saved_server_url(str(overlay)) is None


# ----------------------------------------------------------------------
# Sync
# ----------------------------------------------------------------------


def test_client_syncs_the_tree_into_the_overlay_and_reports_state(
    server: DevServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlay = tmp_path / "overlay"
    states: List[str] = []
    reloads: List[List[str]] = []
    monkeypatch.setattr(devclient.DevClient, "_schedule_reload", lambda self, modules, version: reloads.append(modules))
    client = devclient.DevClient(
        server.info.url("127.0.0.1"), str(overlay), entry_module="app.main", forward_logs=False, log=lambda _: None
    )
    client.add_listener(lambda state, detail: states.append(state))
    client.start()
    try:
        assert client.synced_once.wait(5.0)
        _wait(lambda: client.state == "connected")
        assert (overlay / "app" / "main.py").read_text(encoding="utf-8") == "VALUE = 1\n"
        assert (overlay / "app" / "assets" / "note.txt").read_text(encoding="utf-8") == "hi"
        assert client.synced_version == server.snapshot.version
        assert states[:3] == ["connecting", "connected", "syncing"]
        # The URL is remembered for --dev-client builds.
        assert devclient.saved_server_url(str(overlay)) == client.url
        # Everything was new to this overlay, so the synced modules are reloaded (a
        # --dev-client shell's placeholder entry is replaced the same way).
        _wait(lambda: len(reloads) == 1)
        assert reloads[0] == ["app", "app.main"]
        _wait(lambda: len(server.clients) == 1)
        assert server.clients[0].app == "app.main"
    finally:
        client.stop()
    assert client.state == "idle"


def test_client_hello_advertises_existing_overlay_so_only_changes_flow(server: DevServer, tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    # Pre-seed the overlay with the current main.py so the server has nothing new to send for it.
    _write(overlay / "app" / "main.py", "VALUE = 1\n")
    client = devclient.DevClient(server.info.url("127.0.0.1"), str(overlay), forward_logs=False, log=lambda _: None)
    manifest = client._overlay_manifest()
    assert set(manifest) == {"app/main.py"}
    assert manifest["app/main.py"] == server.snapshot.files["app/main.py"]


def test_first_hello_seeds_the_overlay_from_the_bundled_sources(
    server: DevServer, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build made from the server's sources connects without downloading or reloading anything."""
    bundle = tmp_path / "bundle"
    for rel in ("app/__init__.py", "app/main.py", "app/assets/note.txt"):
        _write(bundle / rel, (project / rel).read_text(encoding="utf-8"))
    _write(bundle / "app" / "__pycache__" / "main.cpython-313.pyc", "junk")
    monkeypatch.syspath_prepend(str(bundle))
    # Prepared the way the native templates do it: the overlay already contains an empty app/ dir.
    overlay = Path(configure_dev_environment(str(tmp_path / "data")))
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(overlay)])
    assert (overlay / "app").is_dir() and not any((overlay / "app").iterdir())
    reloads: List[List[str]] = []
    monkeypatch.setattr(devclient.DevClient, "_schedule_reload", lambda self, modules, version: reloads.append(modules))
    client = devclient.DevClient(
        server.info.url("127.0.0.1"), str(overlay), entry_module="app.main", forward_logs=False, log=lambda _: None
    )
    hello = client._hello()
    # Seeded from the bundle: the whole tree, minus caches, hashed like the server does.
    assert hello["files"] == server.snapshot.files
    assert not (overlay / "app" / "__pycache__").exists()
    client.start()
    try:
        assert client.synced_once.wait(5.0)
        _wait(lambda: client.state == "connected")
        # Nothing differed, so the first sync wrote nothing and reloaded nothing.
        time.sleep(0.2)
        assert reloads == []
    finally:
        client.stop()
    # Seeding happens once: an existing overlay is left alone even if the bundle changes.
    _write(bundle / "app" / "main.py", "VALUE = 2\n")
    assert client._hello()["files"]["app/main.py"] == server.snapshot.files["app/main.py"]


def test_bundled_package_root_ignores_the_overlay_and_does_not_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlay = tmp_path / "overlay"
    _write(overlay / "pkg_seed_test" / "__init__.py", "")
    bundle = tmp_path / "bundle"
    _write(bundle / "pkg_seed_test" / "__init__.py", "raise RuntimeError('must not be imported')\n")
    _write(bundle / "pkg_seed_test" / "sub" / "leaf.py", "")
    monkeypatch.syspath_prepend(str(bundle))
    monkeypatch.syspath_prepend(str(overlay))
    root = devclient._bundled_package_root("pkg_seed_test", exclude=str(overlay))
    assert root is not None and Path(str(root)) == bundle / "pkg_seed_test"
    assert sorted(child.name for child in root.iterdir()) == ["__init__.py", "sub"]
    assert "pkg_seed_test" not in sys.modules
    assert devclient._bundled_package_root("no_such_pkg_anywhere", exclude=str(overlay)) is None


def test_updates_are_applied_and_reloads_scheduled(
    server: DevServer, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlay = tmp_path / "overlay"
    reloads: List[List[str]] = []
    monkeypatch.setattr(devclient.DevClient, "_schedule_reload", lambda self, modules, version: reloads.append(modules))
    client = devclient.DevClient(server.info.url("127.0.0.1"), str(overlay), forward_logs=False, log=lambda _: None)
    client.start()
    try:
        assert client.synced_once.wait(5.0)
        _wait(lambda: len(server.clients) == 1)
        before = server.snapshot
        _write(project / "app" / "main.py", "VALUE = 2\n")
        _write(project / "app" / "screens.py", "X = 1\n")
        (project / "app" / "assets" / "note.txt").unlink()
        after = snapshot_sources(str(project), previous=before)
        server._on_files_changed(before.diff(after), after)
        _wait(lambda: len(reloads) >= 2)
        assert (overlay / "app" / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
        assert (overlay / "app" / "screens.py").exists()
        _wait(lambda: not (overlay / "app" / "assets" / "note.txt").exists())
        assert reloads[-1] == ["app.main", "app.screens"]
        assert client.synced_version == after.version
    finally:
        client.stop()


def test_client_refuses_paths_that_escape_the_overlay(tmp_path: Path) -> None:
    client = devclient.DevClient("ws://127.0.0.1:1/ws", str(tmp_path / "overlay"), forward_logs=False)
    client._handle(
        {
            "type": "update",
            "version": "v",
            "files": [
                {"path": "../evil.py", "content": "x", "encoding": "utf-8"},
                {"path": "app/ok.py", "content": "y", "encoding": "utf-8"},
            ],
            "removed": ["../../etc/passwd"],
        }
    )
    assert not (tmp_path / "evil.py").exists()
    assert (tmp_path / "overlay" / "app" / "ok.py").read_text(encoding="utf-8") == "y"


def test_client_retries_when_the_server_is_down(tmp_path: Path) -> None:
    logs: List[str] = []
    client = devclient.DevClient("ws://127.0.0.1:1/ws", str(tmp_path / "overlay"), forward_logs=False, log=logs.append)
    client.start()
    try:
        _wait(lambda: client.state == "disconnected")
        _wait(lambda: any("cannot reach" in line for line in logs))
    finally:
        client.stop()


def test_log_forwarding_tees_stdout_to_the_server(server: DevServer, tmp_path: Path, capsys: Any) -> None:
    client = devclient.DevClient(server.info.url("127.0.0.1"), str(tmp_path / "overlay"), forward_logs=True)
    logs: List[str] = []
    server.log = logs.append
    client.start()
    try:
        assert client.synced_once.wait(5.0)
        print("hello from the app")
        _wait(lambda: any("hello from the app" in line for line in logs))
    finally:
        client.stop()
    assert not isinstance(sys.stdout, devclient._Tee)
    captured = capsys.readouterr()
    assert "hello from the app" in captured.out  # still printed locally


# ----------------------------------------------------------------------
# Bootstrap wiring
# ----------------------------------------------------------------------


def test_start_if_configured_needs_an_overlay_and_a_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative import hot_reload

    monkeypatch.delenv(devclient.SERVER_URL_ENV, raising=False)
    monkeypatch.setattr(hot_reload, "overlay_root", lambda: None)
    assert devclient.start_if_configured() is None
    monkeypatch.setattr(hot_reload, "overlay_root", lambda: str(tmp_path))
    assert devclient.start_if_configured() is None  # overlay but no URL anywhere

    started: List[Any] = []

    def fake_start(url: str, root: str, **kw: Any) -> str:
        started.append((url, root, kw))
        return "client"

    monkeypatch.setattr(devclient, "start", fake_start)
    monkeypatch.setenv(devclient.SERVER_URL_ENV, "ws://10.0.2.2:8765/ws?role=client")
    monkeypatch.setenv("PN_ENTRY_MODULE", "app.entry")
    assert devclient.start_if_configured() == "client"
    assert started == [("ws://10.0.2.2:8765/ws?role=client", str(tmp_path), {"entry_module": "app.entry"})]


def test_start_if_configured_falls_back_to_the_saved_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative import hot_reload

    monkeypatch.delenv(devclient.SERVER_URL_ENV, raising=False)
    monkeypatch.delenv("PN_ENTRY_MODULE", raising=False)
    monkeypatch.setattr(hot_reload, "overlay_root", lambda: str(tmp_path))
    devclient._save_server_url(str(tmp_path), "ws://192.168.1.9:8765/ws?role=client")
    started: List[Any] = []

    def fake_start(url: str, root: str, **kw: Any) -> str:
        started.append(url)
        return "client"

    monkeypatch.setattr(devclient, "start", fake_start)
    assert devclient.start_if_configured() == "client"
    assert started == ["ws://192.168.1.9:8765/ws?role=client"]


def test_placeholder_main_source_exports_the_connect_screen() -> None:
    source = devclient.placeholder_main_source()
    namespace: dict = {}
    exec(compile(source, "main.py", "exec"), namespace)
    assert namespace["App"] is devclient.ConnectScreen
    assert namespace["__all__"] == ["App"]


def test_connect_screen_renders_without_a_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative.testing import render

    monkeypatch.setattr(devclient, "_current", None)
    result = render(devclient.ConnectScreen())
    try:
        text = result.text()
        assert "Dev server address" in text
        assert "idle" in text
        result.get_by_text("Connect")
    finally:
        result.unmount()


def test_overlay_manifest_skips_caches_and_the_saved_url(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    _write(overlay / "app" / "main.py", "x")
    _write(overlay / "app" / "__pycache__" / "main.pyc", "junk")
    _write(overlay / "server.json", json.dumps({"url": "ws://x"}))
    client = devclient.DevClient("ws://127.0.0.1:1/ws", str(overlay), forward_logs=False)
    assert set(client._overlay_manifest()) == {"app/main.py"}
    assert os.path.exists(overlay / "server.json")
