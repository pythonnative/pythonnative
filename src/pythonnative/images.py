"""Shared image pipeline: async fetch with memory and disk caching.

Every platform's ``Image`` handler routes remote sources through this
module. The pipeline downloads on a daemon thread (never blocking the
UI), stores the raw bytes in a platform-appropriate disk cache keyed
by URL hash, deduplicates concurrent requests for the same URL, and
keeps a small in-memory LRU of recently fetched byte payloads so
scrolling back to an image doesn't touch the filesystem again.

Decoding stays platform-native (``BitmapFactory`` / ``UIImage`` /
``PhotoImage``): callbacks receive a *local file path*, which each
handler decodes with its platform's downsampling facilities.

Callbacks are delivered on the platform main thread via
[`call_on_main_thread`][pythonnative.runtime.call_on_main_thread], so
handlers can touch native views directly.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import urllib.request
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Tuple

_DOWNLOAD_TIMEOUT_S = 30.0
_MEMORY_CACHE_MAX_BYTES = 16 * 1024 * 1024


def _default_cache_dir() -> str:
    """Resolve the on-disk cache directory for the current platform.

    Android: the app's ``Context.getCacheDir()`` (purged by the OS
    under storage pressure). iOS: ``~/Library/Caches`` (excluded from
    backups). Browser preview and tests: a per-user directory under the
    system temp dir.
    """
    try:
        from .utils import IS_ANDROID, IS_IOS

        if IS_ANDROID or IS_IOS:
            from .native_modules.registry import native_module

            info = native_module("Device").call("info")
            if isinstance(info, dict) and info.get("cache_dir"):
                return os.path.join(str(info["cache_dir"]), "pn_images")
    except Exception:
        pass
    home = os.path.expanduser("~")
    caches = os.path.join(home, "Library", "Caches")
    if os.path.isdir(caches):  # iOS / macOS
        return os.path.join(caches, "pn_images")
    return os.path.join(tempfile.gettempdir(), "pn_images")


class _ByteLru:
    """Tiny thread-safe LRU for raw image bytes."""

    def __init__(self, max_bytes: int) -> None:
        self._max = max_bytes
        self._size = 0
        self._items: "OrderedDict[str, bytes]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            data = self._items.get(key)
            if data is not None:
                self._items.move_to_end(key)
            return data

    def put(self, key: str, data: bytes) -> None:
        if len(data) > self._max:
            return
        with self._lock:
            old = self._items.pop(key, None)
            if old is not None:
                self._size -= len(old)
            self._items[key] = data
            self._size += len(data)
            while self._size > self._max and self._items:
                _, evicted = self._items.popitem(last=False)
                self._size -= len(evicted)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._size = 0


_memory_cache = _ByteLru(_MEMORY_CACHE_MAX_BYTES)
_cache_dir: Optional[str] = None
# URL -> callbacks waiting on an in-flight download.
_in_flight: Dict[str, List[Tuple[Callable[[str], None], Callable[[str], None]]]] = {}
_in_flight_lock = threading.Lock()


def _get_cache_dir() -> str:
    global _cache_dir
    if _cache_dir is None:
        _cache_dir = _default_cache_dir()
        os.makedirs(_cache_dir, exist_ok=True)
    return _cache_dir


def _cache_path(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    ext = os.path.splitext(url.split("?", 1)[0])[1]
    if len(ext) > 8 or "/" in ext:
        ext = ""
    return os.path.join(_get_cache_dir(), digest + ext)


def _dispatch_main(fn: Callable[[], None]) -> None:
    try:
        from .runtime import call_on_main_thread

        call_on_main_thread(fn)
    except Exception:
        try:
            fn()
        except Exception:
            pass


def fetch(
    url: str,
    on_ready: Callable[[str], None],
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """Fetch ``url`` into the cache and deliver a local file path.

    Cache hits (memory or disk) still deliver asynchronously-consistent
    behavior but resolve without a network round trip. Concurrent
    requests for the same URL share one download. Callbacks run on the
    platform main thread.

    Args:
        url: The ``http(s)`` image URL.
        on_ready: Called with the local file path once available.
        on_error: Called with an error message if the download fails.
    """
    path = _cache_path(url)
    if _memory_cache.get(url) is not None or os.path.isfile(path):
        _dispatch_main(lambda: on_ready(path))
        return

    err = on_error or (lambda _msg: None)
    with _in_flight_lock:
        waiters = _in_flight.get(url)
        if waiters is not None:
            waiters.append((on_ready, err))
            return
        _in_flight[url] = [(on_ready, err)]

    def _worker() -> None:
        error_msg: Optional[str] = None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PythonNative"})
            with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_S) as resp:
                data = resp.read()
            _memory_cache.put(url, data)
            tmp = path + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except Exception as exc:
            error_msg = str(exc)
        with _in_flight_lock:
            callbacks = _in_flight.pop(url, [])

        def _notify(ready_cb: Callable[[str], None], error_cb: Callable[[str], None], msg: Optional[str]) -> None:
            if msg is None:
                _dispatch_main(lambda: ready_cb(path))
            else:
                _dispatch_main(lambda: error_cb(msg))

        for ready_cb, error_cb in callbacks:
            _notify(ready_cb, error_cb, error_msg)

    threading.Thread(target=_worker, name=f"pn-image-{path[-12:]}", daemon=True).start()


def clear_cache() -> None:
    """Empty the memory cache and delete all cached image files."""
    _memory_cache.clear()
    try:
        directory = _get_cache_dir()
        for name in os.listdir(directory):
            try:
                os.remove(os.path.join(directory, name))
            except OSError:
                pass
    except OSError:
        pass
