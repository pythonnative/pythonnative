"""Async HTTP client (``pn.fetch``).

A small, dependency-free coroutine wrapper around
:mod:`urllib.request`. Operates on bytes internally and exposes a
:class:`Response` with `text()`, `json()`, and `bytes` accessors.

It covers what a mobile app reaches for: JSON APIs, multipart uploads
(``files=``) with progress, and streamed downloads (``stream=True``). For
HTTP/2 or connection pooling, integrate ``httpx`` or ``aiohttp`` directly.
WebSockets are in [`pythonnative.websocket`][pythonnative.websocket].

Example:
    ```python
    import pythonnative as pn


    async def load_user(user_id):
        resp = await pn.fetch(
            f"https://api.example.com/users/{user_id}",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


    async def upload_photo(path):
        resp = await pn.fetch(
            "https://api.example.com/photos",
            method="POST",
            body={"caption": "Trailhead"},
            files={"photo": Path(path)},
            on_upload_progress=lambda sent, total: print(sent, "of", total),
        )
        resp.raise_for_status()


    async def download(url, destination):
        resp = await pn.fetch(url, stream=True)
        with open(destination, "wb") as out:
            async for chunk in resp.chunks():
                out.write(chunk)
    ```
"""

from __future__ import annotations

import asyncio
import itertools
import json
import mimetypes
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, Union

# A package-level SSL context lets callers (or tests) override TLS
# verification globally without monkeypatching the stdlib. Defaults
# to the system trust store.
_default_ssl_context: Optional[ssl.SSLContext] = None


def set_default_ssl_context(context: Optional[ssl.SSLContext]) -> None:
    """Override the SSL context used by [`fetch`][pythonnative.fetch].

    ``None`` (the default) means ``urllib`` builds a context from
    the system trust store. Tests can pass an unverified context.
    """
    global _default_ssl_context
    _default_ssl_context = context


def default_ssl_context() -> ssl.SSLContext:
    """The TLS context [`fetch`][pythonnative.fetch] and ``WebSocket`` connect with."""
    return _default_ssl_context or ssl.create_default_context()


# ======================================================================
# Response object
# ======================================================================


