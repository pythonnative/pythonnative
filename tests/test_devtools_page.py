"""The DevTools page as ``pn start`` serves it: the page, its modules, and its socket."""

from __future__ import annotations

import http.client
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import pytest

from pythonnative.devserver import DevServer, auth, ws
from pythonnative.devserver.server import _STATIC_DIR


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def server(tmp_path: Path) -> Iterator[DevServer]:
    _write(tmp_path / "pythonnative.toml", '[app]\nid = "com.example.demo"\nname = "demo"\n')
    _write(tmp_path / "app" / "__init__.py", "")
    _write(tmp_path / "app" / "main.py", "import pythonnative as pn\n\nApp = None\n")
    srv = DevServer(
        str(tmp_path), "app.main", host="127.0.0.1", port=0, project_name="demo", log=lambda _: None, watch=False
    )
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _get(server: DevServer, path: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.info.port, timeout=5)
    try:
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        connection.close()


def _imports(source: str) -> List[str]:
    """Relative and absolute module specifiers in an ES module."""
    return re.findall(r"""^\s*import\s+(?:[^'"]*?\s+from\s+)?["']([^"']+)["']""", source, flags=re.MULTILINE)


def _resolve(base: str, spec: str) -> str:
    if spec.startswith("/"):
        return spec
    parts = base.rsplit("/", 1)[0].split("/")
    for piece in spec.split("/"):
        if piece == "..":
            parts.pop()
        elif piece != ".":
            parts.append(piece)
    return "/".join(parts)


class _Page:
    """A DevTools socket that buffers messages so tests can wait for one type."""

    def __init__(self, server: DevServer) -> None:
        url = auth.with_token(server.info.url("127.0.0.1").replace("http", "ws") + "/ws?role=devtools", server.token)
        self.client = ws.WebSocketClient(url, timeout=5.0)
        self.client.connect()
        self.seen: List[Dict[str, Any]] = []

    def send(self, message: Dict[str, Any]) -> None:
        self.client.send_text(json.dumps(message))

    def wait(self, kind: str, timeout: float = 5.0, **match: Any) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for message in self.seen:
                if message.get("type") == kind and all(message.get(k) == v for k, v in match.items()):
                    self.seen.remove(message)
                    return message
            text = self.client.recv()
            if text is None:
                break
            self.seen.append(json.loads(text))
        raise AssertionError(f"no {kind!r} message; saw {[m.get('type') for m in self.seen]}")

    def close(self) -> None:
        self.client.close()


# ----------------------------------------------------------------------
# The page and its assets
# ----------------------------------------------------------------------


def test_devtools_url_trades_the_token_for_a_cookie(server: DevServer) -> None:
    status, headers, _ = _get(server, f"/devtools?{auth.QUERY_PARAM}={server.token}")
    assert status == 302
    assert headers["location"] == "/devtools"
    assert headers["set-cookie"].startswith(f"{auth.COOKIE_NAME}={server.token}")
    assert "HttpOnly" in headers["set-cookie"]


def test_devtools_page_is_served(server: DevServer) -> None:
    status, headers, body = _get(server, "/devtools")
    assert status == 200
    assert headers["content-type"].startswith("text/html")
    html = body.decode("utf-8")
    assert "<title>PythonNative DevTools</title>" in html
    # The page lives at /devtools (no trailing slash), so its assets must be absolute.
    assert 'href="/devtools/devtools.css"' in html
    assert 'src="/devtools/devtools.js"' in html
    assert "http://" not in html.replace("http://www.w3.org", "") and "https://" not in html, "no external resources"


