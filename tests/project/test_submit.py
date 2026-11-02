"""Tests for ``pn submit`` and ``pn links``: requests, credentials, and failure messages."""

from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple

import pytest

from pythonnative.project import links, submit
from pythonnative.project.config import AppConfig


class _FakePlay(BaseHTTPRequestHandler):
    calls: List[Tuple[str, str, bytes, Dict[str, str]]] = []
    fail: Dict[str, int] = {}

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).calls.append((self.command, self.path, body, dict(self.headers.items())))
        status = next((code for part, code in self.fail.items() if part in self.path), 200)
        reply: Dict[str, Any] = {}
        if self.path == "/token":
            reply = {"access_token": "token-1"}
        elif self.path.endswith("/edits"):
            reply = {"id": "edit-1"}
        elif "/bundles" in self.path:
            reply = {"versionCode": 42}
        encoded = json.dumps(reply if status == 200 else {"error": "denied"}).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    do_POST = do_PUT = _handle

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def play() -> Generator[str, None, None]:
    _FakePlay.calls, _FakePlay.fail = [], {}
    server = HTTPServer(("127.0.0.1", 0), _FakePlay)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def service_account(tmp_path: Path, play: str) -> Path:
    key = tmp_path / "key.pem"
    subprocess.run(["openssl", "genrsa", "-out", str(key), "2048"], check=True, capture_output=True)
    path = tmp_path / "account.json"
    path.write_text(
        json.dumps({"client_email": "ci@example.iam", "private_key": key.read_text(), "token_uri": f"{play}/token"})
    )
    return path


def test_play_upload_runs_one_edit_in_order(tmp_path: Path, service_account: Path, play: str) -> None:
    bundle = tmp_path / "app-release.aab"
    bundle.write_bytes(b"bundle bytes")
    version = submit.submit_android(
        bundle,
        package="com.example.demo",
        track="internal",
        environ={"PN_PLAY_SERVICE_ACCOUNT": str(service_account)},
        api_root=play,
        log=lambda _: None,
    )
    assert version == 42
    calls = _FakePlay.calls
    root = "/androidpublisher/v3/applications/com.example.demo/edits"
    assert [(method, path.split("?")[0]) for method, path, _, _ in calls] == [
        ("POST", "/token"),
        ("POST", root),
        ("POST", f"/upload{root}/edit-1/bundles"),
        ("PUT", f"{root}/edit-1/tracks/internal"),
        ("POST", f"{root}/edit-1:commit"),
    ]
    # The token request carries a three-part JWT; every later call carries the token.
    assert calls[0][2].count(b".") >= 2
    assert all(headers["Authorization"] == "Bearer token-1" for _, _, _, headers in calls[1:])
    assert calls[2][2] == b"bundle bytes"
    release = json.loads(calls[3][2])
    assert release == {"track": "internal", "releases": [{"status": "completed", "versionCodes": ["42"]}]}


def test_play_draft_releases(tmp_path: Path, service_account: Path, play: str) -> None:
    bundle = tmp_path / "app-release.aab"
    bundle.write_bytes(b"x")
    submit.submit_android(
        bundle,
        package="p",
        track="beta",
        draft=True,
        environ={"PN_PLAY_SERVICE_ACCOUNT": str(service_account)},
        api_root=play,
        log=lambda _: None,
    )
    assert json.loads(_FakePlay.calls[3][2])["releases"][0]["status"] == "draft"


def test_play_failures_explain_themselves(tmp_path: Path, service_account: Path, play: str) -> None:
    bundle = tmp_path / "app-release.aab"
    bundle.write_bytes(b"x")
    _FakePlay.fail = {"/bundles": 403}
    with pytest.raises(submit.SubmitError, match="HTTP 403.*denied"):
        submit.submit_android(
            bundle,
            package="p",
            environ={"PN_PLAY_SERVICE_ACCOUNT": str(service_account)},
            api_root=play,
            log=lambda _: None,
        )
    assert not any(":commit" in path for _, path, _, _ in _FakePlay.calls)


