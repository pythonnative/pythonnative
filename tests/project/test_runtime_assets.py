"""Unit tests for the iOS runtime asset helpers.

These are network-free. The autouse fixture below blocks socket creation
for this module only; it deliberately does not live in tests/conftest.py,
because tests/test_net.py opens a real socket to find a free port.
"""

from __future__ import annotations

import hashlib
import io
import socket
import tarfile
import warnings
from pathlib import Path
from typing import Any, List, Tuple

import pytest

from pythonnative.project import config, runtime_assets

# Version literals are derived from the source constants, never hardcoded, so
# a supported-version bump does not need edits here. main moved from
# 3.10-3.12 to 3.13-3.14 while this was in review, which is the drift this
# avoids. ``UNPINNED_VERSION`` is the one deliberate literal; the test that
# uses it asserts it really is absent.
PINNED_VERSION = sorted(runtime_assets.PINNED_ASSETS)[0]
OTHER_PINNED_VERSION = sorted(runtime_assets.PINNED_ASSETS)[-1]
UNPINNED_VERSION = "2.7"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if anything in this module reaches for the network.

    Blocking at the socket layer proves no network, where stubbing a
    single ``urlopen`` would only prove that one call site was covered.
    """

    def _blocked(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access attempted in a network-free test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


# ---------------------------------------------------------------------------
# _sha256
# ---------------------------------------------------------------------------


def test_sha256_matches_hashlib(tmp_path: Path) -> None:
    payload = b"pythonnative embedded runtime asset\n"
    path = tmp_path / "asset.bin"
    path.write_bytes(payload)

    assert runtime_assets._sha256(path) == hashlib.sha256(payload).hexdigest()


def test_sha256_reads_across_chunk_boundaries(tmp_path: Path) -> None:
    # _sha256 reads in 1 MiB chunks. A payload larger than one chunk makes
    # the read loop iterate more than once, which a short string never does.
    payload = b"pn" * 1_500_000  # ~2.9 MiB, spanning three chunks
    path = tmp_path / "big.bin"
    path.write_bytes(payload)

    assert len(payload) > 2 * 1024 * 1024
    assert runtime_assets._sha256(path) == hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# _safe_extract
# ---------------------------------------------------------------------------


class _NoFilterTar:
    """Wrap a TarFile so ``extractall(filter=...)`` raises TypeError.

    ``filter="data"`` landed in 3.12 and was backported to 3.10.12 and
    3.11.4, so CI (which runs current patch releases) always takes the
    filter path. Without this shim the manual checks in ``_safe_extract``
    are never exercised, and they are the only protection an older
    interpreter in the supported range has.
    """

    def __init__(self, inner: tarfile.TarFile) -> None:
        self._inner = inner

    def __enter__(self) -> "_NoFilterTar":
        self._inner.__enter__()
        return self

    def __exit__(self, *exc: Any) -> Any:
        return self._inner.__exit__(*exc)

    def getmembers(self) -> List[tarfile.TarInfo]:
        return self._inner.getmembers()

    def extractall(self, *args: Any, **kwargs: Any) -> Any:
        if "filter" in kwargs:
            raise TypeError("extractall() got an unexpected keyword argument 'filter'")
        # Extracting with no filter is deprecated from 3.12 and warns on
        # 3.14. That warning is this shim doing exactly what it simulates,
        # not the code under test, so keep it out of the suite's output.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return self._inner.extractall(*args, **kwargs)


@pytest.fixture
def force_no_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make _safe_extract take its pre-3.10.12 fallback path."""
    real_open = tarfile.open

    def _open(*args: Any, **kwargs: Any) -> Any:
        # runtime_assets.tarfile is the shared module, so this patch is
        # visible to the tests' own tarball writing too. Wrap read mode
        # only, which is the single call _safe_extract makes.
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        opened = real_open(*args, **kwargs)
        return _NoFilterTar(opened) if str(mode).startswith("r") else opened

    monkeypatch.setattr(runtime_assets.tarfile, "open", _open)


def _workspace(tmp_path: Path) -> Tuple[Path, Path]:
    """Return (root, dest). The dest basename is deliberately ``out``.

    Sibling paths like ``out-evil`` and ``outsider.txt`` share that string
    prefix, which is what a ``startswith`` containment test fails to catch.
    """
    root = tmp_path / "work"
    dest = root / "out"
    dest.mkdir(parents=True)
    return root, dest


def _add_file(tar: tarfile.TarFile, name: str, data: bytes = b"payload\n") -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _add_link(tar: tarfile.TarFile, name: str, linkname: str, *, hard: bool = False) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.LNKTYPE if hard else tarfile.SYMTYPE
    info.linkname = linkname
    tar.addfile(info)


def _add_special(tar: tarfile.TarFile, name: str, kind: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = {"fifo": tarfile.FIFOTYPE, "chr": tarfile.CHRTYPE, "blk": tarfile.BLKTYPE}[kind]
    info.mode = 0o644
    if kind != "fifo":
        info.devmajor, info.devminor = (1, 3) if kind == "chr" else (8, 0)
    tar.addfile(info)


def _files_outside(root: Path, dest: Path) -> List[str]:
    """Every regular file under root that is not inside dest, tarballs aside."""
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and not path.is_relative_to(dest) and path.suffix != ".gz"
    )