def test_every_devtools_module_resolves(server: DevServer) -> None:
    """Walk the import graph from the page's entry points; every module must load."""
    pending = ["/devtools/devtools.js", "/static/host.js", "/static/shell.js"]
    seen: Set[str] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        status, headers, body = _get(server, path)
        assert status == 200, f"{path} -> {status}"
        assert headers["content-type"].startswith("text/javascript"), path
        source = body.decode("utf-8")
        assert "https://" not in re.sub(r"//.*", "", source), f"{path} loads something from the network"
        pending.extend(_resolve(path, spec) for spec in _imports(source))
    expected = {
        "/devtools/connection.js",
        "/devtools/tree.js",
        "/devtools/report.js",
        "/devtools/panels/components.js",
        "/devtools/panels/console.js",
        "/devtools/panels/problems.js",
        "/devtools/panels/network.js",
        "/devtools/panels/performance.js",
        "/devtools/panels/connect.js",
        "/static/devsupport.js",
        "/static/devtools/report.js",
    }
    assert expected <= seen, expected - seen
    status, headers, _ = _get(server, "/devtools/devtools.css")
    assert status == 200 and headers["content-type"].startswith("text/css")


@pytest.mark.parametrize("path", ["/devtools/../server.py", "/devtools/.hidden", "/devtools/missing.js"])
def test_devtools_static_paths_stay_inside_the_folder(server: DevServer, path: str) -> None:
    assert _get(server, path)[0] == 404


def test_devtools_assets_are_packaged() -> None:
    static = Path(_STATIC_DIR) / "devtools"
    shipped = {str(p.relative_to(static)) for p in static.rglob("*") if p.is_file()}
    for name in ("index.html", "devtools.js", "devtools.css", "connection.js", "report.js", "panels/components.js"):
        assert name in shipped, f"{name} missing from {static}"


# ----------------------------------------------------------------------
# The DevTools socket
# ----------------------------------------------------------------------


def test_devtools_socket_needs_the_token(server: DevServer) -> None:
    url = server.info.url("127.0.0.1").replace("http", "ws") + "/ws?role=devtools"
    client = ws.WebSocketClient(url, timeout=5.0)
    with pytest.raises(Exception):
        client.connect()


def test_devtools_socket_gets_targets_history_and_events(server: DevServer) -> None:
    server.publish_local("preview", "log", {"level": "info", "text": "before the page"})
    page = _Page(server)
    try:
        targets = page.wait("targets")
        assert targets["targets"] == [] and targets["debug_target"] is None
        history = page.wait("history")
        assert isinstance(history["events"], list)
        server.publish_local("preview", "log", {"level": "warning", "text": "hello devtools"})
        event = page.wait("event")
        assert event["target"] == "preview" and event["topic"] == "log"
        assert event["data"] == {"level": "warning", "text": "hello devtools"}
        assert isinstance(event["time"], float)
    finally:
        page.close()


def test_devtools_socket_answers_connect_rpc_and_open(server: DevServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PN_EDITOR", "true")  # a no-op editor
    page = _Page(server)
    try:
        page.wait("history")
        page.send({"type": "connect"})
        connect = page.wait("connect")
        assert connect["project"] == "demo"
        assert connect["qr_svg"].startswith("<svg")
        assert {"server", "go", "go_compatible", "preferred"} <= set(connect["links"])
        assert "/devtools?token=" in connect["devtools"]

        page.send({"type": "rpc", "id": 7, "target": "nope", "method": "tree", "params": {}})
        result = page.wait("rpc_result", id=7)
        assert result["error"] and "result" not in result

        page.send({"type": "open", "file": "app/main.py", "line": 3})
        opened = page.wait("opened", file="app/main.py")
        assert opened["path"].endswith("app/main.py") and "error" not in opened
        page.send({"type": "open", "file": "/etc/hosts", "line": 1})
        refused = page.wait("opened", file="/etc/hosts")
        assert "error" in refused

        page.send({"type": "debug_target", "target": None})
        assert page.wait("targets")["debug_target"] is None
        page.send({"type": "clear", "target": None, "topic": "log"})
        page.send({"type": "command", "name": "reload", "target": None})
        # The socket stays up after fire-and-forget messages.
        page.send({"type": "connect"})
        page.wait("connect")
    finally:
        page.close()
