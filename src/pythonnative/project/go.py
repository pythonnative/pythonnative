"""PythonNative Go: the prebuilt, project-independent dev client.

Go is an ordinary debug build of a fixed project: its ``app/main.py`` is
the [home screen][pythonnative.devclient.GoHome], its identity is
``com.pythonnative.go``, and it declares every permission the built-in
modules use, so a project's camera, location, and notification code works
in it. Any project that adds no native code runs in it: the dev server
syncs the project's sources and pure-Python packages.

Artifacts for each release are attached to the GitHub release by
``scripts/build-go.py`` and cached per version under the shared cache
(``~/Library/Caches/pythonnative/go/<version>/``):

- ``pythonnative-go-<version>-ios-simulator.zip`` (the ``.app``)
- ``pythonnative-go-<version>-android.apk``
- ``pythonnative-go-<version>.sha256`` (``sha256sum`` format)

[`ensure_artifact`][pythonnative.project.go.ensure_artifact] finds the
artifact for the running ``pythonnative`` version in the cache, downloads
and verifies it, or builds it locally (a development checkout, offline,
or ``--build``).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AppConfig, render_default_toml
from .runtime_assets import default_cache_dir

__all__ = [
    "GO_APP_ID",
    "GO_DISPLAY_NAME",
    "GoError",
    "artifact_names",
    "build",
    "cache_dir",
    "download",
    "ensure_artifact",
    "go_config",
    "package",
]

GO_APP_ID = "com.pythonnative.go"
GO_DISPLAY_NAME = "PythonNative Go"
RELEASE_BASE_URL = "https://github.com/pythonnative/pythonnative/releases/download/v{version}"
BASE_URL_ENV = "PN_GO_BASE_URL"
"""Overrides where release assets are downloaded from (a mirror, or a test server)."""

_GO_PERMISSIONS = {
    "camera": "Lets the app you're developing use the camera.",
    "microphone": "Lets the app you're developing record audio.",
    "photo_library": "Lets the app you're developing read your photos.",
    "photo_library_add": "Lets the app you're developing save photos.",
    "location_when_in_use": "Lets the app you're developing use your location.",
    "face_id": "Lets the app you're developing authenticate with Face ID.",
    "motion": "Lets the app you're developing read motion data.",
    "notifications": True,
    "vibration": True,
}

Logger = Callable[[str], None]
Fetch = Callable[[str], bytes]


class GoError(RuntimeError):
    """PythonNative Go couldn't be found, downloaded, or built."""


