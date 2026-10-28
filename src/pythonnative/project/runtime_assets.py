"""Embedded CPython runtime acquisition for iOS builds.

iOS apps can't rely on a system Python, so PythonNative bundles a copy of
CPython built for iOS by the excellent
[Python-Apple-support](https://github.com/beeware/Python-Apple-support)
project. This module downloads the pinned release asset for the
project's ``app.python_version``, verifies its checksum, and prepares it
once per machine in a shared cache
([`default_cache_dir`][pythonnative.project.runtime_assets.default_cache_dir]):

- the standard library loses the parts an app never imports
  ([`PRUNED_STDLIB`][pythonnative.project.runtime_assets.PRUNED_STDLIB] and
  the test-only extension modules), and
- the remaining modules are compiled to bytecode, so the device never
  compiles the standard library at launch.

The xcframework is linked and embedded by the bundled Xcode template at
build time; its ``build/utils.sh`` helper (shipped inside the framework
by BeeWare) installs the prepared standard library and converts binary
modules into signed frameworks during the Xcode build.

Android doesn't need any of this: Chaquopy ships its own precompiled
CPython via Gradle, so there's no Android equivalent here.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

from . import bytecode

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
_DOWNLOAD_TIMEOUT_S = 60

CACHE_ENV = "PN_CACHE_DIR"
"""Environment variable that overrides the shared cache directory."""

PREPARATION = 1
"""Version of the pruning and compilation applied to a cached runtime.

Raising it makes every cached runtime prepare itself again.
"""

PRUNED_STDLIB = (
    "test",
    "idlelib",
    "tkinter",
    "turtledemo",
    "turtle.py",
    "ensurepip",
    "venv",
    "__phello__",
    "__hello__.py",
    "antigravity.py",
    "this.py",
)
"""Standard library entries an app never imports: tests, GUI toolkits, and installers.

``pydoc_data`` and ``_pyrepl`` stay, because ``pydoc`` and ``site`` import them.
"""

PRUNED_EXTENSIONS = (
    "_ctypes_test",
    "_testbuffer",
    "_testcapi",
    "_testclinic",
    "_testclinic_limited",
    "_testexternalinspection",
    "_testimportmultiple",
    "_testinternalcapi",
    "_testlimitedcapi",
    "_testmultiphase",
    "_testsinglephase",
    "_xxtestfuzz",
    "xxlimited",
    "xxlimited_35",
    "xxsubtype",
)
"""CPython's test-only extension modules; each would become a signed framework."""

Logger = Callable[[str], None]


def default_cache_dir() -> Path:
    """The per-machine cache shared by every project.

    ``PN_CACHE_DIR`` wins; otherwise ``~/Library/Caches/pythonnative`` on
    macOS and ``$XDG_CACHE_HOME/pythonnative`` (``~/.cache/pythonnative``)
    elsewhere.
    """
    override = os.environ.get(CACHE_ENV)
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "pythonnative"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "pythonnative"


@dataclass
class IOSRuntime:
    """A resolved, extracted iOS CPython support package.

    Attributes:
        python_version: The CPython ``major.minor`` version.
        xcframework_dir: Path to the extracted ``Python.xcframework``.
        stdlib_compiled: Whether the standard library carries bytecode.
    """

    python_version: str
    xcframework_dir: Path
    stdlib_compiled: bool = False

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

    Preflight checks reject unsafe paths, link targets, and special files.
    The data filter also checks each member during extraction, accounting
    for links created by earlier members and sanitizing file permissions.
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
                # The pinned archives only need files, directories, and
                # links, so refuse FIFOs and device nodes before extraction.
                raise RuntimeError(f"Refusing to extract special file: {member.name}")
        # Every supported interpreter provides the data filter. Keep it
        # explicit because Python 3.13 defaults to unfiltered extraction.
        tar.extractall(dest, filter="data")


def _locate_runtime(extract_root: Path, python_version: str) -> IOSRuntime:
    xcframework = extract_root / "Python.xcframework"
    if not xcframework.is_dir():
        raise RuntimeError("Python.xcframework not found in extracted Python-Apple-support package.")
    runtime = IOSRuntime(python_version=python_version, xcframework_dir=xcframework)
    if not runtime.install_script.is_file():
        raise RuntimeError(
            "The extracted Python.xcframework is missing build/utils.sh; the support "
            "package layout is older than PythonNative expects. Delete "
            f"{extract_root} and re-run to fetch the pinned asset."
        )
    return runtime


