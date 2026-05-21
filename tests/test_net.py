"""Unit tests for pn.fetch (async HTTP client)."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Generator

import pytest

from pythonnative.net import HTTPError, Response, fetch

# ======================================================================
# Mini HTTP server fixture
# ======================================================================


class _EchoHandler(BaseHTTPRequestHandler):
    """Records every request and replies with metadata or canned content.

    Routes:
      - ``GET /text`` → ``"hello"`` with ``Content-Type: text/plain``.
      - ``GET /json`` → ``{"ok": True}``.
      - ``GET /status/<code>`` → empty body with that status code.
      - ``POST /echo`` → JSON object echoing method, path, body, headers.
    """

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Suppress per-request stderr noise.
        return

    def do_GET(self) -> None:
        if self.path == "/text":
            body = b"hello"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/json":
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/status/"):
            code = int(self.path.rsplit("/", 1)[-1])
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        path_only = self.path.split("?", 1)[0]
        if path_only != "/echo":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        payload = {
            "method": self.command,
            "path": self.path,
            "body": raw.decode("utf-8"),
            "headers": {k: v for k, v in self.headers.items()},
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def echo_server() -> Generator[str, None, None]:
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


# ======================================================================
# Tests
# ======================================================================


def test_get_text(echo_server: str) -> None:
    async def run() -> Response:
        return await fetch(echo_server + "/text")

    resp = asyncio.run(run())
    assert resp.status == 200
    assert resp.ok
    assert resp.text() == "hello"


def test_get_json(echo_server: str) -> None:
    async def run() -> Response:
        return await fetch(echo_server + "/json")

    resp = asyncio.run(run())
    assert resp.json() == {"ok": True}


def test_non_2xx_does_not_raise_but_keeps_body(echo_server: str) -> None:
    async def run() -> Response:
        return await fetch(echo_server + "/status/418")

    resp = asyncio.run(run())
    assert resp.status == 418
    assert resp.ok is False


def test_raise_for_status_on_4xx(echo_server: str) -> None:
    async def run() -> None:
        resp = await fetch(echo_server + "/status/404")
        resp.raise_for_status()

    with pytest.raises(HTTPError) as exc_info:
        asyncio.run(run())
    assert exc_info.value.status == 404


def test_post_dict_body_becomes_json(echo_server: str) -> None:
    async def run() -> dict:
        resp = await fetch(
            echo_server + "/echo",
            method="POST",
            body={"name": "Alice"},
        )
        return resp.json()

    body = asyncio.run(run())
    assert body["method"] == "POST"
    assert body["headers"].get("Content-Type") == "application/json"
    assert json.loads(body["body"]) == {"name": "Alice"}


def test_post_string_body(echo_server: str) -> None:
    async def run() -> dict:
        resp = await fetch(echo_server + "/echo", method="POST", body="raw")
        return resp.json()

    assert asyncio.run(run())["body"] == "raw"


def test_query_params_are_appended(echo_server: str) -> None:
    async def run() -> Response:
        return await fetch(
            echo_server + "/echo",
            method="POST",
            params={"q": "hi there", "limit": 5},
        )

    resp = asyncio.run(run())
    body = resp.json()
    # urlencode preserves order for sorted dicts; check both keys are present.
    assert "q=hi+there" in body["path"]
    assert "limit=5" in body["path"]


def test_unreachable_host_raises_oserror() -> None:
    # Bind to an ephemeral port then close it, guaranteeing nothing listens.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    async def run() -> Response:
        return await fetch(f"http://127.0.0.1:{port}/", timeout=2.0)

    with pytest.raises(OSError):
        asyncio.run(run())
