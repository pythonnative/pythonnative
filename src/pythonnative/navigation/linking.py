"""Deep links derived from the navigator tree.

Each [`Screen`][pythonnative.Screen] may declare a ``path`` with Python
format placeholders for its params. A nested navigator's path prefixes
the paths of its screens:

```python
Tabs = pn.TabNavigator(
    pn.Screen(FeedScreen, path="feed"),
    pn.Screen(ProfileScreen, path="users/{user}"),
    name="Main",
)
Root = pn.StackNavigator(
    pn.Screen(Tabs),
    pn.Screen(ItemScreen, path="items/{id}"),
)

pn.NavigationContainer(Root, link_prefixes=["myapp://", "https://example.com"])
```

``myapp://items/42?tab=reviews`` opens ``ItemScreen(id=42, tab="reviews")``:
path placeholders and query parameters become the screen component's
arguments, converted with its annotations (``str``, ``int``, ``float``,
``bool``, ``Enum`` subclasses, ``Literal`` values, and ``Optional`` of
those). Query parameters the component doesn't accept are ignored. A
URL whose values don't convert, or that lacks a required parameter,
matches nothing.

Path placeholders arrive percent-decoded, once, before conversion, so
``users/Ada%20Lovelace`` gives ``user="Ada Lovelace"`` and an encoded
``%2F`` stays inside one value instead of splitting the path. A ``+`` in
a path is a literal plus, unlike in the query string, where it means a
space. Bytes that don't decode as UTF-8 are left as they arrived.
Literal segments are matched exactly as written.

A placeholder stands for one non-empty segment when a URL is built:
a route whose placeholder value is empty or absent yields ``None``
rather than a URL with an empty segment. Reading is narrower. An
*interior* empty segment never reaches a screen, so ``org//repo/pn``
matches nothing instead of shifting its values onto a shorter route. A
*leading or trailing* empty segment can't be told apart from the
leading or trailing slash that URLs may always carry, so it is
discarded with that slash: ``u/`` is read as ``u``, and may still match
some other route. An empty query value is unaffected.
"""

from __future__ import annotations

import enum
import inspect
import types
import typing
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

from ..component import Component
from .screen import Screen
from .state import NavigationState, Route

if TYPE_CHECKING:
    from .navigators import Navigator

__all__ = ["LinkTable"]

Converter = Callable[[str], Any]

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def converter_for(hint: Any) -> Converter:
    """Return a ``str -> value`` converter for a parameter annotation."""
    origin = typing.get_origin(hint)
    if origin is typing.Union or origin is types.UnionType:
        options = [arg for arg in typing.get_args(hint) if arg is not type(None)]
        converters = [converter_for(arg) for arg in options]

        def union(value: str) -> Any:
            for convert in converters:
                try:
                    return convert(value)
                except (TypeError, ValueError, KeyError):
                    continue
            raise ValueError(f"{value!r} doesn't match {hint!r}")

        return union
    if origin is typing.Literal:
        choices = typing.get_args(hint)

        def literal(value: str) -> Any:
            for choice in choices:
                if str(choice) == value:
                    return choice
            raise ValueError(f"{value!r} isn't one of {choices!r}")

        return literal
    if origin is typing.Annotated:
        return converter_for(typing.get_args(hint)[0])
    if hint is bool:
        return _parse_bool
    if hint in (int, float, str):
        return typing.cast(Converter, hint)
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        enum_type = hint

        def enum_value(value: str) -> Any:
            for member in enum_type:
                if str(member.value) == value or member.name == value:
                    return member
            raise ValueError(f"{value!r} isn't a {enum_type.__name__}")

        return enum_value
    return str