@dataclass
class Response:
    """The result of a [`fetch`][pythonnative.fetch] call.

    Attributes:
        status: HTTP status code (e.g. ``200``).
        url: Final URL after any redirects.
        headers: Response headers, case-insensitive.
        content: Raw response body. With ``stream=True``, it stays empty until
            [`read`][pythonnative.net.Response.read] fills it.
    """

    status: int
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes = b""
    _stream: Any = field(default=None, repr=False, compare=False)

    @property
    def ok(self) -> bool:
        """``True`` if the status is in the 2xx range."""
        return 200 <= self.status < 300

    def __repr__(self) -> str:
        cls = type(self).__name__
        return f"{cls}(status={self.status}, url={self.url!r}, ok={self.ok}, content={len(self.content)} bytes)"

    async def chunks(self, size: int = 64 * 1024) -> AsyncIterator[bytes]:
        """Yield a ``stream=True`` response's body as it arrives, then close it.

        Args:
            size: The largest chunk to yield, in bytes.

        Raises:
            RuntimeError: If the response wasn't requested with ``stream=True``,
                or its body was already read.
        """
        stream = self._stream
        if stream is None:
            raise RuntimeError("chunks() needs a response from fetch(..., stream=True) that hasn't been read yet.")
        self._stream = None
        try:
            while True:
                chunk = await asyncio.to_thread(stream.read, size)
                if not chunk:
                    return
                yield chunk
        finally:
            await asyncio.to_thread(stream.close)

    async def read(self) -> bytes:
        """Read the rest of a ``stream=True`` response into ``content`` and return it."""
        if self._stream is not None:
            self.content = b"".join([chunk async for chunk in self.chunks()])
        return self.content

    async def close(self) -> None:
        """Abandon a ``stream=True`` response's unread body. Safe to call on any response."""
        stream, self._stream = self._stream, None
        if stream is not None:
            await asyncio.to_thread(stream.close)

    def text(self, encoding: Optional[str] = None) -> str:
        """Decode ``content`` to ``str``.

        Args:
            encoding: Optional override; defaults to the
                ``charset`` parameter of ``Content-Type`` (or UTF-8).
        """
        enc = encoding or _charset_from_headers(self.headers) or "utf-8"
        try:
            return self.content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse the response body as JSON.

        Raises:
            json.JSONDecodeError: If the body isn't valid JSON.
        """
        return json.loads(self.text())

    def raise_for_status(self) -> None:
        """Raise [`HTTPError`][pythonnative.net.HTTPError] for non-2xx responses."""
        if not self.ok:
            raise HTTPError(self.status, self.url, self.text())


class HTTPError(Exception):
    """Raised by [`Response.raise_for_status`][pythonnative.net.Response.raise_for_status]."""

    def __init__(self, status: int, url: str, body: str) -> None:
        super().__init__(f"HTTP {status} from {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body


def _charset_from_headers(headers: Mapping[str, str]) -> Optional[str]:
    ctype = headers.get("Content-Type") or headers.get("content-type")
    if not ctype:
        return None
    for part in ctype.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            return part[len("charset=") :].strip().strip('"')
    return None


# ======================================================================
# Public fetch coroutine
# ======================================================================


UploadFile = Union[Path, bytes, Tuple[str, Union[Path, bytes], str]]
"""A file for ``fetch(files=...)``: a path, raw bytes, or ``(filename, content, content_type)``."""


async def fetch(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Mapping[str, str]] = None,
    body: Union[bytes, str, Mapping[str, Any], None] = None,
    params: Optional[Mapping[str, Any]] = None,
    timeout: float = 30.0,
    files: Optional[Mapping[str, UploadFile]] = None,
    stream: bool = False,
    on_upload_progress: Optional[Callable[[int, int], None]] = None,
) -> Response:
    """Make an HTTP request and return a [`Response`][pythonnative.net.Response].

    Args:
        url: Target URL. Relative URLs are not supported.
        method: HTTP method (``GET``, ``POST``, ``PUT`` …).
        headers: Optional request headers.
        body: Request body. ``bytes`` are sent as-is; ``str`` is
            UTF-8 encoded; ``dict`` is JSON-encoded with a
            ``Content-Type: application/json`` header added (unless
            already supplied).
        params: Optional mapping of query-string parameters appended
            to ``url`` (urlencoded).
        timeout: Seconds to wait for the response (excluding the
            time spent on DNS / connect).
        files: Files to send as a ``multipart/form-data`` body, by field name.
            Each value is a ``Path``, raw ``bytes``, or a
            ``(filename, Path | bytes, content_type)`` tuple. ``body``, when a
            mapping, then supplies the form's other fields.
        stream: Return as soon as the headers arrive, and read the body with
            [`Response.chunks`][pythonnative.net.Response.chunks] or
            [`Response.read`][pythonnative.net.Response.read].
        on_upload_progress: Called on the application thread with
            ``(bytes_sent, bytes_total)`` as the body goes out.

    Returns:
        A [`Response`][pythonnative.net.Response].

    Raises:
        TimeoutError: If the request doesn't complete within
            ``timeout`` seconds.
        OSError: For network errors (DNS failure, connection refused,
            etc.), re-raised from ``urllib``.

    Example:
        ```python
        resp = await pn.fetch(
            "https://api.example.com/posts",
            method="POST",
            body={"title": "Hello"},
        )
        resp.raise_for_status()
        ```
    """
    # Building an upload reads its files, which mustn't block the render loop.
    build = partial(_build_request, url=url, method=method, headers=headers, body=body, params=params, files=files)
    request = await asyncio.to_thread(build) if files else build()
    if on_upload_progress is not None and isinstance(request.data, bytes):
        request.data = _ProgressBody(request.data, on_upload_progress, asyncio.get_running_loop())
    if not _observers:
        return await asyncio.to_thread(_dispatch_request, request, timeout, stream)
    return await _observed(request, timeout, stream)


class _ProgressBody:
    """A request body urllib sends in pieces, reporting each one to the application thread."""

    CHUNK = 64 * 1024

    def __init__(self, data: bytes, callback: Callable[[int, int], None], loop: asyncio.AbstractEventLoop) -> None:
        self.data = data
        self.callback = callback
        self.loop = loop

    def __iter__(self) -> Iterator[bytes]:
        total = len(self.data)
        for start in range(0, total, self.CHUNK):
            yield self.data[start : start + self.CHUNK]
            self.loop.call_soon_threadsafe(self.callback, min(start + self.CHUNK, total), total)


# ======================================================================
# Request observers (DevTools' Network panel)
# ======================================================================

_observers: List[Callable[[Dict[str, Any]], None]] = []
_request_ids = itertools.count(1)
_PREVIEW_BYTES = 4096


def observe_requests(callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
    """Receive a record for every [`fetch`][pythonnative.net.fetch] request.

    The devtools agent subscribes in development builds. ``callback``
    gets two records per request on the application loop: one when it
    starts (``"phase": "start"``) and one when it finishes (``"end"`` or
    ``"error"``), sharing an ``id``. Bodies are previewed up to 4 KB.

    Returns:
        A callable that removes the observer.
    """
    _observers.append(callback)

    def remove() -> None:
        try:
            _observers.remove(callback)
        except ValueError:
            pass

    return remove


def _preview(data: Optional[bytes]) -> Optional[str]:
    if not data:
        return None
    clipped = data[:_PREVIEW_BYTES]
    try:
        text = clipped.decode("utf-8")
    except UnicodeDecodeError:
        return f"<{len(data)} bytes of binary data>"
    return text + ("…" if len(data) > _PREVIEW_BYTES else "")


def _notify(record: Dict[str, Any]) -> None:
    for callback in list(_observers):
        try:
            callback(record)
        except Exception:
            pass


async def _observed(request: urllib.request.Request, timeout: float, stream: bool = False) -> Response:
    request_id = next(_request_ids)
    started = time.time()
    data = request.data
    body = data.data if isinstance(data, _ProgressBody) else data if isinstance(data, bytes) else None
    _notify(
        {
            "id": request_id,
            "phase": "start",
            "method": request.get_method(),
            "url": request.full_url,
            "request_headers": dict(request.header_items()),
            "request_body": _preview(body),
            "request_size": len(body) if body else 0,
            "started": started,
        }
    )
    try:
        response = await asyncio.to_thread(_dispatch_request, request, timeout, stream)
    except BaseException as exc:
        _notify(
            {
                "id": request_id,
                "phase": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": round((time.time() - started) * 1000.0, 1),
            }
        )
        raise
    _notify(
        {
            "id": request_id,
            "phase": "end",
            "status": response.status,
            "url": response.url,
            "response_headers": dict(response.headers),
            "response_body": _preview(response.content),
            "response_size": len(response.content),
            "duration_ms": round((time.time() - started) * 1000.0, 1),
        }
    )
    return response


def _build_request(
    *,
    url: str,
    method: str,
    headers: Optional[Mapping[str, str]],
    body: Union[bytes, str, Mapping[str, Any], None],
    params: Optional[Mapping[str, Any]],
    files: Optional[Mapping[str, UploadFile]] = None,
) -> urllib.request.Request:
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params, doseq=True)

    header_dict: Dict[str, str] = dict(headers or {})
    payload: Optional[bytes] = None
    if files:
        if body is not None and not isinstance(body, Mapping):
            raise TypeError("With files=, body must be a mapping of form fields.")
        payload, content_type = _encode_multipart(body or {}, files)
        header_dict["Content-Type"] = content_type
    elif body is None:
        pass
    elif isinstance(body, (bytes, bytearray)):
        payload = bytes(body)
    elif isinstance(body, str):
        payload = body.encode("utf-8")
    elif isinstance(body, Mapping):
        payload = json.dumps(body, default=str).encode("utf-8")
        if not any(name.lower() == "content-type" for name in header_dict):
            header_dict["Content-Type"] = "application/json"
    else:
        raise TypeError(f"Unsupported body type: {type(body)!r}")

    return urllib.request.Request(
        url=url,
        data=payload,
        method=method.upper(),
        headers=header_dict,
    )


def _encode_multipart(fields: Mapping[str, Any], files: Mapping[str, UploadFile]) -> Tuple[bytes, str]:
    """Encode a ``multipart/form-data`` body, returning it and its ``Content-Type``."""
    boundary = f"pythonnative{os.urandom(16).hex()}"

    def escaped(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "%0D").replace("\n", "%0A")

    parts: List[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{escaped(name)}"\r\n\r\n'.encode()
            + str(value).encode("utf-8")
            + b"\r\n"
        )
    for name, file in files.items():
        if isinstance(file, tuple):
            filename, content, content_type = file
        else:
            content = file
            filename = file.name if isinstance(file, Path) else name
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        data = content.read_bytes() if isinstance(content, Path) else bytes(content)
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{escaped(name)}"; '
                f'filename="{escaped(filename)}"\r\nContent-Type: {content_type}\r\n\r\n'
            ).encode()
            + data
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _dispatch_request(request: urllib.request.Request, timeout: float, stream: bool = False) -> Response:
    context = _default_ssl_context
    data = request.data
    if isinstance(data, _ProgressBody):
        # urllib would chunk an iterable body with no declared length.
        request.add_unredirected_header("Content-Length", str(len(data.data)))
    try:
        if stream:
            resp = urllib.request.urlopen(request, timeout=timeout, context=context)
            return Response(
                status=resp.status,
                url=resp.geturl(),
                headers={k: v for k, v in resp.headers.items()},
                _stream=resp,
            )
        with urllib.request.urlopen(request, timeout=timeout, context=context) as resp:
            content = resp.read()
            return Response(
                status=resp.status,
                url=resp.geturl(),
                headers={k: v for k, v in resp.headers.items()},
                content=content,
            )
    except urllib.error.HTTPError as exc:
        # HTTPError is itself a response object; propagate the body
        # so callers can inspect it before deciding to raise.
        body = exc.read() if hasattr(exc, "read") else b""
        return Response(
            status=exc.code,
            url=getattr(exc, "url", request.full_url),
            headers={k: v for k, v in (exc.headers or {}).items()},
            content=body,
        )
    except urllib.error.URLError as exc:
        # Convert urllib's TimeoutError wrapper into a plain TimeoutError
        # so callers get a recognisable exception type.
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            raise reason
        raise OSError(str(reason)) from exc


__all__ = ["fetch", "default_ssl_context", "Response", "HTTPError", "UploadFile", "set_default_ssl_context"]
