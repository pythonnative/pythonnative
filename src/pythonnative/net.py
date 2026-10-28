"""Async HTTP client (``pn.fetch``).

A small, dependency-free coroutine wrapper around
:mod:`urllib.request`. Operates on bytes internally and exposes a
:class:`Response` with `text()`, `json()`, and `bytes` accessors.

The implementation is deliberately minimal; it covers the
"call a JSON API" path that's overwhelmingly the use case for mobile
apps. For streaming, multipart uploads, or HTTP/2, integrate
``httpx`` / ``aiohttp`` directly; this module won't try to compete.

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
    ```
"""

from __future__ import annotations

import asyncio
import itertools
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

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
        content: Raw response body.
    """

    status: int
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes = b""

    @property
    def ok(self) -> bool:
        """``True`` if the status is in the 2xx range."""
        return 200 <= self.status < 300

    def __repr__(self) -> str:
        cls = type(self).__name__
        return f"{cls}(status={self.status}, url={self.url!r}, ok={self.ok}, content={len(self.content)} bytes)"

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


async def fetch(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Mapping[str, str]] = None,
    body: Union[bytes, str, Mapping[str, Any], None] = None,
    params: Optional[Mapping[str, Any]] = None,
    timeout: float = 30.0,
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
    request = _build_request(url=url, method=method, headers=headers, body=body, params=params)
    if not _observers:
        return await asyncio.to_thread(_dispatch_request, request, timeout)
    return await _observed(request, timeout)


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


async def _observed(request: urllib.request.Request, timeout: float) -> Response:
    request_id = next(_request_ids)
    started = time.time()
    body = request.data if isinstance(request.data, bytes) else None
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
        response = await asyncio.to_thread(_dispatch_request, request, timeout)
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
) -> urllib.request.Request:
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params, doseq=True)

    header_dict: Dict[str, str] = dict(headers or {})
    payload: Optional[bytes] = None
    if body is None:
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


def _dispatch_request(request: urllib.request.Request, timeout: float) -> Response:
    context = _default_ssl_context
    try:
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


__all__ = ["fetch", "Response", "HTTPError", "set_default_ssl_context"]
