"""Embedded CPython runtime acquisition for iOS builds.

iOS apps can't rely on a system Python, so PythonNative bundles a copy of
CPython built for iOS by the excellent
[Python-Apple-support](https://github.com/beeware/Python-Apple-support)
project. This module downloads the pinned release asset, verifies it,
extracts it once (cached under the build directory), and exposes the
paths the [`ios`][pythonnative.project.ios] configurator needs:
``Python.xcframework``, the simulator ``Python.framework``, the standard
library, and the simulator headers/static lib.

Android doesn't need any of this — Chaquopy ships its own CPython via
Gradle — so there's no Android equivalent here.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

# Pinned, checksum-verified asset for the supported iOS Python version.
_PINNED_ASSETS = {
    "3.11": (
        "Python-3.11-iOS-support.b7.tar.gz",
        "2b7d8589715b9890e8dd7e1bce91c210bb5287417e17b9af120fc577675ed28e",
    ),
}

_RELEASES_API = "https://api.github.com/repos/beeware/Python-Apple-support/releases?per_page=100"
_USER_AGENT = "pythonnative-cli"

Logger = Callable[[str], None]


@dataclass
class IOSRuntime:
    """Resolved paths to an extracted iOS CPython support package.

    Attributes:
        python_version: The CPython ``major.minor`` version.
        xcframework_dir: Path to ``Python.xcframework``.
        simulator_framework: Path to the simulator-slice
            ``Python.framework`` (embedded into the simulator ``.app``).
        stdlib_dir: Path to the simulator standard library directory.
        simulator_headers: Path to the simulator-slice ``Headers``
            directory (used when the project links the static lib).
        simulator_static_lib: Path to the simulator ``libPythonX.Y.a``.
        device_framework: Path to the device-slice ``Python.framework``
            (embedded when archiving for a real device).
        device_stdlib: Path to the device standard library directory.
    """

    python_version: str
    xcframework_dir: Path
    simulator_framework: Optional[Path]
    stdlib_dir: Optional[Path]
    simulator_headers: Optional[Path]
    simulator_static_lib: Optional[Path]
    device_framework: Optional[Path] = None
    device_stdlib: Optional[Path] = None

    def framework_for(self, destination: str) -> Optional[Path]:
        """Return the ``Python.framework`` for a build destination.

        Args:
            destination: ``"simulator"`` or ``"device"``.

        Returns:
            The matching framework path, or ``None`` if unavailable.
        """
        return self.device_framework if destination == "device" else self.simulator_framework

    def stdlib_for(self, destination: str) -> Optional[Path]:
        """Return the standard library directory for a build destination.

        Args:
            destination: ``"simulator"`` or ``"device"``.

        Returns:
            The matching stdlib path, or ``None`` if unavailable.
        """
        return self.device_stdlib if destination == "device" else self.stdlib_dir


def _github_json(url: str) -> object:
    headers = {"User-Agent": _USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_asset_url(python_version: str, preferred_name: Optional[str] = None) -> Optional[str]:
    """Resolve a download URL for a Python-Apple-support iOS release asset.

    Prefers an exact ``preferred_name`` match across all releases, then
    falls back to the newest asset whose name contains
    ``Python-<version>-iOS-support`` and ends in ``.tar.gz``.

    Args:
        python_version: CPython ``major.minor`` (e.g., ``"3.11"``).
        preferred_name: Exact asset filename to prefer.

    Returns:
        A ``browser_download_url``, or ``None`` if resolution fails.
    """
    try:
        releases = _github_json(_RELEASES_API)
    except Exception:
        return None
    if not isinstance(releases, list):
        return None

    if preferred_name:
        for release in releases:
            for asset in release.get("assets", []) or []:
                if asset.get("name") == preferred_name:
                    return asset.get("browser_download_url")

    needle = f"Python-{python_version}-iOS-support"
    for release in releases:
        for asset in release.get("assets", []) or []:
            name = asset.get("name") or ""
            if needle in name and name.endswith(".tar.gz"):
                return asset.get("browser_download_url")
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(tar_path: Path, dest: Path) -> None:
    """Extract a tarball, refusing entries that escape ``dest``."""
    dest = dest.resolve()
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            target = (dest / member.name).resolve()
            if not str(target).startswith(str(dest)):
                raise RuntimeError(f"Refusing to extract unsafe path: {member.name}")
        # ``filter='data'`` (3.12+) blocks unsafe members; older Pythons
        # fall back to the manual check above.
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


def _first_existing(candidates: List[Path]) -> Optional[Path]:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _locate_runtime(extract_root: Path, python_version: str) -> IOSRuntime:
    xc_candidates = [
        extract_root / "Python.xcframework",
        extract_root / "support" / "Python.xcframework",
    ]
    xcframework = _first_existing(xc_candidates)
    if xcframework is None:
        raise RuntimeError("Python.xcframework not found in extracted Python-Apple-support package.")

    sim_slice = xcframework / "ios-arm64_x86_64-simulator"
    simulator_framework = _first_existing([sim_slice / "Python.framework"])
    stdlib_dir = _first_existing([sim_slice / "lib" / f"python{python_version}"])
    simulator_headers = _first_existing([sim_slice / "Headers"])
    simulator_static_lib = _first_existing(
        [
            sim_slice / f"libPython{python_version}.a",
            sim_slice / "libpython.a",
        ]
    )

    device_slice = xcframework / "ios-arm64"
    device_framework = _first_existing([device_slice / "Python.framework"])
    device_stdlib = _first_existing([device_slice / "lib" / f"python{python_version}"])

    return IOSRuntime(
        python_version=python_version,
        xcframework_dir=xcframework,
        simulator_framework=simulator_framework,
        stdlib_dir=stdlib_dir,
        simulator_headers=simulator_headers,
        simulator_static_lib=simulator_static_lib,
        device_framework=device_framework,
        device_stdlib=device_stdlib,
    )


def prepare_ios_runtime(
    cache_dir: Path,
    python_version: str = "3.11",
    *,
    log: Optional[Logger] = None,
) -> IOSRuntime:
    """Download (if needed), verify, and extract the iOS CPython package.

    The download and extraction are cached under ``cache_dir`` so repeat
    builds are fast. For the pinned version the tarball checksum is
    verified; for other versions the checksum is skipped with a warning.

    Args:
        cache_dir: Directory to store downloads and extractions in.
        python_version: CPython ``major.minor`` to fetch.
        log: Optional callback for progress messages.

    Returns:
        A resolved [`IOSRuntime`][pythonnative.project.runtime_assets.IOSRuntime].

    Raises:
        RuntimeError: If the asset URL can't be resolved, the checksum
            doesn't match, or the package layout is unexpected.
    """
    emit: Logger = log or (lambda _message: None)
    cache_dir.mkdir(parents=True, exist_ok=True)

    pinned = _PINNED_ASSETS.get(python_version)
    preferred_name = pinned[0] if pinned else None
    expected_sha = pinned[1] if pinned else None

    extract_root = cache_dir / f"python-{python_version}"
    if extract_root.is_dir():
        try:
            return _locate_runtime(extract_root, python_version)
        except RuntimeError:
            # Stale/partial extraction — re-extract below.
            pass

    url = resolve_asset_url(python_version, preferred_name=preferred_name)
    if not url:
        raise RuntimeError(
            f"Could not resolve a Python-Apple-support iOS asset for Python {python_version}. "
            "Check your network connection or set GITHUB_TOKEN to avoid rate limits."
        )

    tar_path = cache_dir / os.path.basename(url)
    if not tar_path.exists():
        emit(f"Downloading embedded Python runtime ({python_version} iOS): {os.path.basename(url)}")
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req) as response, open(tar_path, "wb") as handle:
            handle.write(response.read())

    if expected_sha:
        actual = _sha256(tar_path)
        if actual != expected_sha:
            tar_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Checksum mismatch for {tar_path.name}: expected {expected_sha}, got {actual}. "
                "The download may be corrupt; re-run to try again."
            )
    else:
        emit(f"Warning: no pinned checksum for Python {python_version}; skipping verification.")

    emit("Extracting embedded Python runtime...")
    extract_root.mkdir(parents=True, exist_ok=True)
    _safe_extract(tar_path, extract_root)
    return _locate_runtime(extract_root, python_version)
