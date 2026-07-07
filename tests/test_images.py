"""Unit tests for the shared image pipeline (pythonnative.images)."""

from __future__ import annotations

import io
import threading
from typing import Any, List

import pytest

from pythonnative import images


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(images, "_cache_dir", str(tmp_path))
    images._memory_cache.clear()


def _fake_urlopen_factory(payload: bytes, calls: List[str]) -> Any:
    class _Resp(io.BytesIO):
        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *exc: Any) -> None:
            self.close()

    def _urlopen(req: Any, timeout: float = 0) -> _Resp:
        calls.append(req.full_url)
        return _Resp(payload)

    return _urlopen


def _fetch_and_wait(url: str) -> tuple:
    """Run images.fetch and block until one of the callbacks fires."""
    done = threading.Event()
    result: dict = {}

    def on_ready(path: str) -> None:
        result["path"] = path
        done.set()

    def on_error(message: str) -> None:
        result["error"] = message
        done.set()

    images.fetch(url, on_ready, on_error)
    assert done.wait(timeout=5.0), "fetch never completed"
    return result.get("path"), result.get("error")


# ======================================================================
# _ByteLru
# ======================================================================


def test_lru_put_get_and_eviction() -> None:
    lru = images._ByteLru(max_bytes=10)
    lru.put("a", b"12345")
    lru.put("b", b"12345")
    assert lru.get("a") == b"12345"
    # "b" is now least-recently-used; adding "c" evicts it.
    lru.put("c", b"12345")
    assert lru.get("b") is None
    assert lru.get("a") == b"12345"
    assert lru.get("c") == b"12345"


def test_lru_rejects_oversized_entries() -> None:
    lru = images._ByteLru(max_bytes=4)
    lru.put("big", b"12345")
    assert lru.get("big") is None


# ======================================================================
# Cache paths
# ======================================================================


def test_cache_path_is_stable_and_keeps_extension() -> None:
    a = images._cache_path("https://example.com/pic.png?size=2")
    b = images._cache_path("https://example.com/pic.png?size=2")
    assert a == b
    assert a.endswith(".png")


def test_cache_path_drops_weird_extensions() -> None:
    p = images._cache_path("https://example.com/x.superlongextension")
    assert "." not in p.rsplit("/", 1)[-1][64:]


# ======================================================================
# fetch
# ======================================================================


def test_fetch_downloads_and_writes_disk_cache(monkeypatch: Any) -> None:
    calls: List[str] = []
    monkeypatch.setattr(images.urllib.request, "urlopen", _fake_urlopen_factory(b"IMGDATA", calls))

    url = "https://example.com/a.png"
    path, error = _fetch_and_wait(url)
    assert error is None
    assert path is not None
    with open(path, "rb") as fh:
        assert fh.read() == b"IMGDATA"
    assert calls == [url]


def test_fetch_second_request_hits_cache(monkeypatch: Any) -> None:
    calls: List[str] = []
    monkeypatch.setattr(images.urllib.request, "urlopen", _fake_urlopen_factory(b"IMGDATA", calls))

    url = "https://example.com/b.png"
    _fetch_and_wait(url)
    path, error = _fetch_and_wait(url)
    assert error is None and path is not None
    assert calls == [url]  # no second network round trip


def test_fetch_reports_errors(monkeypatch: Any) -> None:
    def _boom(req: Any, timeout: float = 0) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(images.urllib.request, "urlopen", _boom)
    path, error = _fetch_and_wait("https://example.com/c.png")
    assert path is None
    assert "connection refused" in str(error)


def test_clear_cache_removes_files(monkeypatch: Any) -> None:
    calls: List[str] = []
    monkeypatch.setattr(images.urllib.request, "urlopen", _fake_urlopen_factory(b"IMGDATA", calls))
    url = "https://example.com/d.png"
    path, _ = _fetch_and_wait(url)
    assert path is not None

    images.clear_cache()
    import os

    assert not os.path.isfile(path)
    # Fetch again: must re-download.
    _fetch_and_wait(url)
    assert calls == [url, url]