ESCAPING_MEMBERS = [
    pytest.param("../escape.txt", id="parent-dir"),
    pytest.param("../outsider.txt", id="sibling-file-sharing-prefix"),
    pytest.param("../out-evil/x.txt", id="sibling-dir-sharing-prefix"),
]


def test_safe_extract_extracts_a_normal_member(tmp_path: Path) -> None:
    root, dest = _workspace(tmp_path)
    tar_path = root / "a.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        _add_file(tar, "nested/dir/normal.txt", b"hello\n")

    runtime_assets._safe_extract(tar_path, dest)

    assert (dest / "nested" / "dir" / "normal.txt").read_text(encoding="utf-8") == "hello\n"
    assert _files_outside(root, dest) == []


def _assert_member_refused(tmp_path: Path, member: str) -> None:
    """The member is refused by the manual check, and nothing escapes dest.

    Matching on RuntimeError is deliberate: it is what the manual check
    raises. If that check stopped catching a member, the ``filter="data"``
    layer would still block it on a current interpreter, but as
    ``tarfile.OutsideDestinationError``, so this assertion pins which layer
    did the work.
    """
    root, dest = _workspace(tmp_path)
    tar_path = root / "a.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        _add_file(tar, member)

    with pytest.raises(RuntimeError, match="Refusing to extract unsafe path"):
        runtime_assets._safe_extract(tar_path, dest)
    assert _files_outside(root, dest) == []


@pytest.mark.parametrize("member", ESCAPING_MEMBERS)
def test_safe_extract_refuses_escaping_members(tmp_path: Path, member: str) -> None:
    _assert_member_refused(tmp_path, member)


@pytest.mark.parametrize("member", ESCAPING_MEMBERS)
def test_safe_extract_refuses_escaping_members_without_the_filter(
    tmp_path: Path, member: str, force_no_filter: None
) -> None:
    # Same members with extractall's filter unavailable, so the manual
    # checks are the only thing between the archive and the disk.
    _assert_member_refused(tmp_path, member)


def test_safe_extract_refuses_a_symlink_that_escapes_via_linkname(tmp_path: Path, force_no_filter: None) -> None:
    # Both member names resolve inside dest; only the link target escapes.
    # Extracting the pair writes through the symlink, outside dest.
    root, dest = _workspace(tmp_path)
    (root / "outside_target").mkdir()
    tar_path = root / "a.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        _add_link(tar, "escape_dir", "../outside_target")
        _add_file(tar, "escape_dir/payload.txt", b"pwned\n")

    with pytest.raises(RuntimeError, match="Refusing to extract unsafe link"):
        runtime_assets._safe_extract(tar_path, dest)
    assert _files_outside(root, dest) == []
    assert list((root / "outside_target").iterdir()) == []


def test_safe_extract_refuses_a_hardlink_that_escapes_via_linkname(tmp_path: Path, force_no_filter: None) -> None:
    root, dest = _workspace(tmp_path)
    tar_path = root / "a.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        _add_link(tar, "hard", "../../secret.txt", hard=True)

    with pytest.raises(RuntimeError, match="Refusing to extract unsafe link"):
        runtime_assets._safe_extract(tar_path, dest)


def test_safe_extract_allows_a_symlink_that_stays_inside(tmp_path: Path, force_no_filter: None) -> None:
    # Guards against over-blocking: a link pointing within dest is fine.
    root, dest = _workspace(tmp_path)
    tar_path = root / "a.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        _add_file(tar, "subdir/real.txt", b"ok\n")
        _add_link(tar, "subdir/alias.txt", "real.txt")

    runtime_assets._safe_extract(tar_path, dest)

    assert (dest / "subdir" / "alias.txt").is_symlink()
    assert (dest / "subdir" / "alias.txt").read_text(encoding="utf-8") == "ok\n"


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("fifo", id="fifo"),
        pytest.param("chr", id="character-device"),
        pytest.param("blk", id="block-device"),
    ],
)
def test_safe_extract_refuses_special_files(tmp_path: Path, kind: str, force_no_filter: None) -> None:
    # filter="data" raises SpecialFileError for these. Without it the
    # fallback creates the FIFO outright and reaches mknod for the device
    # nodes, which fail only for lack of privilege.
    root, dest = _workspace(tmp_path)
    tar_path = root / "a.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        _add_special(tar, "special_member", kind)

    with pytest.raises(RuntimeError, match="Refusing to extract special file"):
        runtime_assets._safe_extract(tar_path, dest)
    assert list(dest.iterdir()) == []


# ---------------------------------------------------------------------------
# _locate_runtime
# ---------------------------------------------------------------------------


