"""Immutable navigation state and the pure operations on it.

A navigator's state is a [`NavigationState`][pythonnative.navigation.NavigationState]:
an ordered tuple of [`Route`][pythonnative.navigation.Route] entries
plus the index of the active one. Stack navigators treat the tuple as
a history (the active route is always the last); tab and drawer
navigators keep one route per screen and move the index.

Every operation returns a new state, so navigators can store the state
in ``use_state`` and diff it like any other value. States serialize to
plain dicts (``to_dict`` / ``from_dict``) so a native host can hand a
pushed screen the full history it belongs to.
"""

from __future__ import annotations

import itertools
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Sequence, Tuple, cast

__all__ = ["NavigationState", "Route", "RouteParams"]

type RouteParams = Mapping[str, Any]
"""Bound for the ``P`` type parameter of [`Route`][pythonnative.navigation.Route].

Declare a screen's params as a ``TypedDict`` and read them with
``use_route(MyParams)`` for a fully typed ``route.params``.
"""

_route_keys = itertools.count(1)


def _new_key(name: str) -> str:
    return f"{name}-{next(_route_keys)}"


class Route[P: RouteParams = Dict[str, Any]]:
    """One entry in a navigator's state.

    ``Route`` is generic in its params type. Bare ``Route`` is
    ``Route[dict[str, Any]]``; pass a ``TypedDict`` to
    [`use_route`][pythonnative.use_route] to get ``Route[MyParams]``
    with a typed ``params`` attribute:

    ```python
    class DetailParams(TypedDict):
        id: int

    route = pn.use_route(DetailParams)
    route.params["id"]  # int
    ```

    Attributes:
        name: The screen name this route renders.
        params: Parameters passed to the screen (read with
            [`use_route`][pythonnative.use_route]). Always a plain
            ``dict`` at runtime.
        key: Stable identity for this particular visit to the screen,
            unique per process. Two pushes of the same screen have
            different keys, so their component state never mixes.
        state: Seed state for a navigator rendered by this screen
            (set by ``navigate("Tabs", screen="Profile")`` and by deep
            links). ``None`` for ordinary screens.
    """

    __slots__ = ("name", "params", "key", "state")

    def __init__(
        self,
        name: str,
        params: Optional[Mapping[str, Any]] = None,
        key: Optional[str] = None,
        state: Optional["NavigationState"] = None,
    ) -> None:
        self.name = name
        self.params: P = cast(P, dict(params or {}))
        self.key = key or _new_key(name)
        self.state = state

    def with_params(self, params: Mapping[str, Any], *, merge: bool = True) -> "Route[P]":
        """Return a copy carrying ``params`` (merged over the current ones by default)."""
        merged = {**self.params, **params} if merge else dict(params)
        return Route(self.name, merged, key=self.key, state=self.state)

    def with_state(self, state: Optional["NavigationState"]) -> "Route[P]":
        """Return a copy carrying a nested navigator seed ``state``."""
        return Route(self.name, self.params, key=self.key, state=state)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (``name``, ``params``, ``key``, and ``state`` when nested)."""
        out: Dict[str, Any] = {"name": self.name, "params": dict(self.params), "key": self.key}
        if self.state is not None:
            out["state"] = self.state.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Route[Dict[str, Any]]":
        """Rebuild a route from ``to_dict`` output, keeping its ``key`` so component state carries over."""
        params = data.get("params")
        nested = data.get("state")
        return Route(
            str(data["name"]),
            params if isinstance(params, Mapping) else {},
            key=data.get("key"),
            state=NavigationState.from_dict(nested) if isinstance(nested, Mapping) and nested.get("routes") else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Route):
            return NotImplemented
        return (
            self.name == other.name
            and self.params == other.params
            and self.key == other.key
            and self.state == other.state
        )

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"Route({self.name!r}, params={self.params!r}, key={self.key!r})"


class NavigationState:
    """Immutable ordered routes plus the active index.

    Attributes:
        routes: The routes, oldest first.
        index: Position of the active route in ``routes``.
    """

    __slots__ = ("routes", "index")

    def __init__(self, routes: Iterable[Route], index: Optional[int] = None) -> None:
        self.routes: Tuple[Route, ...] = tuple(routes)
        if not self.routes:
            raise ValueError("NavigationState needs at least one route")
        self.index = len(self.routes) - 1 if index is None else index
        if not 0 <= self.index < len(self.routes):
            raise IndexError(f"index {self.index} out of range for {len(self.routes)} route(s)")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def current(self) -> Route:
        """The active route."""
        return self.routes[self.index]

    @property
    def can_go_back(self) -> bool:
        """Whether a route precedes the active one."""
        return self.index > 0

    def find(self, name: str) -> Optional[int]:
        """Index of the most recent route named ``name``, or ``None``."""
        for i in range(len(self.routes) - 1, -1, -1):
            if self.routes[i].name == name:
                return i
        return None

    def __len__(self) -> int:
        return len(self.routes)

    def __iter__(self) -> Iterator[Route]:
        return iter(self.routes)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NavigationState):
            return NotImplemented
        return self.routes == other.routes and self.index == other.index

    def __repr__(self) -> str:
        names = [r.name for r in self.routes]
        return f"NavigationState({names!r}, index={self.index})"

    # ------------------------------------------------------------------
    # Stack operations (history semantics)
    # ------------------------------------------------------------------

    def push(
        self, name: str, params: Optional[Mapping[str, Any]] = None, state: Optional["NavigationState"] = None
    ) -> "NavigationState":
        """Append a new route and make it active (drops any forward entries)."""
        kept = self.routes[: self.index + 1]
        return NavigationState(kept + (Route(name, params, state=state),))

    def pop(self, count: int = 1) -> "NavigationState":
        """Remove up to ``count`` routes from the end (never below one)."""
        keep = max(1, len(self.routes) - max(0, count))
        return NavigationState(self.routes[:keep])

    def pop_to_top(self) -> "NavigationState":
        """Keep only the first route."""
        return NavigationState(self.routes[:1])

    def pop_to(
        self, name: str, params: Optional[Mapping[str, Any]] = None, state: Optional["NavigationState"] = None
    ) -> "NavigationState":
        """Pop back to the most recent route named ``name``, merging ``params`` into it."""
        idx = self.find(name)
        if idx is None:
            raise KeyError(name)
        routes = list(self.routes[: idx + 1])
        if params:
            routes[-1] = routes[-1].with_params(params)
        if state is not None:
            routes[-1] = routes[-1].with_state(state)
        return NavigationState(routes)

    def replace(
        self, name: str, params: Optional[Mapping[str, Any]] = None, state: Optional["NavigationState"] = None
    ) -> "NavigationState":
        """Swap the active route for a fresh one (new key, so state resets)."""
        routes = list(self.routes)
        routes[self.index] = Route(name, params, state=state)
        return NavigationState(routes, self.index)

    def navigate(
        self, name: str, params: Optional[Mapping[str, Any]] = None, state: Optional["NavigationState"] = None
    ) -> "NavigationState":
        """Go to ``name``: pop back to it if it's in the history, else push it."""
        if self.find(name) is not None:
            return self.pop_to(name, params, state)
        return self.push(name, params, state)

    # ------------------------------------------------------------------
    # Tab / drawer operations (one route per screen)
    # ------------------------------------------------------------------

    def jump_to(
        self, name: str, params: Optional[Mapping[str, Any]] = None, state: Optional["NavigationState"] = None
    ) -> "NavigationState":
        """Activate the route named ``name`` in place, merging ``params``."""
        idx = self.find(name)
        if idx is None:
            raise KeyError(name)
        routes = list(self.routes)
        if params:
            routes[idx] = routes[idx].with_params(params)
        if state is not None:
            routes[idx] = routes[idx].with_state(state)
        return NavigationState(routes, idx)

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    def set_params(self, params: Mapping[str, Any]) -> "NavigationState":
        """Merge ``params`` into the active route."""
        routes = list(self.routes)
        routes[self.index] = routes[self.index].with_params(params)
        return NavigationState(routes, self.index)

    def reset(self, routes: Sequence[Route], index: Optional[int] = None) -> "NavigationState":
        """Return a state holding exactly ``routes`` with ``index`` active (the last route by default)."""
        return NavigationState(routes, index)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict with ``routes`` (each via ``Route.to_dict``) and ``index``."""
        return {"routes": [r.to_dict() for r in self.routes], "index": self.index}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavigationState":
        """Rebuild a state from ``to_dict`` output; a missing ``index`` activates the last route."""
        routes = [Route.from_dict(r) for r in data.get("routes", [])]
        index = data.get("index")
        return cls(routes, int(index) if isinstance(index, int) else None)
