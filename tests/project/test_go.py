"""PythonNative Go: its project, release assets, downloads, and caching (RFC 0006)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, Iterator, List
from urllib.error import HTTPError

import pytest

from pythonnative.project import go


@pytest.fixture(autouse=True)
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "cache"
    monkeypatch.setenv("PN_CACHE_DIR", str(root))
    monkeypatch.delenv(go.BASE_URL_ENV, raising=False)
    monkeypatch.setattr(go, "framework_version", lambda: "1.2.3")
    yield root


def test_go_project_is_a_debug_app_with_every_builtin_permission(tmp_path: Path) -> None:
    config = go.go_config(tmp_path / "go")
    assert config.app_id == go.GO_APP_ID
    assert config.display_name == "PythonNative Go"
    assert config.orientation == "all"
    assert config.version == "1.2.3"
    resolved = config.resolved_permissions()
    assert "NSCameraUsageDescription" in resolved.ios_usage_descriptions
    assert "android.permission.CAMERA" in resolved.android_permissions
    main = (tmp_path / "go" / "app" / "main.py").read_text(encoding="utf-8")
    assert "from pythonnative.devclient import GoHome as App" in main


def test_go_project_carries_a_signing_team_for_device_builds(tmp_path: Path) -> None:
    config = go.go_config(tmp_path / "go", development_team="ABCDE12345")
    assert config.ios.development_team == "ABCDE12345"


def test_artifact_names_follow_the_release_convention() -> None:
    assert go.artifact_names("1.2.3") == {
        "ios": "pythonnative-go-1.2.3-ios-simulator.zip",
        "android": "pythonnative-go-1.2.3-android.apk",
        "sums": "pythonnative-go-1.2.3.sha256",
    }


def _fake_app(root: Path) -> Path:
    app = root / "PythonNativeGo.app"
    (app / "Frameworks" / "Python.framework" / "Versions" / "A").mkdir(parents=True)
    (app / "Frameworks" / "Python.framework" / "Versions" / "A" / "Python").write_bytes(b"binary")
    os.symlink("Versions/A/Python", app / "Frameworks" / "Python.framework" / "Python")
    (app / "Info.plist").write_bytes(b"plist")
    launcher = app / "PythonNativeGo"
    launcher.write_bytes(b"exe")
    launcher.chmod(0o755)
    return app


def _release(tmp_path: Path) -> Dict[str, bytes]:
    out = tmp_path / "dist"
    ios = go.package("ios", _fake_app(tmp_path / "build"), out, "1.2.3")
    apk = tmp_path / "go.apk"
    apk.write_bytes(b"apk bytes")
    android = go.package("android", apk, out, "1.2.3")
    sums = go.write_checksums([ios, android], out, "1.2.3")
    return {path.name: path.read_bytes() for path in (ios, android, sums)}


def _fetcher(files: Dict[str, bytes], calls: List[str]) -> go.Fetch:
    def fetch(url: str) -> bytes:
        calls.append(url)
        name = url.rsplit("/", 1)[-1]
        if name not in files:
            raise HTTPError(url, 404, "not found", {}, None)  # type: ignore[arg-type]
        return files[name]

    return fetch


def test_downloads_are_verified_and_unpacked_into_the_cache(tmp_path: Path) -> None:
    files = _release(tmp_path)
    calls: List[str] = []
    app = go.download("ios", "1.2.3", fetch=_fetcher(files, calls), log=lambda line: None)
    assert app is not None and app.name == "PythonNativeGo.app"
    assert calls[0].endswith("/v1.2.3/pythonnative-go-1.2.3.sha256")
    framework = app / "Frameworks" / "Python.framework" / "Python"
    assert framework.is_symlink() and framework.read_bytes() == b"binary"
    assert os.access(app / "PythonNativeGo", os.X_OK)
    apk = go.download("android", "1.2.3", fetch=_fetcher(files, []), log=lambda line: None)
    assert apk is not None and apk.read_bytes() == b"apk bytes"
    assert go.installed_artifact("android") == apk
    assert go.installed_artifact("ios") == app


def test_a_tampered_download_is_refused(tmp_path: Path) -> None:
    files = _release(tmp_path)
    files["pythonnative-go-1.2.3-android.apk"] = b"evil"
    with pytest.raises(go.GoError, match="SHA-256"):
        go.download("android", "1.2.3", fetch=_fetcher(files, []), log=lambda line: None)
    assert go.installed_artifact("android") is None


def test_missing_release_assets_return_none(tmp_path: Path) -> None:
    assert go.download("ios", "1.2.3", fetch=_fetcher({}, []), log=lambda line: None) is None


def test_mirrors_can_replace_the_release_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(go.BASE_URL_ENV, "https://mirror.example/go")
    calls: List[str] = []
    go.download("ios", "1.2.3", fetch=_fetcher({}, calls), log=lambda line: None)
    assert calls == ["https://mirror.example/go/pythonnative-go-1.2.3.sha256"]


def test_ensure_artifact_prefers_the_cache_then_downloads_then_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: List[str] = []

    def fake_build(platform: str, *, out_dir: Path, log: object = None, **kw: object) -> Path:
        built.append(platform)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / go.artifact_names("1.2.3")["android"]
        target.write_bytes(b"local")
        return target

    monkeypatch.setattr(go, "build", fake_build)
    artifact = go.ensure_artifact("android", fetch=_fetcher({}, []), log=lambda line: None)
    assert built == ["android"] and artifact.read_bytes() == b"local"
    assert go.ensure_artifact("android", fetch=_fetcher({}, []), log=lambda line: None) == artifact
    assert built == ["android"], "a cached artifact is reused"
    go.ensure_artifact("android", force_build=True, fetch=_fetcher({}, []), log=lambda line: None)
    assert built == ["android", "android"]


def test_unsafe_archives_are_refused(tmp_path: Path) -> None:
    import zipfile

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", b"x")
    with pytest.raises(go.GoError, match="unsafe path"):
        go._extract_app(archive, tmp_path / "out")


def test_checksum_file_matches_sha256sum(tmp_path: Path) -> None:
    asset = tmp_path / "pythonnative-go-1.2.3-android.apk"
    asset.write_bytes(b"abc")
    sums = go.write_checksums([asset], tmp_path, "1.2.3")
    assert sums.read_text() == f"{hashlib.sha256(b'abc').hexdigest()}  {asset.name}\n"


def test_short_versions_are_numeric() -> None:
    assert go._short_version("0.50.0.dev3") == "0.50.0"
    assert go._short_version("1.2") == "1.2.0"
