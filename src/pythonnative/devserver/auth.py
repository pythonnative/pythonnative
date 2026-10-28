"""The per-user development token that guards the dev server.

``pn start`` serves the application's source code, so everything that
reads it has to prove it belongs to the developer running the server.
The proof is a random token generated once per user and stored with mode
``0600`` in ``~/.pythonnative/dev-token``. It's reused across restarts, so
debug builds that ``pn run`` launched keep connecting after the server
restarts. Delete the file to issue a new token; every client then needs
the new URL.

Clients present the token in one of three ways (see
[`request_token`][pythonnative.devserver.auth.request_token]):

- the ``token`` query parameter (``pn run`` bakes it into the dev-client
  URL, and ``pn start`` prints it in the preview URL),
- the ``X-PN-Token`` header, or
- the ``pn_token`` cookie, which the browser preview receives once in
  exchange for the query parameter.

Two environment variables override the stored token:
``PN_DEV_TOKEN`` supplies the token itself, and ``PN_DEV_TOKEN_FILE``
points at a different token file.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

__all__ = [
    "COOKIE_NAME",
    "HEADER_NAME",
    "QUERY_PARAM",
    "TOKEN_ENV",
    "TOKEN_FILE_ENV",
    "load_token",
    "request_token",
    "token_matches",
    "token_path",
    "token_source",
    "with_token",
]

TOKEN_ENV = "PN_DEV_TOKEN"
"""Environment variable that supplies the token directly (skips the file)."""

TOKEN_FILE_ENV = "PN_DEV_TOKEN_FILE"
"""Environment variable naming the token file (default ``~/.pythonnative/dev-token``)."""

QUERY_PARAM = "token"
"""Query parameter that carries the token in URLs."""

HEADER_NAME = "X-PN-Token"
"""Request header that carries the token."""

COOKIE_NAME = "pn_token"
"""Cookie the browser preview holds after exchanging the query parameter."""


def token_path() -> Path:
    """Where the token lives: ``$PN_DEV_TOKEN_FILE`` or ``~/.pythonnative/dev-token``."""
    override = os.environ.get(TOKEN_FILE_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".pythonnative" / "dev-token"


def token_source() -> str:
    """Where [`load_token`][pythonnative.devserver.auth.load_token] gets the token, for messages."""
    return f"${TOKEN_ENV}" if os.environ.get(TOKEN_ENV, "").strip() else str(token_path())


def load_token() -> str:
    """Return this user's dev token, creating it on first use.

    ``PN_DEV_TOKEN`` wins when set. Otherwise the token file is read, or
    created with mode ``0600`` (its directory with ``0700``) holding
    ``secrets.token_urlsafe(24)``. A file that other users can read is
    tightened to ``0600``; an empty one is replaced.
    """
    explicit = os.environ.get(TOKEN_ENV, "").strip()
    if explicit:
        return explicit
    path = token_path()
    existing = _read(path)
    if existing:
        return existing
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Another process created it first (or it exists but is empty).
        existing = _read(path)
        if existing:
            return existing
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    _restrict(path)
    return token


def _read(path: Path) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if text:
        _restrict(path)
    return text or None


def _restrict(path: Path) -> None:
    try:
        if path.stat().st_mode & 0o077:
            os.chmod(path, 0o600)
    except OSError:
        pass


def token_matches(candidate: Optional[str], token: str) -> bool:
    """Compare ``candidate`` against ``token`` in constant time."""
    if not candidate:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), token.encode("utf-8"))


def request_token(headers: Dict[str, str], query: Dict[str, str]) -> Optional[str]:
    """The token a request presents, if any.

    Checks the ``token`` query parameter, then the ``X-PN-Token`` header,
    then the ``pn_token`` cookie. ``headers`` must have lower-cased names.
    """
    for value in (query.get(QUERY_PARAM), headers.get(HEADER_NAME.lower()), _cookie(headers.get("cookie", ""))):
        if value:
            return value
    return None


def _cookie(header: str) -> Optional[str]:
    for part in header.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name == COOKIE_NAME:
            return value.strip().strip('"') or None
    return None


def with_token(url: str, token: str) -> str:
    """Return ``url`` with its ``token`` query parameter set to ``token``."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != QUERY_PARAM]
    query.append((QUERY_PARAM, token))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
