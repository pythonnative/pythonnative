"""Testing Library-style queries over a tree of fake views.

[`Queries`][pythonnative.testing.queries.Queries] is the mixin behind
[`RenderResult`][pythonnative.testing.RenderResult] and the scoped object
returned by [`within`][pythonnative.testing.within]. Every query comes in
four flavors:

- ``get_by_*`` returns exactly one match or raises ``LookupError`` with
  the tree dumped in the message;
- ``query_by_*`` returns the first match or ``None``;
- ``get_all_by_*`` returns every match;
- ``find_by_*`` is ``get_by_*`` wrapped in
  [`wait_for`][pythonnative.testing.wait_for], for content that appears
  after async work.

Matchers are exact strings, compiled regexes, or predicates taking the
candidate string. Views inside a ``display: "none"`` subtree are skipped
unless ``hidden=True`` is passed.
"""

from __future__ import annotations

import re
import time
import weakref
from typing import Any, Callable, List, Optional, Pattern, Protocol, TypeVar, Union

from .backend import FakeView
from .clock import current_fake_clock

__all__ = ["Matcher", "Queries", "Scope", "wait_for", "within"]

T = TypeVar("T")
Matcher = Union[str, Pattern[str], Callable[[Optional[str]], bool]]
"""What a query accepts: an exact string, a compiled regex (``search``), or a predicate over the candidate."""


class _Flushable(Protocol):
    def _flush_renders(self) -> None: ...

    def dump(self) -> str: ...


_live: "weakref.WeakSet[Any]" = weakref.WeakSet()
"""Mounted render results, so ``wait_for`` can flush their pending renders and dump them on timeout."""


def _matches(value: Optional[str], matcher: Matcher, *, exact: bool = True) -> bool:
    if callable(matcher) and not isinstance(matcher, (str, re.Pattern)):
        return bool(matcher(value))
    if value is None:
        return False
    if isinstance(matcher, re.Pattern):
        return matcher.search(value) is not None
    return value == matcher if exact else matcher in value


def _pump(interval: float) -> None:
    """Run the framework loop once between ``wait_for`` checks and flush pending renders."""
    from .. import runtime

    clock = current_fake_clock()
    if clock is not None:
        clock.run_until_idle()
        if interval > 0:
            time.sleep(interval)
    else:
        runtime.drain(interval)
    for result in list(_live):
        result._flush_renders()


def _dump_live() -> str:
    dumps = [result.dump() for result in _live]
    return "\n\n".join(dumps) if dumps else "<nothing rendered>"


def wait_for(predicate: Callable[[], T], *, timeout: float = 1.0, interval: float = 0.01) -> T:
    """Poll ``predicate`` until it returns a truthy value, draining the framework loop between checks.

    ``LookupError`` and ``AssertionError`` raised by the predicate count as
    "not yet", so ``wait_for(lambda: result.get_by_text("Saved"))`` works
    as well as ``wait_for(lambda: result.query_by_text("Saved"))``. Other
    exceptions propagate immediately.

    Args:
        predicate: Called on every check; its truthy return value is the result.
        timeout: Real seconds to keep trying (measured on the wall clock, not a fake one).
        interval: Longest pause between checks; the loop is drained during it.

    Returns:
        The first truthy value the predicate returned.

    Raises:
        TimeoutError: With the last error (if any) and the rendered tree, when
            ``timeout`` elapses first.
    """
    deadline = time.monotonic() + timeout
    last_error: Optional[BaseException] = None
    while True:
        try:
            value = predicate()
            if value:
                return value
            last_error = None
        except (LookupError, AssertionError) as error:
            last_error = error
        if time.monotonic() >= deadline:
            break
        _pump(interval)
    reason = f": {last_error}" if last_error is not None else " (predicate stayed falsy)"
    raise TimeoutError(f"wait_for timed out after {timeout:g}s{reason}\n\n{_dump_live()}")