def framework_version() -> str:
    """The running ``pythonnative`` version (Go must match it exactly)."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("pythonnative")
    except PackageNotFoundError:
        from .. import __version__

        return __version__


def artifact_names(version: str) -> Dict[str, str]:
    """Release asset names for ``version``: ``{"ios", "android", "sums"}``."""
    return {
        "ios": f"pythonnative-go-{version}-ios-simulator.zip",
        "android": f"pythonnative-go-{version}-android.apk",
        "sums": f"pythonnative-go-{version}.sha256",
    }


def cache_dir(version: Optional[str] = None) -> Path:
    """Where Go artifacts for ``version`` (default: the running one) are cached."""
    return default_cache_dir() / "go" / (version or framework_version())


def installed_artifact(platform: str, version: Optional[str] = None) -> Optional[Path]:
    """The cached, ready-to-install artifact (an ``.app`` directory or an ``.apk``), if any."""
    root = cache_dir(version)
    if platform == "ios":
        app = root / "ios" / f"{GO_DISPLAY_NAME.replace(' ', '')}.app"
        candidates = sorted((root / "ios").glob("*.app")) if (root / "ios").is_dir() else []
        if app.is_dir():
            return app
        return candidates[0] if candidates else None
    apk = root / "android" / artifact_names(version or framework_version())["android"]
    return apk if apk.is_file() else None


# ======================================================================
# Project
# ======================================================================


def go_config(work_dir: Path, *, development_team: Optional[str] = None) -> AppConfig:
    """Write Go's project into ``work_dir`` and load its config.

    Args:
        work_dir: An empty or reusable directory; ``app/main.py`` and
            ``pythonnative.toml`` are (re)written there.
        development_team: An Apple team id, for a build signed for
            physical iPhones.
    """
    from ..devclient import go_main_source
    from ..project.config import DEFAULT_PYTHON_VERSION

    work_dir.mkdir(parents=True, exist_ok=True)
    app_dir = work_dir / "app"
    app_dir.mkdir(exist_ok=True)
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "main.py").write_text(go_main_source(), encoding="utf-8")
    toml = render_default_toml(name="pythonnative_go", app_id=GO_APP_ID, python_version=DEFAULT_PYTHON_VERSION)
    toml = toml.replace('display_name = "Pythonnative Go"', f'display_name = "{GO_DISPLAY_NAME}"')
    toml = toml.replace('version = "1.0.0"', f'version = "{_short_version(framework_version())}"')
    toml = toml.replace('orientation = "portrait"        # portrait | landscape | all', 'orientation = "all"')
    permissions = "\n".join(
        f"{key} = {'true' if value is True else json.dumps(value)}" for key, value in _GO_PERMISSIONS.items()
    )
    toml = toml.replace("[permissions]\n", f"[permissions]\n{permissions}\n", 1)
    if development_team:
        toml = toml.replace('# development_team = "ABCDE12345"', f'development_team = "{development_team}"')
    (work_dir / "pythonnative.toml").write_text(toml, encoding="utf-8")
    return AppConfig.load(work_dir)


def _short_version(version: str) -> str:
    """``0.50.0.dev3`` becomes ``0.50.0`` (store version strings are numeric)."""
    parts = []
    for part in version.split(".")[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(digits or "0")
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts)


def build(
    platform: str,
    *,
    out_dir: Path,
    log: Optional[Logger] = None,
    device: bool = False,
    development_team: Optional[str] = None,
) -> Path:
    """Build Go for ``platform`` and copy the artifact into ``out_dir``.

    Args:
        platform: ``"ios"`` or ``"android"``.
        out_dir: Where the ``.app`` or ``.apk`` lands.
        log: Progress logger.
        device: Build for physical iPhones (needs ``development_team``).
        development_team: The Apple team that signs a device build.

    Returns:
        The artifact in ``out_dir``.
    """
    from .builder import Builder, BuildError

    emit = log or print
    work = default_cache_dir() / "go" / "project"
    config = go_config(work, development_team=development_team)
    builder = Builder(config, log=emit)
    try:
        if platform == "android":
            prepared = builder.prepare("android", dev_client="go")
            builder.build_android(prepared, debug=True)
            apk = builder.android_debug_apk(prepared)
            if apk is None or not apk.is_file():
                raise GoError("Gradle finished without a debug APK.")
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / artifact_names(framework_version())["android"]
            shutil.copy2(apk, target)
            return target
        sdk = "iphoneos" if device else "iphonesimulator"
        prepared = builder.prepare("ios", ios_sdks=(sdk,), dev_client="go")
        app = builder.build_ios_device(prepared) if device else builder.build_ios_simulator(prepared)
    except BuildError as exc:
        raise GoError(str(exc)) from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{GO_DISPLAY_NAME.replace(' ', '')}.app"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(app, target, symlinks=True)
    return target


def package(platform: str, artifact: Path, out_dir: Path, version: Optional[str] = None) -> Path:
    """Turn a built artifact into its release asset in ``out_dir``."""
    names = artifact_names(version or framework_version())
    out_dir.mkdir(parents=True, exist_ok=True)
    if platform == "android":
        target = out_dir / names["android"]
        if artifact.resolve() != target.resolve():
            shutil.copy2(artifact, target)
        return target
    target = out_dir / names["ios"]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(artifact.rglob("*")):
            rel = Path(artifact.name) / path.relative_to(artifact)
            if path.is_symlink():
                info = zipfile.ZipInfo(str(rel))
                info.external_attr = (0o120777 << 16) | 0x20
                archive.writestr(info, os.readlink(path))
            elif path.is_file():
                archive.write(path, rel)
    return target


def write_checksums(paths: list[Path], out_dir: Path, version: Optional[str] = None) -> Path:
    """Write ``pythonnative-go-<version>.sha256`` for ``paths`` (``sha256sum`` format)."""
    lines = [f"{_sha256(path)}  {path.name}" for path in sorted(paths, key=lambda p: p.name)]
    target = out_dir / artifact_names(version or framework_version())["sums"]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ======================================================================
# Download
# ======================================================================


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "pythonnative-cli"})
    with urlopen(request, timeout=60) as response:
        return bytes(response.read())


def download(
    platform: str,
    version: Optional[str] = None,
    *,
    fetch: Fetch = _fetch,
    log: Optional[Logger] = None,
) -> Optional[Path]:
    """Download and verify the release artifact into the cache.

    Returns:
        The installed artifact, or ``None`` when the release has no Go
        assets (or the network is unavailable).

    Raises:
        GoError: When a download doesn't match its published checksum.
    """
    emit = log or print
    version = version or framework_version()
    names = artifact_names(version)
    base = os.environ.get(BASE_URL_ENV) or RELEASE_BASE_URL.format(version=version)
    try:
        sums = fetch(f"{base}/{names['sums']}").decode("utf-8")
    except (HTTPError, URLError, OSError, ValueError):
        return None
    expected = {}
    for line in sums.splitlines():
        digest, _, name = line.strip().partition("  ")
        if digest and name:
            expected[name.strip()] = digest.strip()
    name = names[platform]
    if name not in expected:
        return None
    emit(f"Downloading {GO_DISPLAY_NAME} {version} for {platform}...")
    try:
        data = fetch(f"{base}/{name}")
    except (HTTPError, URLError, OSError) as exc:
        emit(f"Couldn't download {name}: {exc}")
        return None
    if hashlib.sha256(data).hexdigest() != expected[name]:
        raise GoError(f"{name} doesn't match its published SHA-256; refusing to install it.")
    root = cache_dir(version) / platform
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    if platform == "android":
        target = root / name
        target.write_bytes(data)
        return target
    with tempfile.TemporaryDirectory() as scratch:
        archive_path = Path(scratch) / name
        archive_path.write_bytes(data)
        _extract_app(archive_path, root)
    return installed_artifact("ios", version)


def _extract_app(archive_path: Path, dest: Path) -> None:
    """Unzip an ``.app`` archive, restoring symlinks and refusing paths outside ``dest``."""
    root = dest.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (dest / info.filename).resolve()
            if root not in target.parents and target != root:
                raise GoError(f"{archive_path.name} contains an unsafe path: {info.filename}")
            mode = info.external_attr >> 16
            if (mode & 0o170000) == 0o120000:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(archive.read(info).decode("utf-8"), target)
            elif info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
                if mode & 0o111:
                    target.chmod(0o755)


def ensure_artifact(
    platform: str,
    *,
    force_build: bool = False,
    fetch: Fetch = _fetch,
    log: Optional[Logger] = None,
) -> Path:
    """Return an installable Go artifact for the running framework version.

    Looks in the cache, then downloads the release asset, then builds it
    locally (which needs Xcode or the Android toolchain, once).
    """
    emit = log or print
    version = framework_version()
    if not force_build:
        cached = installed_artifact(platform, version)
        if cached is not None:
            return cached
        downloaded = download(platform, version, fetch=fetch, log=emit)
        if downloaded is not None:
            return downloaded
        emit(f"No prebuilt {GO_DISPLAY_NAME} {version} for {platform}; building it once (this takes a few minutes).")
    return build(platform, out_dir=cache_dir(version) / platform, log=emit)