def _stringify(value: Any) -> str:
    if isinstance(value, enum.Enum):
        return str(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _decode(segment: str) -> str:
    """Percent-decode one captured path segment, or return it unchanged.

    Strict decoding with a fallback to the raw segment is
    non-regressive: a segment whose bytes aren't valid UTF-8 (``%FF``,
    Latin-1 ``caf%E9``) reads back exactly as it does without any
    decoding, where ``errors="replace"`` would overwrite it with U+FFFD
    and lose information that can't be recovered.

    The fallback hands the converter the raw segment, and the converter
    then applies its ordinary rules: a ``str`` param keeps it, an ``int``
    param rejects it so the pattern doesn't match, and a ``Literal`` or
    ``Enum`` param matches only when one of its declared values equals
    the raw text.

    Args:
        segment: One path segment, already split on ``/``, so an encoded
            ``%2F`` decodes to a slash inside the value.

    Returns:
        The decoded segment, or ``segment`` itself when it isn't valid
        UTF-8.
    """
    try:
        return unquote(segment, errors="strict")
    except UnicodeDecodeError:
        return segment


class _Param:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class _Pattern:
    """A path pattern that opens the last screen of ``chain``."""

    __slots__ = ("chain", "segments", "converters", "accepts", "required", "open_query")

    def __init__(self, chain: Tuple[Screen, ...], segments: Tuple[Union[str, _Param], ...]) -> None:
        self.chain = chain
        self.segments = segments
        leaf = chain[-1].component
        self.converters: Dict[str, Converter] = {}
        self.accepts: set[str] = set()
        self.required: set[str] = set()
        self.open_query = False
        if isinstance(leaf, Component):
            try:
                hints = typing.get_type_hints(leaf.fn)
            except Exception:
                hints = {}
            for name, parameter in inspect.signature(leaf.fn).parameters.items():
                if parameter.kind is parameter.VAR_KEYWORD:
                    self.open_query = True
                    continue
                if parameter.kind is parameter.VAR_POSITIONAL:
                    continue
                self.accepts.add(name)
                self.converters[name] = converter_for(hints.get(name, str))
                if parameter.default is inspect.Parameter.empty:
                    self.required.add(name)
        for segment in segments:
            if isinstance(segment, _Param) and segment.name not in self.accepts and not self.open_query:
                raise ValueError(
                    f"Deep-link path of screen {chain[-1].name!r} names {{{segment.name}}}, "
                    "which isn't a parameter of its component"
                )

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(screen.name for screen in self.chain)

    def match(self, parts: Sequence[str], query: Dict[str, str]) -> Optional[Dict[str, Any]]:
        if len(parts) != len(self.segments):
            return None
        raw: Dict[str, str] = {}
        for pattern, actual in zip(self.segments, parts):
            if isinstance(pattern, _Param):
                # A placeholder never captures nothing. The split below keeps
                # interior empty segments, so ``org//repo/pn`` arrives with an
                # empty capture rather than one segment short, and rejecting it
                # here stops it reaching a screen with shifted values. Tested
                # before the decode, because only ``""`` decodes to ``""``.
                if not actual:
                    return None
                # Only captured values are decoded, and only here. Decoding
                # in the conversion loop below would decode query values a
                # second time, since ``parse_qsl`` has already decoded them.
                raw[pattern.name] = _decode(actual)
            elif pattern != actual:
                return None
        for key, value in query.items():
            if key not in raw and (key in self.accepts or self.open_query):
                raw[key] = value
        if not self.required <= raw.keys():
            return None
        params: Dict[str, Any] = {}
        for key, value in raw.items():
            convert = self.converters.get(key, str)
            try:
                params[key] = convert(value)
            except (TypeError, ValueError, KeyError):
                return None
        return params


def _split_path(path: Optional[str]) -> Tuple[Union[str, _Param], ...]:
    if not path:
        return ()
    segments: List[Union[str, _Param]] = []
    for part in path.strip("/").split("/"):
        if not part:
            continue
        if part.startswith("{") and part.endswith("}") and part[1:-1].isidentifier():
            segments.append(_Param(part[1:-1]))
        elif "{" in part or "}" in part:
            raise ValueError(f"Deep-link path segment {part!r} must be a literal or a whole {{param}} placeholder")
        else:
            segments.append(part)
    return tuple(segments)


class LinkTable:
    """URL <-> navigation state mapping built from a navigator tree.

    Path placeholders are percent-decoded once, where the segment is
    captured and before conversion; ``+`` in a path stays a literal plus,
    and undecodable bytes are left as-is. Literal segments match exactly
    as the paths declare them, and query values are decoded by
    ``parse_qsl`` alone.

    A path placeholder never captures an empty value. ``url_from_state``
    returns ``None`` rather than emitting an empty segment, and an
    interior empty segment in a URL matches nothing. A leading or
    trailing slash stays optional, so a boundary empty is discarded
    along with it and the shortened path may still match another route:
    ``u/`` is read as ``u``. Query values are unconstrained, so an empty
    one round-trips as ``key=``.

    Args:
        navigator: The root navigator.
        prefixes: URL prefixes the app answers to (schemes such as
            ``"myapp://"`` or web origins). Matching is case-insensitive
            and a trailing slash is optional.

    Raises:
        ValueError: If a path names a placeholder its component doesn't
            accept, or a segment mixes literal text with a placeholder.
    """

    def __init__(self, navigator: "Navigator", prefixes: Sequence[str]) -> None:
        self.prefixes: Tuple[str, ...] = tuple(p if p.endswith("://") else p.rstrip("/") for p in prefixes)
        self._patterns: List[_Pattern] = []
        self._collect(navigator, (), ())
        # Longer patterns first so literal segments win over ``{param}`` catch-alls.
        self._patterns.sort(key=lambda p: (-len(p.segments), sum(isinstance(s, _Param) for s in p.segments)))

    def _collect(
        self, navigator: "Navigator", chain: Tuple[Screen, ...], prefix: Tuple[Union[str, _Param], ...]
    ) -> None:
        for screen in navigator.screens:
            here = chain + (screen,)
            segments = prefix + _split_path(screen.path)
            nested = screen.navigator
            if nested is not None:
                self._collect(nested, here, segments)
            elif screen.path is not None:
                self._patterns.append(_Pattern(here, segments))

    # ------------------------------------------------------------------
    # URL -> state
    # ------------------------------------------------------------------

    def strip_prefix(self, url: str) -> Optional[str]:
        """Return the path and query of ``url`` if it matches a prefix (or is relative), else ``None``."""
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
        # Strip the slashes that bound the path, then keep every segment
        # between them: an interior empty survives for ``match`` to reject,
        # while a leading or trailing slash stays optional as before.
        body = split.path.strip("/")
        parts = tuple(body.split("/")) if body else ()
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        for pattern in self._patterns:
            params = pattern.match(parts, query)
            if params is not None:
                return _nest(pattern.names, params)
        return None

    # ------------------------------------------------------------------
    # State -> URL
    # ------------------------------------------------------------------

    def url_from_state(self, state: NavigationState) -> Optional[str]:
        """Build a URL for the focused leaf of ``state``.

        Returns:
            The URL, or ``None`` when it can't be built: no screen on the
            way has a path, the route chain isn't in the table, or a path
            placeholder's value is empty or absent. A placeholder has to
            become a non-empty segment, since an empty one either shifts
            the remaining values onto another route or is discarded with a
            boundary slash. Emptiness is judged on the serialized text, so
            ``0`` and ``False`` are fine while a value that stringifies to
            ``""`` is not. An empty *query* value round-trips as ``key=``.
        """
        chain: List[Route] = []
        cursor: Optional[NavigationState] = state
        while cursor is not None:
            chain.append(cursor.current)
            cursor = cursor.current.state
        names = tuple(route.name for route in chain)
        pattern = next((p for p in self._patterns if p.names == names), None)
        if pattern is None:
            return None
        params = dict(chain[-1].params)
        segments: List[str] = []
        for segment in pattern.segments:
            if isinstance(segment, _Param):
                # An empty value would collapse into an empty segment, which
                # reads back as a different route or as nothing at all, so
                # decline the URL the way an unknown route already does. A
                # missing key stringifies to the same empty text, and both
                # answers are ``None``, so they need not be told apart.
                text = quote(_stringify(params.pop(segment.name, "")), safe="")
                if not text:
                    return None
                segments.append(text)
            else:
                segments.append(segment)
        path = "/".join(segments)
        query = urlencode({key: _stringify(value) for key, value in params.items()})
        base = self.prefixes[0] if self.prefixes else ""
        joiner = "" if base.endswith("://") or not base else "/"
        url = f"{base}{joiner}{path}"
        return f"{url}?{query}" if query else url


def _nest(names: Tuple[str, ...], params: Dict[str, Any]) -> NavigationState:
    """Build ``Route(names[0], state=Route(names[1], ... params))`` from the outside in."""
    state = NavigationState([Route(names[-1], params)])
    for name in reversed(names[:-1]):
        state = NavigationState([Route(name, state=state)])
    return state