class Queries:
    """Query methods shared by ``RenderResult`` and ``within`` scopes.

    Subclasses implement ``views`` (the candidate views in document
    order) and ``dump`` (used in error messages). See the module
    docstring for the ``get_by_`` / ``query_by_`` / ``get_all_by_`` /
    ``find_by_`` conventions.
    """

    def views(self, *, hidden: bool = False) -> List[FakeView]:
        """Candidate views in document order (``hidden=True`` includes ``display: "none"`` subtrees)."""
        raise NotImplementedError

    def dump(self) -> str:
        """Indented text rendering of the queried tree."""
        raise NotImplementedError

    def text(self, *, hidden: bool = False) -> List[str]:
        """Visible strings in document order (``Text`` contents and ``Button`` titles)."""
        return [v.text for v in self.views(hidden=hidden) if v.text is not None]

    # -- plumbing -------------------------------------------------------

    def _all(self, predicate: Callable[[FakeView], bool], hidden: bool = False) -> List[FakeView]:
        return [v for v in self.views(hidden=hidden) if predicate(v)]

    def _one(self, kind: str, matcher: Any, found: List[FakeView]) -> FakeView:
        if len(found) == 1:
            return found[0]
        detail = "no matches" if not found else f"{len(found)} matches: {found}"
        raise LookupError(f"get_by_{kind}({matcher!r}): {detail}\n\n{self.dump()}")

    @staticmethod
    def _first(found: List[FakeView]) -> Optional[FakeView]:
        return found[0] if found else None

    # -- text -----------------------------------------------------------

    def get_all_by_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> List[FakeView]:
        """Return every view whose visible text matches ``matcher`` (``exact=False`` matches substrings)."""
        return self._all(lambda v: _matches(v.text, matcher, exact=exact), hidden)

    def get_by_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> FakeView:
        """Return the single view whose visible text matches ``matcher``; raise ``LookupError`` otherwise."""
        return self._one("text", matcher, self.get_all_by_text(matcher, exact=exact, hidden=hidden))

    def query_by_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view whose visible text matches ``matcher``, or ``None``."""
        return self._first(self.get_all_by_text(matcher, exact=exact, hidden=hidden))

    def find_by_text(
        self,
        matcher: Matcher,
        *,
        exact: bool = True,
        hidden: bool = False,
        timeout: float = 1.0,
        interval: float = 0.01,
    ) -> FakeView:
        """``get_by_text`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(
            lambda: self.get_by_text(matcher, exact=exact, hidden=hidden), timeout=timeout, interval=interval
        )

    # -- test_id --------------------------------------------------------

    def get_all_by_test_id(self, matcher: Matcher, *, hidden: bool = False) -> List[FakeView]:
        """Return every view whose ``test_id`` prop matches ``matcher``."""
        return self._all(lambda v: _matches(v.test_id, matcher), hidden)

    def get_by_test_id(self, matcher: Matcher, *, hidden: bool = False) -> FakeView:
        """Return the single view whose ``test_id`` prop matches ``matcher``; raise ``LookupError`` otherwise."""
        return self._one("test_id", matcher, self.get_all_by_test_id(matcher, hidden=hidden))

    def query_by_test_id(self, matcher: Matcher, *, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view whose ``test_id`` prop matches ``matcher``, or ``None``."""
        return self._first(self.get_all_by_test_id(matcher, hidden=hidden))

    def find_by_test_id(
        self, matcher: Matcher, *, hidden: bool = False, timeout: float = 1.0, interval: float = 0.01
    ) -> FakeView:
        """``get_by_test_id`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(lambda: self.get_by_test_id(matcher, hidden=hidden), timeout=timeout, interval=interval)

    # -- label ----------------------------------------------------------

    def get_all_by_label(self, matcher: Matcher, *, hidden: bool = False) -> List[FakeView]:
        """Return every view whose ``accessibility_label`` prop matches ``matcher``."""
        return self._all(lambda v: _matches(v.label, matcher), hidden)

    def get_by_label(self, matcher: Matcher, *, hidden: bool = False) -> FakeView:
        """Return the single view whose ``accessibility_label`` matches ``matcher``; raise ``LookupError`` if not."""
        return self._one("label", matcher, self.get_all_by_label(matcher, hidden=hidden))

    def query_by_label(self, matcher: Matcher, *, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view whose ``accessibility_label`` prop matches ``matcher``, or ``None``."""
        return self._first(self.get_all_by_label(matcher, hidden=hidden))

    def find_by_label(
        self, matcher: Matcher, *, hidden: bool = False, timeout: float = 1.0, interval: float = 0.01
    ) -> FakeView:
        """``get_by_label`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(lambda: self.get_by_label(matcher, hidden=hidden), timeout=timeout, interval=interval)

    # -- type -----------------------------------------------------------

    def get_all_by_type(self, type_name: str, *, hidden: bool = False) -> List[FakeView]:
        """Return every view of native type ``type_name`` (for example ``"Text"``)."""
        return self._all(lambda v: v.type_name == type_name, hidden)

    def get_by_type(self, type_name: str, *, hidden: bool = False) -> FakeView:
        """Return the single view of native type ``type_name``; raise ``LookupError`` otherwise."""
        return self._one("type", type_name, self.get_all_by_type(type_name, hidden=hidden))

    def query_by_type(self, type_name: str, *, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view of native type ``type_name``, or ``None``."""
        return self._first(self.get_all_by_type(type_name, hidden=hidden))

    def find_by_type(
        self, type_name: str, *, hidden: bool = False, timeout: float = 1.0, interval: float = 0.01
    ) -> FakeView:
        """``get_by_type`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(lambda: self.get_by_type(type_name, hidden=hidden), timeout=timeout, interval=interval)

    # -- role -----------------------------------------------------------

    def get_all_by_role(
        self, role: Matcher, *, name: Optional[Matcher] = None, exact: bool = True, hidden: bool = False
    ) -> List[FakeView]:
        """Return every view whose accessibility role matches ``role`` (and accessible name matches ``name``).

        The role is the ``accessibility_role`` prop, else the type's
        implicit role from [`IMPLICIT_ROLES`][pythonnative.testing.IMPLICIT_ROLES]
        (``Button`` and ``Pressable`` are ``"button"``, ``Switch`` is
        ``"switch"``, ``Checkbox`` is ``"checkbox"``, ``TextInput`` is
        ``"textbox"``, ``Image`` is ``"image"``). The name is the
        ``accessibility_label``, else the visible text or title, else the
        text of descendants (see ``FakeView.accessible_name``);
        ``exact=False`` matches ``name`` as a substring.
        """

        def predicate(v: FakeView) -> bool:
            if not _matches(v.role, role):
                return False
            return name is None or _matches(v.accessible_name, name, exact=exact)

        return self._all(predicate, hidden)

    def get_by_role(
        self, role: Matcher, *, name: Optional[Matcher] = None, exact: bool = True, hidden: bool = False
    ) -> FakeView:
        """Return the single view with role ``role`` (and accessible name ``name``); raise ``LookupError`` otherwise."""
        found = self.get_all_by_role(role, name=name, exact=exact, hidden=hidden)
        label = role if name is None else f"{role!r}, name={name!r}"
        return self._one("role", label, found)

    def query_by_role(
        self, role: Matcher, *, name: Optional[Matcher] = None, exact: bool = True, hidden: bool = False
    ) -> Optional[FakeView]:
        """Return the first view with role ``role`` (and accessible name ``name``), or ``None``."""
        return self._first(self.get_all_by_role(role, name=name, exact=exact, hidden=hidden))

    def find_by_role(
        self,
        role: Matcher,
        *,
        name: Optional[Matcher] = None,
        exact: bool = True,
        hidden: bool = False,
        timeout: float = 1.0,
        interval: float = 0.01,
    ) -> FakeView:
        """``get_by_role`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(
            lambda: self.get_by_role(role, name=name, exact=exact, hidden=hidden), timeout=timeout, interval=interval
        )

    # -- placeholder ----------------------------------------------------

    def get_all_by_placeholder_text(
        self, matcher: Matcher, *, exact: bool = True, hidden: bool = False
    ) -> List[FakeView]:
        """Return every view whose ``placeholder`` prop matches ``matcher`` (``exact=False`` matches substrings)."""
        return self._all(lambda v: _matches(v.placeholder, matcher, exact=exact), hidden)

    def get_by_placeholder_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> FakeView:
        """Return the single view whose ``placeholder`` matches ``matcher``; raise ``LookupError`` otherwise."""
        found = self.get_all_by_placeholder_text(matcher, exact=exact, hidden=hidden)
        return self._one("placeholder_text", matcher, found)

    def query_by_placeholder_text(
        self, matcher: Matcher, *, exact: bool = True, hidden: bool = False
    ) -> Optional[FakeView]:
        """Return the first view whose ``placeholder`` matches ``matcher``, or ``None``."""
        return self._first(self.get_all_by_placeholder_text(matcher, exact=exact, hidden=hidden))

    def find_by_placeholder_text(
        self,
        matcher: Matcher,
        *,
        exact: bool = True,
        hidden: bool = False,
        timeout: float = 1.0,
        interval: float = 0.01,
    ) -> FakeView:
        """``get_by_placeholder_text`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(
            lambda: self.get_by_placeholder_text(matcher, exact=exact, hidden=hidden),
            timeout=timeout,
            interval=interval,
        )

    # -- display value --------------------------------------------------

    def get_all_by_display_value(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> List[FakeView]:
        """Return every view whose string ``value`` prop (a ``TextInput``'s contents) matches ``matcher``."""
        return self._all(lambda v: _matches(v.value, matcher, exact=exact), hidden)

    def get_by_display_value(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> FakeView:
        """Return the single view whose display value matches ``matcher``; raise ``LookupError`` otherwise."""
        found = self.get_all_by_display_value(matcher, exact=exact, hidden=hidden)
        return self._one("display_value", matcher, found)

    def query_by_display_value(
        self, matcher: Matcher, *, exact: bool = True, hidden: bool = False
    ) -> Optional[FakeView]:
        """Return the first view whose display value matches ``matcher``, or ``None``."""
        return self._first(self.get_all_by_display_value(matcher, exact=exact, hidden=hidden))

    def find_by_display_value(
        self,
        matcher: Matcher,
        *,
        exact: bool = True,
        hidden: bool = False,
        timeout: float = 1.0,
        interval: float = 0.01,
    ) -> FakeView:
        """``get_by_display_value`` retried with [`wait_for`][pythonnative.testing.wait_for] until it succeeds."""
        return wait_for(
            lambda: self.get_by_display_value(matcher, exact=exact, hidden=hidden), timeout=timeout, interval=interval
        )

    # -- scoping --------------------------------------------------------

    def within(self, view: FakeView) -> "Scope":
        """Return the same queries restricted to ``view`` and its descendants."""
        return Scope(view)


class Scope(Queries):
    """Queries restricted to one view's subtree (see [`within`][pythonnative.testing.within]).

    Attributes:
        view: The subtree root; it is itself a candidate for every query.
    """

    def __init__(self, view: FakeView) -> None:
        self.view = view

    def views(self, *, hidden: bool = False) -> List[FakeView]:
        """The scope root and every descendant, depth-first (skipping hidden subtrees unless ``hidden=True``)."""
        return list(self.view.walk(include_hidden=hidden))

    def dump(self) -> str:
        """Indented text rendering of the scoped subtree."""
        return self.view.dump()

    def __repr__(self) -> str:
        return f"<within {self.view!r}>"


def within(view: FakeView) -> Scope:
    """Scope queries to ``view``'s subtree.

    ```python
    card = within(result.get_by_test_id("summary"))
    assert card.get_by_display_value("a@b.c")
    ```
    """
    return Scope(view)
