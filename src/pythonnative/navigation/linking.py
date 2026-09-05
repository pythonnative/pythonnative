"""Deep-link configuration: map URLs to navigation state and back.

```python
linking = pn.LinkingConfig(
    prefixes=["myapp://", "https://example.com"],
    screens={
        "Home": "",
        "Detail": {"path": "item/:id", "parse": {"id": int}},
        "Tabs": {
            "path": "tabs",
            "screens": {"Feed": "feed", "Profile": "me/:user"},
        },
    },
)
```

Pass it to [`NavigationContainer`][pythonnative.NavigationContainer]
and every URL the app opens with (cold start or while running) becomes
a ``navigate`` on the root navigator. Each screen entry is either a
path pattern (``"item/:id"``, where ``:name`` segments capture params
and the query string supplies the rest) or a dict with ``path``,
``parse`` (per-param converters), and ``screens`` for a nested
navigator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from .state import NavigationState, Route

__all__ = ["LinkingConfig"]

ScreenPathConfig = Union[str, Mapping[str, Any]]


class _Pattern:
    __slots__ = ("names", "segments", "parse", "stringify")

    def __init__(
        self,
        names: Tuple[str, ...],
        segments: Tuple[str, ...],
        parse: Mapping[str, Callable[[str], Any]],
        stringify: Mapping[str, Callable[[Any], str]],
    ) -> None:
        self.names = names
        self.segments = segments
        self.parse = dict(parse)
        self.stringify = dict(stringify)

    def match(self, parts: Sequence[str]) -> Optional[Dict[str, Any]]:
        if len(parts) != len(self.segments):
            return None
        params: Dict[str, Any] = {}
        for pattern, actual in zip(self.segments, parts):
            if pattern.startswith(":"):
                params[pattern[1:]] = actual
            elif pattern != actual:
                return None
        return params


class LinkingConfig:
    """URL <-> navigation state mapping for a navigator tree.

    Args:
        prefixes: URL prefixes this app answers to (schemes such as
            ``"myapp://"`` or web origins). Matching is case-insensitive
            and a trailing slash is optional.
        screens: Route name -> path pattern or nested config (see the
            module docstring).
    """

    def __init__(self, prefixes: Sequence[str], screens: Mapping[str, ScreenPathConfig]) -> None:
        self.prefixes: Tuple[str, ...] = tuple(p if p.endswith("://") else p.rstrip("/") for p in prefixes)
        self.screens = dict(screens)
        self._patterns: List[_Pattern] = []
        self._collect((), (), self.screens)
        # Longer patterns first so literal segments win over ``:param`` catch-alls.
        self._patterns.sort(key=lambda p: (-len(p.segments), sum(s.startswith(":") for s in p.segments)))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _collect(
        self, names: Tuple[str, ...], prefix: Tuple[str, ...], screens: Mapping[str, ScreenPathConfig]
    ) -> None:
        for name, config in screens.items():
            if isinstance(config, str):
                path, nested = config, None
                parse: Mapping[str, Callable[[str], Any]] = {}
                stringify: Mapping[str, Callable[[Any], str]] = {}
            else:
                path = config.get("path")
                parse = config.get("parse") or {}
                stringify = config.get("stringify") or {}
                nested = config.get("screens")
            chain = names + (name,)
            segments = prefix + _split_path(path) if path is not None else prefix
            if path is not None:
                self._patterns.append(_Pattern(chain, segments, parse, stringify))
            if nested:
                self._collect(chain, segments, nested)

    # ------------------------------------------------------------------
    # URL -> state
    # ------------------------------------------------------------------

    def strip_prefix(self, url: str) -> Optional[str]:
        """Return the path+query portion of ``url`` if it matches a prefix, else ``None``."""
        lowered = url.lower()
        for prefix in self.prefixes:
            low_prefix = prefix.lower()
            if low_prefix.endswith("://"):
                if lowered.startswith(low_prefix):
                    return url[len(prefix) :]
            elif lowered == low_prefix or lowered.startswith(low_prefix + "/") or lowered.startswith(low_prefix + "?"):
                return url[len(prefix) :]
        if "://" not in url and not url.startswith("//"):
            return url
        return None

    def state_from_url(self, url: str) -> Optional[NavigationState]:
        """Translate ``url`` into a (possibly nested) state, or ``None`` when nothing matches."""
        rest = self.strip_prefix(url)
        if rest is None:
            return None
        split = urlsplit(rest if rest.startswith("/") else "/" + rest)
        parts = _split_path(split.path)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        for pattern in self._patterns:
            matched = pattern.match(parts)
            if matched is None:
                continue
            params = {**query, **matched}
            for key, convert in pattern.parse.items():
                if key in params:
                    try:
                        params[key] = convert(params[key])
                    except Exception:
                        pass
            return _nest(pattern.names, params)
        return None

    # ------------------------------------------------------------------
    # State -> URL
    # ------------------------------------------------------------------

    def url_from_state(self, state: NavigationState) -> Optional[str]:
        """Build a URL for the focused leaf of ``state`` (``None`` if it has no path)."""
        chain: List[Route] = []
        cursor: Optional[NavigationState] = state
        while cursor is not None:
            chain.append(cursor.current)
            cursor = cursor.current.state
        names = tuple(r.name for r in chain)
        pattern = next((p for p in self._patterns if p.names == names), None)
        if pattern is None:
            # Fall back to the deepest ancestor that has a path.
            for depth in range(len(names) - 1, 0, -1):
                pattern = next((p for p in self._patterns if p.names == names[:depth]), None)
                if pattern is not None:
                    chain = chain[:depth]
                    break
        if pattern is None:
            return None
        params = dict(chain[-1].params)
        segments = []
        for seg in pattern.segments:
            if seg.startswith(":"):
                key = seg[1:]
                value = params.pop(key, "")
                convert = pattern.stringify.get(key, str)
                segments.append(quote(convert(value), safe=""))
            else:
                segments.append(seg)
        path = "/".join(segments)
        query = urlencode({k: str(v) for k, v in params.items()})
        base = self.prefixes[0] if self.prefixes else ""
        joiner = "" if base.endswith("://") or not base else "/"
        url = f"{base}{joiner}{path}"
        return f"{url}?{query}" if query else url


def _split_path(path: Optional[str]) -> Tuple[str, ...]:
    if not path:
        return ()
    return tuple(p for p in path.strip("/").split("/") if p)


def _nest(names: Tuple[str, ...], params: Dict[str, Any]) -> NavigationState:
    """Build ``Route(names[0], state=Route(names[1], ... params))`` from the outside in."""
    leaf = Route(names[-1], params)
    state = NavigationState([leaf])
    for name in reversed(names[:-1]):
        state = NavigationState([Route(name, state=state)])
    return state