@contextlib.contextmanager
def _locked(cache_dir: Path) -> Iterator[None]:
    """Serialize preparation between concurrent builds on one machine."""
    try:
        import fcntl
    except ImportError:  # pragma: no cover - Windows never builds for iOS
        yield
        return
    with open(cache_dir / ".lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _download(url: str, destination: Path, emit: Logger) -> None:
    """Stream ``url`` to ``destination`` with a timeout and progress output."""
    partial = destination.with_name(destination.name + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_S) as response, open(partial, "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            received, reported = 0, 0
            while chunk := response.read(1 << 20):
                handle.write(chunk)
                received += len(chunk)
                if total and received * 4 // total > reported:
                    reported = received * 4 // total
                    emit(f"  {received * 100 // total}% of {total / 1e6:.0f} MB")
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not download the iOS Python runtime from {url}: {exc}. Check your network connection and re-run."
        ) from exc
    os.replace(partial, destination)


def _python_lib(xcframework: Path, python_version: str) -> Iterator[Path]:
    """Every ``lib*/pythonX.Y`` directory in the framework and its slices."""
    for candidate in (xcframework / "lib", *xcframework.glob("*/lib"), *xcframework.glob("*/lib-*")):
        directory = candidate / f"python{python_version}"
        if directory.is_dir():
            yield directory


def prune_stdlib(xcframework: Path, python_version: str) -> int:
    """Remove [`PRUNED_STDLIB`][pythonnative.project.runtime_assets.PRUNED_STDLIB] and test extensions.

    Returns:
        The number of entries removed.
    """
    removed = 0
    for lib in _python_lib(xcframework, python_version):
        for name in PRUNED_STDLIB:
            target = lib / name
            if target.is_dir():
                shutil.rmtree(target)
                removed += 1
            elif target.exists():
                target.unlink()
                removed += 1
        dynload = lib / "lib-dynload"
        if dynload.is_dir():
            for module in dynload.iterdir():
                if module.name.split(".", 1)[0] in PRUNED_EXTENSIONS:
                    module.unlink()
                    removed += 1
    return removed


def _prepare(extract_root: Path, runtime: IOSRuntime, compiler: Optional[str], emit: Logger) -> IOSRuntime:
    """Prune once, then compile the standard library once a compiler is available."""
    pruned = extract_root / f".pn-pruned-{PREPARATION}"
    if not pruned.exists():
        removed = prune_stdlib(runtime.xcframework_dir, runtime.python_version)
        emit(f"Trimmed the embedded standard library ({removed} test and tooling entries removed).")
        pruned.touch()
    compiled = extract_root / f".pn-compiled-{PREPARATION}"
    if not compiled.exists() and compiler is not None:
        emit("Compiling the embedded standard library to bytecode (once per machine)...")
        ok = True
        for lib in _python_lib(runtime.xcframework_dir, runtime.python_version):
            ok = bytecode.compile_tree(lib, compiler, sourceless=False, label=f"python/lib/{lib.name}") and ok
        if ok:
            compiled.touch()
        else:
            emit("Some standard library modules didn't compile; they'll compile on the device instead.")
    runtime.stdlib_compiled = compiled.exists()
    return runtime


def prepare_ios_runtime(
    cache_dir: Path,
    python_version: str = "3.13",
    *,
    log: Optional[Logger] = None,
    compiler: Optional[str] = None,
) -> IOSRuntime:
    """Download (if needed), verify, extract, and prepare the iOS CPython package.

    Everything is cached under ``cache_dir`` and shared by every project,
    so a machine downloads and prepares each pinned runtime once. Only
    pinned, checksum-verified versions are accepted; there is no
    unverified fallback.

    Args:
        cache_dir: Directory to store downloads and extractions in.
        python_version: CPython ``major.minor`` to fetch.
        log: Optional callback for progress messages.
        compiler: A host interpreter matching ``python_version`` that
            compiles the standard library. Without one, the runtime is
            pruned but not compiled until a later build provides it.

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

    with _locked(cache_dir):
        extract_root = cache_dir / f"python-{tag}"
        if extract_root.is_dir():
            try:
                return _prepare(extract_root, _locate_runtime(extract_root, python_version), compiler, emit)
            except RuntimeError:
                # A stale or partial extraction: extract again below.
                shutil.rmtree(extract_root)

        tar_path = cache_dir / asset_name
        if not tar_path.exists() or _sha256(tar_path) != expected_sha:
            emit(f"Downloading the embedded Python runtime ({python_version} iOS, once per machine): {asset_name}")
            _download(_DOWNLOAD_URL.format(tag=tag, name=asset_name), tar_path, emit)

        actual = _sha256(tar_path)
        if actual != expected_sha:
            tar_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Checksum mismatch for {asset_name}: expected {expected_sha}, got {actual}. "
                "The download may be corrupt; re-run to try again."
            )

        emit("Extracting the embedded Python runtime...")
        staging = cache_dir / f".extract-{os.getpid()}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        try:
            _safe_extract(tar_path, staging)
            runtime = _locate_runtime(staging, python_version)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        os.replace(staging, extract_root)
        runtime = _locate_runtime(extract_root, python_version)
        return _prepare(extract_root, runtime, compiler, emit)