def _xcframework(root: Path, *, with_utils: bool = True) -> Path:
    xcframework = root / "Python.xcframework"
    (xcframework / "build").mkdir(parents=True)
    if with_utils:
        (xcframework / "build" / "utils.sh").write_text("install_python() { :; }\n", encoding="utf-8")
    return xcframework


def test_locate_runtime_raises_without_the_xcframework(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Python.xcframework not found"):
        runtime_assets._locate_runtime(tmp_path, PINNED_VERSION)


def test_locate_runtime_raises_without_utils_sh(tmp_path: Path) -> None:
    _xcframework(tmp_path, with_utils=False)

    with pytest.raises(RuntimeError, match="missing build/utils.sh"):
        runtime_assets._locate_runtime(tmp_path, PINNED_VERSION)


def test_locate_runtime_returns_a_runtime_when_both_exist(tmp_path: Path) -> None:
    xcframework = _xcframework(tmp_path)

    # A second pinned version, to show _locate_runtime echoes what it is
    # given rather than resolving a version of its own.
    runtime = runtime_assets._locate_runtime(tmp_path, OTHER_PINNED_VERSION)

    assert runtime.python_version == OTHER_PINNED_VERSION
    assert runtime.xcframework_dir == xcframework
    assert runtime.install_script == xcframework / "build" / "utils.sh"
    assert runtime.install_script.is_file()


# ---------------------------------------------------------------------------
# PINNED_ASSETS
# ---------------------------------------------------------------------------


def test_pinned_assets_and_supported_versions_agree() -> None:
    # Both modules document this invariant in prose but nothing enforced it.
    # The drift this catches: adding a version to SUPPORTED_PYTHON_VERSIONS
    # without pinning an asset makes `pn run ios` accept the config, then
    # fail deep in prepare_ios_runtime with "No pinned iOS runtime".
    assert set(runtime_assets.PINNED_ASSETS) == set(config.SUPPORTED_PYTHON_VERSIONS)


def test_pinned_assets_entries_are_well_formed() -> None:
    for version, entry in runtime_assets.PINNED_ASSETS.items():
        tag, asset_name, expected_sha = entry
        assert version in tag, f"{version}: tag {tag!r} should name the version"
        assert asset_name.endswith(".tar.gz"), asset_name
        assert len(expected_sha) == 64 and set(expected_sha) <= set("0123456789abcdef"), expected_sha


# ---------------------------------------------------------------------------
# prepare_ios_runtime
# ---------------------------------------------------------------------------


def test_prepare_ios_runtime_rejects_an_unpinned_version(tmp_path: Path) -> None:
    cache = tmp_path / "ios_runtime"

    assert UNPINNED_VERSION not in runtime_assets.PINNED_ASSETS

    with pytest.raises(RuntimeError) as excinfo:
        runtime_assets.prepare_ios_runtime(cache, UNPINNED_VERSION)

    message = str(excinfo.value)
    assert f"No pinned iOS runtime for Python {UNPINNED_VERSION}" in message
    for version in config.SUPPORTED_PYTHON_VERSIONS:
        assert version in message
    # cache_dir.mkdir runs before the version check, so the directory exists
    # even on the failure path. Asserted so a future reorder is deliberate.
    assert cache.is_dir()


def test_prepare_ios_runtime_returns_the_cached_extraction(tmp_path: Path) -> None:
    cache = tmp_path / "ios_runtime"
    extract_root = cache / f"python-{PINNED_VERSION}"
    extract_root.mkdir(parents=True)
    xcframework = _xcframework(extract_root)
    messages: List[str] = []

    runtime = runtime_assets.prepare_ios_runtime(cache, PINNED_VERSION, log=messages.append)

    assert runtime.python_version == PINNED_VERSION
    assert runtime.xcframework_dir == xcframework
    assert runtime.install_script.is_file()
    # Both the download and the extraction branches emit; silence proves
    # neither ran, which is what "cached" has to mean.
    assert messages == []
    assert sorted(path.name for path in cache.iterdir()) == [f"python-{PINNED_VERSION}"]


def test_prepare_ios_runtime_refetches_a_stale_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Python.xcframework exists but build/utils.sh does not, so _locate_runtime
    # raises and the cached branch falls through to the download.
    cache = tmp_path / "ios_runtime"
    extract_root = cache / f"python-{PINNED_VERSION}"
    extract_root.mkdir(parents=True)
    _xcframework(extract_root, with_utils=False)

    attempted: List[str] = []

    def _fake_urlopen(request: Any, *args: Any, **kwargs: Any) -> Any:
        attempted.append(request.full_url)
        raise OSError("no network in tests")

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError, match="Could not download the iOS Python runtime"):
        runtime_assets.prepare_ios_runtime(cache, PINNED_VERSION)

    assert len(attempted) == 1
    assert attempted[0].endswith(runtime_assets.PINNED_ASSETS[PINNED_VERSION][1])


def test_no_network_fixture_actually_blocks(tmp_path: Path) -> None:
    # Proves the guard above is live, rather than trusting it.
    with pytest.raises(AssertionError, match="network access attempted"):
        socket.socket()
