"""Dev session protocol v2: handshake, compatibility, packages, DevTools routing, tunnels (RFC 0006)."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import pytest

from pythonnative.devserver import DevServer, compat, ws
from pythonnative.devserver import packages as packages_mod
from pythonnative.devserver.compat import Incompatibility, ProjectRuntime
from pythonnative.devserver.hub import ClientTarget, DebugStream

TOKEN = "session-test-token"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _wait(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("timed out waiting for condition")


@pytest.fixture
def server(tmp_path: Path) -> Iterator[DevServer]:
    root = tmp_path / "proj"
    _write(root / "app" / "__init__.py", "")
    _write(root / "app" / "main.py", "VALUE = 1\n")
    srv = DevServer(str(root), "app.main", host="127.0.0.1", port=0, token=TOKEN, log=lambda line: None, watch=False)
    srv._runtime = ProjectRuntime(pythonnative=compat._framework_version(), protocol=_protocol())
    srv.start()
    yield srv
    srv.stop()


def _protocol() -> int:
    from pythonnative.bridge.commits import PROTOCOL_VERSION

    return PROTOCOL_VERSION


def _connect(server: DevServer, role: str = "client") -> ws.WebSocketClient:
    client = ws.WebSocketClient(f"ws://127.0.0.1:{server.info.port}/ws?role={role}&token={TOKEN}", timeout=5.0)
    client.connect()
    return client


def _hello(**overrides: Any) -> Dict[str, Any]:
    message: Dict[str, Any] = {
        "type": "hello",
        "session": 2,
        "client": "go",
        "platform": "ios",
        "device": "iPhone",
        "app": "app.main",
        "runtime": {"pythonnative": compat._framework_version(), "protocol": _protocol(), "plugins": []},
        "files": {},
        "packages": {},
    }
    message.update(overrides)
    return message


def _recv(client: ws.WebSocketClient, kind: str) -> Dict[str, Any]:
    while True:
        text = client.recv()
        assert text is not None, f"closed before a {kind!r} message"
        message = json.loads(text)
        if message.get("type") == kind:
            return dict(message)


# ======================================================================
# Compatibility rules
# ======================================================================


def _runtime(**overrides: Any) -> ProjectRuntime:
    return ProjectRuntime(**{"pythonnative": "1.0.0", "protocol": 6, **overrides})


def test_go_runs_projects_without_native_code() -> None:
    assert compat.check(_hello(runtime={"pythonnative": "1.0.0", "protocol": 6}), _runtime()) is None


@pytest.mark.parametrize(
    "hello, runtime, reason, fix",
    [
        (_hello(session=1), _runtime(), "older version", "pn go ios"),
        (_hello(runtime={"pythonnative": "0.9.0", "protocol": 6}), _runtime(), "Go 0.9.0", "pn go ios"),
        (_hello(runtime={"pythonnative": "1.0.0", "protocol": 6}), _runtime(plugins=["maps"]), "maps", "pn run ios"),
        (
            _hello(runtime={"pythonnative": "1.0.0", "protocol": 6}),
            _runtime(native_packages=["numpy"]),
            "numpy",
            "pn run ios",
        ),
        (
            _hello(client="app", platform="android", runtime={"pythonnative": "0.9.0", "protocol": 6}),
            _runtime(),
            "contains PythonNative 0.9.0",
            "pn run android --rebuild",
        ),
        (
            _hello(client="app", runtime={"pythonnative": "1.0.0", "protocol": 6, "plugins": ["old"]}),
            _runtime(plugins=["new"]),
            "added new; removed old",
            "--rebuild",
        ),
    ],
)
def test_incompatible_clients_get_a_reason_and_a_fix(
    hello: Dict[str, Any], runtime: ProjectRuntime, reason: str, fix: str
) -> None:
    problem = compat.check(hello, runtime)
    assert isinstance(problem, Incompatibility)
    assert reason in problem.reason
    assert fix in problem.fix
    assert problem.to_message()["type"] == "incompatible"


def test_app_clients_with_matching_plugins_are_compatible() -> None:
    hello = _hello(client="app", runtime={"pythonnative": "1.0.0", "protocol": 6, "plugins": ["maps"]})
    assert compat.check(hello, _runtime(plugins=["maps"])) is None


# ======================================================================
# Package resolution
# ======================================================================


def test_resolve_classifies_installed_distributions() -> None:
    distributions, missing = packages_mod.resolve(["pytest", "definitely-not-installed-pkg"])
    names = {packages_mod.normalize(dist.name) for dist in distributions}
    assert "pytest" in names and "pluggy" in names  # dependencies come along
    assert missing == ["definitely-not-installed-pkg"]
    pytest_dist = next(dist for dist in distributions if packages_mod.normalize(dist.name) == "pytest")
    assert pytest_dist.pure
    rels = [rel for rel, _path in pytest_dist.files]
    assert any(rel.endswith("METADATA") for rel in rels)
    assert not any(rel.endswith(".pyc") or "__pycache__" in rel for rel in rels)


def test_resolve_skips_bundled_distributions_and_pythonnative() -> None:
    distributions, _missing = packages_mod.resolve(["pytest", "pythonnative"], skip=["pytest"])
    names = {packages_mod.normalize(dist.name) for dist in distributions}
    assert "pytest" not in names and "pythonnative" not in names


def test_debugpy_syncs_its_sources_without_binaries() -> None:
    dist = packages_mod.find_distribution("debugpy")
    if dist is None:
        pytest.skip("debugpy isn't installed")
    sources = packages_mod.distribution_files(dist, sources_only=True)
    rels = [rel for rel, _path in sources.files]
    assert sources.pure
    assert not any(rel.endswith(packages_mod.BINARY_SUFFIXES) for rel in rels)
    assert not any("pydevd_attach_to_process" in rel for rel in rels)
    assert "debugpy/__init__.py" in rels


def test_requirement_names() -> None:
    assert packages_mod.requirement_name("httpx[http2]>=0.27") == "httpx"
    assert packages_mod.requirement_name("vendor/pkg-0.1.0-py3-none-any.whl") == "pkg"
    assert packages_mod.normalize("Foo_Bar.baz") == "foo-bar-baz"


# ======================================================================
# Handshake over the wire
# ======================================================================


def test_compatible_hello_gets_a_sync_with_the_project_name(server: DevServer) -> None:
    client = _connect(server)
    try:
        client.send_text(json.dumps(_hello()))
        sync = _recv(client, "sync")
        assert {entry["path"] for entry in sync["files"]} == {"app/__init__.py", "app/main.py"}
        assert "project" in sync
        _wait(lambda: len(server.hub.targets) == 1)
        target = next(iter(server.hub.targets.values()))
        assert target.kind == "go" and target.platform == "ios"
    finally:
        client.close()
    _wait(lambda: not server.hub.targets)


def test_incompatible_hello_gets_the_reason_instead_of_a_sync(server: DevServer) -> None:
    client = _connect(server)
    try:
        client.send_text(json.dumps(_hello(runtime={"pythonnative": "0.0.1", "protocol": 6})))
        message = _recv(client, "incompatible")
        assert "0.0.1" in message["reason"] and "pn go ios" in message["fix"]
        assert not server.hub.targets
    finally:
        client.close()


def test_devtools_pages_see_targets_events_and_rpc_results(server: DevServer) -> None:
    app = _connect(server)
    page = _connect(server, "devtools")
    try:
        assert _recv(page, "targets")["targets"] == []
        _recv(page, "history")
        app.send_text(json.dumps(_hello()))
        _recv(app, "sync")
        targets = _recv(page, "targets")["targets"]
        target_id = targets[0]["id"]
        assert targets[0]["label"] == "ios iPhone"

        app.send_text(json.dumps({"type": "event", "topic": "problem", "data": {"title": "boom"}}))
        event = _recv(page, "event")
        assert event["target"] == target_id and event["topic"] == "problem"

        app.send_text(json.dumps({"type": "log", "level": "info", "text": "hello"}))
        assert _recv(page, "event")["data"] == {"level": "info", "text": "hello"}

        page.send_text(json.dumps({"type": "rpc", "id": 7, "target": target_id, "method": "tree", "params": {}}))
        rpc = _recv(app, "rpc")
        assert rpc["method"] == "tree"
        app.send_text(json.dumps({"type": "rpc_result", "id": rpc["id"], "result": {"screens": []}}))
        assert _recv(page, "rpc_result") == {"type": "rpc_result", "id": 7, "result": {"screens": []}}

        page.send_text(json.dumps({"type": "rpc", "id": 8, "target": "missing", "method": "tree"}))
        assert "isn't connected" in _recv(page, "rpc_result")["error"]

        page.send_text(json.dumps({"type": "command", "name": "menu", "target": target_id}))
        assert _recv(app, "menu") == {"type": "menu"}
    finally:
        app.close()
        page.close()


def test_late_pages_receive_the_event_history(server: DevServer) -> None:
    app = _connect(server)
    try:
        app.send_text(json.dumps(_hello()))
        _recv(app, "sync")
        app.send_text(json.dumps({"type": "log", "level": "error", "text": "early"}))
        _wait(lambda: any(t.history["log"] for t in server.hub.targets.values()))
        page = _connect(server, "devtools")
        try:
            _recv(page, "targets")
            history = _recv(page, "history")["events"]
            assert history[-1]["data"]["text"] == "early"
        finally:
            page.close()
    finally:
        app.close()


def test_connect_document_offers_go_and_app_links(server: DevServer, monkeypatch: pytest.MonkeyPatch) -> None:
    class Config:
        app_id = "com.example.my_app"
        requirements: List[str] = []

    server.config = Config()
    links = server.connect_links("10.0.0.2")
    assert links["go"].startswith("pn-com.pythonnative.go://connect?url=http%3A%2F%2F10.0.0.2")
    assert links["app"].startswith("pn-com.example.my-app://connect?url=")
    assert links["preferred"] == links["go"]
    server._runtime = ProjectRuntime(pythonnative="1", protocol=6, plugins=["maps"])
    assert server.connect_links("10.0.0.2")["preferred"] == server.connect_links("10.0.0.2")["app"]


# ======================================================================
# Tunnels
# ======================================================================


def _echo_server() -> socket.socket:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def serve() -> None:
        connection, _ = listener.accept()
        while True:
            data = connection.recv(4096)
            if not data:
                break
            connection.sendall(data.upper())
        connection.close()

    threading.Thread(target=serve, daemon=True).start()
    return listener


def test_tunnels_carry_tcp_streams_through_a_dev_client(server: DevServer, tmp_path: Path) -> None:
    from pythonnative.devclient import DevClient

    echo = _echo_server()
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    client = DevClient(
        f"ws://127.0.0.1:{server.info.port}/ws?token={TOKEN}",
        str(overlay),
        forward_logs=False,
        agent=False,
        kind="app",
        log=lambda line: None,
    )
    server._runtime = ProjectRuntime(pythonnative=compat._framework_version(), protocol=_protocol())
    client.start()
    try:
        _wait(lambda: server.hub.targets and client.state == "connected")
        target = next(iter(server.hub.targets.values()))
        assert isinstance(target, ClientTarget)
        received: List[bytes] = []
        closed = threading.Event()
        stream = DebugStream(write=lambda data: None, close=lambda: None)
        stream.on_data = received.append
        stream.on_close = closed.set
        target._streams[99] = stream
        loop = server._loop
        assert loop is not None
        port = echo.getsockname()[1]
        import base64

        payload = base64.b64encode(b"hello tunnel").decode()
        # Data sent right behind the open (as a debugger's first request is)
        # waits for the device's local connection instead of being dropped.
        loop.call_soon_threadsafe(target._send, {"type": "tunnel", "stream": 99, "op": "open", "port": port})
        loop.call_soon_threadsafe(target._send, {"type": "tunnel", "stream": 99, "op": "data", "data": payload})
        _wait(lambda: b"".join(received) == b"HELLO TUNNEL")
        assert 99 in client._streams
        loop.call_soon_threadsafe(target._send, {"type": "tunnel", "stream": 99, "op": "close"})
        _wait(lambda: 99 not in client._streams)
    finally:
        client.stop()
        echo.close()


def test_rpc_without_an_agent_is_answered_with_an_error(server: DevServer, tmp_path: Path) -> None:
    from pythonnative.devclient import DevClient

    overlay = tmp_path / "overlay"
    overlay.mkdir()
    client = DevClient(
        f"ws://127.0.0.1:{server.info.port}/ws?token={TOKEN}",
        str(overlay),
        forward_logs=False,
        agent=False,
        log=lambda line: None,
    )
    client.start()
    try:
        _wait(lambda: bool(server.hub.targets))
        target = next(iter(server.hub.targets.values()))
        loop = server._loop
        assert loop is not None
        future = asyncio.run_coroutine_threadsafe(target.call("tree", timeout=5.0), loop)
        with pytest.raises(RuntimeError, match="aren't available"):
            future.result(timeout=10)
    finally:
        client.stop()


def test_packages_are_synced_into_the_overlay(
    server: DevServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pythonnative import devclient
    from pythonnative.devclient import DevClient

    # This process has everything installed; a device bundles only its build's wheels.
    monkeypatch.setattr(devclient, "_bundled_distributions", lambda overlay: {})

    class Config:
        app_id = "com.example.app"
        requirements = ["iniconfig"]

    if packages_mod.find_distribution("iniconfig") is None:
        pytest.skip("iniconfig isn't installed")
    server.config = Config()
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    client = DevClient(
        f"ws://127.0.0.1:{server.info.port}/ws?token={TOKEN}",
        str(overlay),
        forward_logs=False,
        agent=False,
        log=lambda line: None,
    )
    client.start()
    try:
        _wait(lambda: (overlay / "site-packages" / "iniconfig" / "__init__.py").exists(), timeout=10)
        manifest = json.loads((overlay / "site-packages" / ".pn-packages.json").read_text())
        assert "iniconfig" in manifest
        assert client._installed_packages()["iniconfig"] == manifest["iniconfig"]["version"]
    finally:
        client.stop()


def test_debug_connections_without_targets_are_closed(server: DevServer) -> None:
    hub = server.hub

    async def connect() -> Optional[bytes]:
        reader = asyncio.StreamReader()
        reader.feed_eof()

        class Writer:
            closed = False

            def close(self) -> None:
                self.closed = True

            def write(self, data: bytes) -> None:
                pass

        writer = Writer()
        await hub.debug_connection(reader, writer)  # type: ignore[arg-type]
        return b"closed" if writer.closed else None

    loop = server._loop
    assert loop is not None
    assert asyncio.run_coroutine_threadsafe(connect(), loop).result(timeout=5) == b"closed"