def test_android_credentials_and_track_are_checked(tmp_path: Path) -> None:
    bundle = tmp_path / "a.aab"
    with pytest.raises(submit.SubmitError, match="PN_PLAY_SERVICE_ACCOUNT"):
        submit.submit_android(bundle, package="p", environ={})
    with pytest.raises(submit.SubmitError, match="Unknown track"):
        submit.submit_android(bundle, package="p", track="canary", environ={})
    with pytest.raises(submit.SubmitError, match="Couldn't read"):
        submit.submit_android(bundle, package="p", environ={"PN_PLAY_SERVICE_ACCOUNT": str(tmp_path / "none.json")})
    bad = tmp_path / "bad.json"
    bad.write_text('{"client_email": "x"}')
    with pytest.raises(submit.SubmitError, match="missing private_key"):
        submit.submit_android(bundle, package="p", environ={"PN_PLAY_SERVICE_ACCOUNT": str(bad)})


def test_ios_upload_passes_the_key_to_altool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key = tmp_path / "AuthKey.p8"
    key.write_text("key")
    package = tmp_path / "App.ipa"
    package.write_bytes(b"ipa")
    seen: Dict[str, Any] = {}

    def fake_run(command: List[str], *, env: Dict[str, str], **_: Any) -> Any:
        seen["command"] = command
        seen["copied"] = (Path(env["API_PRIVATE_KEYS_DIR"]) / "AuthKey_KEY1.p8").read_text()
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    environ = {"PN_ASC_KEY_PATH": str(key), "PN_ASC_KEY_ID": "KEY1", "PN_ASC_ISSUER_ID": "ISSUER"}
    submit.submit_ios(package, environ=environ, log=lambda _: None)
    assert seen["command"][:3] == ["xcrun", "altool", "--upload-app"]
    assert "--apiKey" in seen["command"] and "KEY1" in seen["command"] and "ISSUER" in seen["command"]
    assert seen["copied"] == "key"


def test_ios_failures_and_missing_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(submit.SubmitError, match="PN_ASC_KEY_PATH, PN_ASC_KEY_ID"):
        submit.submit_ios(tmp_path / "a.ipa", environ={})
    environ = {"PN_ASC_KEY_PATH": str(tmp_path / "none"), "PN_ASC_KEY_ID": "K", "PN_ASC_ISSUER_ID": "I"}
    with pytest.raises(submit.SubmitError, match="doesn't exist"):
        submit.submit_ios(tmp_path / "a.ipa", environ=environ)
    key = tmp_path / "k.p8"
    key.write_text("k")
    environ["PN_ASC_KEY_PATH"] = str(key)
    monkeypatch.setattr(
        subprocess, "run", lambda command, **_: subprocess.CompletedProcess(command, 1, "stdout", "bad build")
    )
    with pytest.raises(submit.SubmitError, match=r"altool failed[\s\S]*bad build"):
        submit.submit_ios(tmp_path / "a.ipa", environ=environ, log=lambda _: None)


def test_finding_artifacts(tmp_path: Path) -> None:
    with pytest.raises(submit.SubmitError, match="Run 'pn build ios'"):
        submit.find_ios_package(tmp_path)
    with pytest.raises(submit.SubmitError, match="Run 'pn build android'"):
        submit.find_android_bundle(tmp_path)
    ipa = tmp_path / "ios" / "export" / "App.ipa"
    ipa.parent.mkdir(parents=True)
    ipa.write_bytes(b"")
    aab = tmp_path / "android" / "outputs" / "app-release.aab"
    aab.parent.mkdir(parents=True)
    aab.write_bytes(b"")
    assert submit.find_ios_package(tmp_path) == ipa
    assert submit.find_android_bundle(tmp_path) == aab


def _config(tmp_path: Path, **app: Any) -> AppConfig:
    section = {"id": "com.example.demo", "name": "demo", "display_name": "Demo", **app}
    return AppConfig.from_dict({"app": section, "ios": {"development_team": "TEAM1"}}, project_root=tmp_path)


def test_links_render_both_files(tmp_path: Path) -> None:
    text = links.render(_config(tmp_path, associated_domains=["example.com"]))
    assert "/.well-known/apple-app-site-association" in text
    assert "TEAM1.com.example.demo" in text
    assert "/.well-known/assetlinks.json" in text
    assert "YOUR_SIGNING_CERTIFICATE_SHA256" in text and "Setup > App signing" in text
    assert "YOUR_TEAM_ID" not in text


def test_links_without_domains_say_how_to_add_them(tmp_path: Path) -> None:
    assert "associated_domains" in links.render(_config(tmp_path))
