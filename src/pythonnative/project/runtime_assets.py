"""Embedded CPython runtime acquisition for iOS builds.

iOS apps can't rely on a system Python, so PythonNative bundles a copy of
CPython built for iOS by the excellent
[Python-Apple-support](https://github.com/beeware/Python-Apple-support)
project. This module downloads the pinned release asset for the
project's ``app.python_version``, verifies its checksum, extracts it
once (cached under the build directory), and exposes the path to
``Python.xcframework``.

The xcframework is linked and embedded by the bundled Xcode template at
build time; its ``build/utils.sh`` helper (shipped inside the framework
by BeeWare) installs the standard library and converts binary modules
into signed frameworks during the Xcode build. There is no post-build
copy step.

Android doesn't need any of this: Chaquopy ships its own CPython via
Gradle, so there's no Android equivalent here.
"""

from __future__ import annotations

import hashlib
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# Pinned, checksum-verified Python-Apple-support assets. Every version in
# ``config.SUPPORTED_PYTHON_VERSIONS`` must have an entry here; iOS builds
# refuse to run against an unpinned, unverified runtime.
#
# Both builds target iOS 13.0 and ship ``ios-arm64`` (device) and
# ``ios-arm64_x86_64-simulator`` slices, so a single package covers every
# ``pn run ios`` / ``pn build ios`` destination.
PINNED_ASSETS = {
    "3.13": (
        "3.13-b14",
        "Python-3.13-iOS-support.b14.tar.gz",
        "8b5cb76ef8d8a2946052479358eeec9d54b4496cb60920e175ec1489b5cf7963",
    ),
    "3.14": (
        "3.14-b10",
        "Python-3.14-iOS-support.b10.tar.gz",
        "200ef60eb67be0483ceb638daa9048f84f41a9a952707a5ad4c3198037c7b583",
    ),
}

_DOWNLOAD_URL = "https://github.com/beeware/Python-Apple-support/releases/download/{tag}/{name}"
_USER_AGENT = "pythonnative-cli"

Logger = Callable[[str], None]


@dataclass
class IOSRuntime:
    """A resolved, extracted iOS CPython support package.

    Attributes:
        python_version: The CPython ``major.minor`` version.
        xcframework_dir: Path to the extracted ``Python.xcframework``.
    """

    python_version: str
    xcframework_dir: Path

    @property
    def install_script(self) -> Path:
        """Path to BeeWare's ``utils.sh`` build helper inside the framework."""
        return self.xcframework_dir / "build" / "utils.sh"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(tar_path: Path, dest: Path) -> None:
    """Extract a tarball, refusing entries that escape ``dest``.

    The manual checks below cover path escapes, link escapes, and special
    files. They are not a ``data_filter`` equivalent: notably they do not
    sanitize modes, so on the fallback path setuid/setgid bits and a
    directory member's permissions are applied as the archive states them.
    That is accepted here because the asset is pinned by SHA-256 and its
    ``build/utils.sh`` has to stay executable.
    """
    dest = dest.resolve()
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            target = (dest / member.name).resolve()
            # ``is_relative_to`` compares path components. A string prefix
            # test would accept a sibling whose name merely starts with
            # ``dest``, such as ``../out-evil/x.txt`` beside ``out/``.
            if not target.is_relative_to(dest):
                raise RuntimeError(f"Refusing to extract unsafe path: {member.name}")
            if member.issym() or member.islnk():
                # A link's name can be innocuous while its target escapes.
                # Symlink targets resolve against the link's own directory;
                # hardlink targets are relative to the archive root.
                base = target.parent if member.issym() else dest
                link_target = (base / member.linkname).resolve()
                if not link_target.is_relative_to(dest):
                    raise RuntimeError(f"Refusing to extract unsafe link: {member.name} -> {member.linkname}")
            if member.isdev():
                # FIFOs and device nodes. ``filter="data"`` rejects these;
                # the fallback would otherwise mknod them. Every member of
                # the pinned archives is a file, directory, or symlink.
                raise RuntimeError(f"Refusing to extract special file: {member.name}")
        # ``filter='data'`` is available on every supported interpreter, so
        # it always runs and blocks unsafe members too. The manual checks
        # above are the primary boundary check: they run first, and their
        # refusals are what the tests pin. The ``except TypeError`` branch
        # below is unreachable on >=3.13; it is kept rather than removed
        # unilaterally.
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


def _locate_runtime(extract_root: Path, python_version: str) -> IOSRuntime:
    xcframework = extract_root / "Python.xcframework"
    if not xcframework.is_dir():
        raise RuntimeError("Python.xcframework not found in extracted Python-Apple-support package.")
    runtime = IOSRuntime(python_version=python_version, xcframework_dir=xcframework)
    if not runtime.install_script.is_file():
        raise RuntimeError(
            "The extracted Python.xcframework is missing build/utils.sh; the support "
            "package layout is older than PythonNative expects. Delete the "
            "build/ios_runtime cache and re-run to fetch the pinned asset."
        )
    return runtime


def prepare_ios_runtime(
    cache_dir: Path,
    python_version: str = "3.13",
    *,
    log: Optional[Logger] = None,
) -> IOSRuntime:
    """Download (if needed), verify, and extract the iOS CPython package.

    The download and extraction are cached under ``cache_dir`` so repeat
    builds are fast. Only pinned, checksum-verified versions are
    accepted; there is no unverified fallback.

    Args:
        cache_dir: Directory to store downloads and extractions in.
        python_version: CPython ``major.minor`` to fetch.
        log: Optional callback for progress messages.

    Returns:
        A resolved [`IOSRuntime`][pythonnative.project.runtime_assets.IOSRuntime].

    Raises:
        RuntimeError: If the version has no pinned asset, the download
            fails, the checksum doesn't match, or the package layout is
            unexpected.
    """
    emit: Logger = log or (lambda _message: None)
    cache_dir.mkdir(parents=True, exist_ok=True)

    pinned = PINNED_ASSETS.get(python_version)
    if pinned is None:
        supported = ", ".join(sorted(PINNED_ASSETS))
        raise RuntimeError(
            f"No pinned iOS runtime for Python {python_version}. Set app.python_version to one of: {supported}."
        )
    tag, asset_name, expected_sha = pinned

    extract_root = cache_dir / f"python-{python_version}"
    if extract_root.is_dir():
        try:
            return _locate_runtime(extract_root, python_version)
        except RuntimeError:
            # Stale/partial extraction: re-extract below.
            pass

    url = _DOWNLOAD_URL.format(tag=tag, name=asset_name)
    tar_path = cache_dir / asset_name
    if not tar_path.exists() or _sha256(tar_path) != expected_sha:
        emit(f"Downloading embedded Python runtime ({python_version} iOS): {asset_name}")
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req) as response, open(tar_path, "wb") as handle:
                handle.write(response.read())
        except OSError as exc:
            tar_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Could not download the iOS Python runtime from {url}: {exc}. "
                "Check your network connection and re-run."
            ) from exc

    actual = _sha256(tar_path)
    if actual != expected_sha:
        tar_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {asset_name}: expected {expected_sha}, got {actual}. "
            "The download may be corrupt; re-run to try again."
        )

    emit("Extracting embedded Python runtime...")
    extract_root.mkdir(parents=True, exist_ok=True)
    _safe_extract(tar_path, extract_root)
    return _locate_runtime(extract_root, python_version)
