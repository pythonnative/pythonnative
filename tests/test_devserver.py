"""The dev server: HTTP endpoints, the dev-client protocol, and the preview channel."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest

from pythonnative.devserver import DevServer, ws
from pythonnative.devserver.watcher import modules_for_paths, snapshot_sources


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    _write(tmp_path / "pythonnative.toml", '[app]\nid = "com.example.demo"\nname = "demo"\n')
    _write(tmp_path / "app" / "__init__.py", "")
    _write(tmp_path / "app" / "main.py", "import pythonnative as pn\n\nApp = None\n")
    _write(tmp_path / "app" / "assets" / "logo.txt", "not really an image")
    _write(tmp_path / "app" / "__pycache__" / "main.cpython-313.pyc", "junk")
    _write(tmp_path / "app" / ".DS_Store", "junk")
    return tmp_path


@pytest.fixture
def server(tmp_path: Path) -> Iterator[DevServer]:
    root = _project(tmp_path)
    logs: List[str] = []
    srv = DevServer(str(root), "app.main", host="127.0.0.1", port=0, project_name="demo", log=logs.append, watch=False)
    srv.start()
    srv.test_logs = logs  # type: ignore[attr-defined]
    try:
        yield srv
    finally:
        srv.stop()


def _get(server: DevServer, path: str) -> Any:
    with urllib.request.urlopen(server.info.url("127.0.0.1") + path, timeout=5) as response:
        body = response.read()
        ctype = response.headers.get("Content-Type", "")
        return (response.status, ctype, body)


def _wait(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


# ----------------------------------------------------------------------
# Snapshots
# ----------------------------------------------------------------------


def test_snapshot_skips_caches_and_editor_junk(tmp_path: Path) -> None:
    snap = snapshot_sources(str(_project(tmp_path)))
    assert set(snap.files) == {"app/__init__.py", "app/main.py", "app/assets/logo.txt"}
    assert all(len(digest) == 64 for digest in snap.files.values())
    assert len(snap.version) == 16


def test_snapshot_version_changes_with_content_and_diff_reports_paths(tmp_path: Path) -> None:
    root = _project(tmp_path)
    before = snapshot_sources(str(root))
    _write(root / "app" / "main.py", "changed = True\n")
    (root / "app" / "assets" / "logo.txt").unlink()
    _write(root / "app" / "new.py", "x = 1\n")
    after = snapshot_sources(str(root), previous=before)
    assert after.version != before.version
    change = before.diff(after)
    assert change.changed == ["app/main.py", "app/new.py"]
    assert change.removed == ["app/assets/logo.txt"]


def test_preview_page_assets_are_packaged() -> None:
    """The page only works from an installed wheel if setuptools ships ``devserver/static``."""
    import tomllib

    import pythonnative.devserver.server as server_mod

    static_dir = Path(server_mod._STATIC_DIR)
    shipped = {p.name for p in static_dir.iterdir() if p.is_file()}
    for name in ("index.html", "shell.js", "renderer.js", "bridge.js", "host.js", "colors.js", "preview.css"):
        assert name in shipped, f"{name} missing from {static_dir}"
    # Every asset the page loads has to be in the wheel; the glob in pyproject covers the directory.
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        package_data = tomllib.load(handle)["tool"]["setuptools"]["package-data"]["pythonnative"]
    assert any(pattern.startswith("devserver/static/") for pattern in package_data), package_data


def test_modules_for_paths_maps_python_files_only() -> None:
    assert modules_for_paths(["app/main.py", "app/screens/__init__.py", "app/assets/logo.png", "app/x/y.py"]) == [
        "app.main",
        "app.screens",
        "app.x.y",
    ]


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------


def test_http_serves_page_static_manifest_and_files(server: DevServer) -> None:
    status, ctype, body = _get(server, "/")
    assert status == 200 and "text/html" in ctype and b'<script type="module"' in body

    status, ctype, body = _get(server, "/static/shell.js")
    assert status == 200 and "javascript" in ctype and b"PreviewHost" in body

    status, _, body = _get(server, "/manifest")
    manifest = json.loads(body)
    assert manifest["entry"] == "app.main"
    assert set(manifest["files"]) == {"app/__init__.py", "app/main.py", "app/assets/logo.txt"}
    assert manifest["version"] == server.snapshot.version

    status, _, body = _get(server, "/file/app/main.py")
    assert status == 200 and body == b"import pythonnative as pn\n\nApp = None\n"

    status, _, body = _get(server, "/status")
    info = json.loads(body)
    assert info["name"] == "demo" and info["clients"] == [] and info["preview_connected"] is False


@pytest.mark.parametrize("path", ["/file/../pythonnative.toml", "/file/pythonnative.toml", "/static/../server.py"])
def test_http_refuses_paths_outside_the_synced_tree(server: DevServer, path: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(server, path)
    assert excinfo.value.code in (403, 404)


def test_http_404_for_unknown_routes(server: DevServer) -> None:
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(server, "/nope")
    assert excinfo.value.code == 404


# ----------------------------------------------------------------------
# Dev-client protocol
# ----------------------------------------------------------------------


def _client(server: DevServer, role: str = "client") -> ws.WebSocketClient:
    client = ws.WebSocketClient(server.info.url("127.0.0.1").replace("http", "ws") + f"/ws?role={role}", timeout=5.0)
    client.connect()
    return client


def test_client_hello_gets_only_the_files_it_lacks(server: DevServer) -> None:
    snap = server.snapshot
    client = _client(server)
    try:
        client.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "platform": "ios",
                    "device": "iPhone 15",
                    "app": "app.main",
                    "files": {"app/__init__.py": snap.files["app/__init__.py"], "app/stale.py": "0" * 64},
                }
            )
        )
        message = json.loads(client.recv() or "{}")
        assert message["type"] == "sync"
        assert message["version"] == snap.version
        assert sorted(f["path"] for f in message["files"]) == ["app/assets/logo.txt", "app/main.py"]
        assert message["removed"] == ["app/stale.py"]
        main = next(f for f in message["files"] if f["path"] == "app/main.py")
        assert main["sha256"] == snap.files["app/main.py"]
        assert main["content"] == "import pythonnative as pn\n\nApp = None\n"
        _wait(lambda: any(c.platform == "ios" for c in server.clients))
        assert server.clients[0].device == "iPhone 15"
    finally:
        client.close()
    _wait(lambda: not server.clients)


def test_client_logs_and_errors_reach_the_terminal(server: DevServer) -> None:
    logs: List[str] = server.test_logs  # type: ignore[attr-defined]
    client = _client(server)
    try:
        client.send_text(json.dumps({"type": "hello", "platform": "android", "device": "Pixel", "files": {}}))
        client.recv()  # sync
        client.send_text(json.dumps({"type": "log", "level": "info", "text": "hello from device\nsecond line"}))
        client.send_text(json.dumps({"type": "error", "phase": "render", "text": "Traceback...\nValueError: boom"}))
        client.send_text(json.dumps({"type": "reloaded", "mode": "fast_refresh", "modules": ["app.main"]}))
        _wait(lambda: any("fast_refresh: app.main" in line for line in logs))
    finally:
        client.close()
    assert "[android Pixel] hello from device" in logs
    assert "[android Pixel] second line" in logs
    assert "[android Pixel] error during render:" in logs
    assert "    ValueError: boom" in logs


def test_file_change_is_broadcast_to_connected_clients(server: DevServer) -> None:
    root = Path(server.project_root)
    client = _client(server)
    try:
        client.send_text(json.dumps({"type": "hello", "platform": "ios", "files": {}}))
        client.recv()
        _wait(lambda: len(server.clients) == 1)
        seen: List[Any] = []
        server.add_change_listener(lambda change, snap: seen.append(change))
        before = server.snapshot
        _write(root / "app" / "main.py", "App = 'changed'\n")
        after = snapshot_sources(str(root), previous=before)
        server._on_files_changed(before.diff(after), after)
        update = json.loads(client.recv() or "{}")
        assert update["type"] == "update"
        assert [f["path"] for f in update["files"]] == ["app/main.py"]
        assert update["files"][0]["content"] == "App = 'changed'\n"
        assert seen and seen[0].changed == ["app/main.py"]
        assert server.snapshot.version == after.version
    finally:
        client.close()


def test_binary_files_are_base64_encoded(server: DevServer) -> None:
    root = Path(server.project_root)
    (root / "app" / "assets" / "blob.bin").write_bytes(bytes(range(256)))
    before = server.snapshot
    after = snapshot_sources(str(root), previous=before)
    client = _client(server)
    try:
        client.send_text(json.dumps({"type": "hello", "platform": "ios", "files": {}}))
        client.recv()
        _wait(lambda: len(server.clients) == 1)
        server._on_files_changed(before.diff(after), after)
        update = json.loads(client.recv() or "{}")
        entry = update["files"][0]
        assert entry["path"] == "app/assets/blob.bin"
        assert entry["encoding"] == "base64"
        import base64

        assert base64.b64decode(entry["content"]) == bytes(range(256))
    finally:
        client.close()


# ----------------------------------------------------------------------
# Preview channel
# ----------------------------------------------------------------------


class _RecordingChannel:
    def __init__(self) -> None:
        self.connected: List[Dict[str, Any]] = []
        self.messages: List[str] = []
        self.disconnected = threading.Event()
        self.peer: Any = None
        self.got_message = threading.Event()

    def on_preview_connected(self, peer: Any, info: Dict[str, Any]) -> None:
        self.peer = peer
        self.connected.append(info)

    def on_preview_message(self, peer: Any, text: str) -> None:
        self.messages.append(text)
        self.got_message.set()
        peer.send(json.dumps(["res", 1, "pong"]))

    def on_preview_disconnected(self, peer: Any) -> None:
        self.disconnected.set()


def test_preview_socket_is_refused_when_no_preview_is_running(server: DevServer) -> None:
    client = _client(server, role="preview")
    try:
        assert client.recv() is None  # server closed the socket
    finally:
        client.close()


def test_preview_channel_relays_frames_both_ways_and_supersedes_older_pages(server: DevServer) -> None:
    channel = _RecordingChannel()
    server.set_preview_channel(channel)
    first = _client(server, role="preview")
    try:
        _wait(lambda: channel.peer is not None)
        first.send_text(json.dumps(["cb", "event", 7, "on_press", "[]"]))
        assert channel.got_message.wait(5.0)
        assert json.loads(channel.messages[0]) == ["cb", "event", 7, "on_press", "[]"]
        assert json.loads(first.recv() or "null") == ["res", 1, "pong"]
        _wait(lambda: json.loads(_get(server, "/status")[2])["preview_connected"])

        second = _client(server, role="preview")
        try:
            # The old page is told it lost control and gets closed.
            superseded = json.loads(first.recv() or "null")
            assert superseded == ["dev", {"type": "superseded"}]
            assert first.recv() is None
            _wait(lambda: len(channel.connected) == 2)
        finally:
            second.close()
        assert channel.disconnected.wait(5.0)
    finally:
        first.close()


def test_lan_addresses_never_include_loopback() -> None:
    from pythonnative.devserver import lan_addresses

    for address in lan_addresses():
        assert not address.startswith("127.")


def test_start_twice_is_idempotent_and_port_conflicts_raise(server: DevServer) -> None:
    assert server.start() is server.info
    other = DevServer(server.project_root, host="127.0.0.1", port=server.info.port, watch=False, log=lambda _: None)
    with pytest.raises(OSError):
        other.start()


def test_stop_without_start_is_safe(tmp_path: Path) -> None:
    srv = DevServer(str(_project(tmp_path)), watch=False, log=lambda _: None)
    srv.stop()
    assert os.path.isdir(srv.project_root)
