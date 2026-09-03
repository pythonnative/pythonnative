"""Render components into a fake backend and query the result.

```python
import pythonnative as pn
from pythonnative.testing import render

def test_counter():
    result = render(Counter())
    assert result.get_by_text("Count: 0")
    result.press(result.get_by_text("+"))
    assert result.get_by_text("Count: 1")
```
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Generic, List, Optional, Pattern, Tuple, TypeVar, Union

from ..element import Element, Node
from ..events import dispatch_event, get_event_registry
from .backend import FakeBackend, FakeView

__all__ = ["FakeHost", "HookResult", "RenderResult", "render", "render_hook", "settle"]

T = TypeVar("T")
Matcher = Union[str, Pattern[str], Callable[[Optional[str]], bool]]
Target = Union[FakeView, int]

DEFAULT_VIEWPORT: Tuple[float, float] = (390.0, 844.0)


def _matches(value: Optional[str], matcher: Matcher, *, exact: bool) -> bool:
    if callable(matcher) and not isinstance(matcher, (str, re.Pattern)):
        return bool(matcher(value))
    if value is None:
        return False
    if isinstance(matcher, re.Pattern):
        return matcher.search(value) is not None
    return value == matcher if exact else matcher in value


def settle(reconciler: Any = None, timeout: float = 1.0) -> None:
    """Pump the framework loop and flush pending renders until everything is idle.

    Use after triggering async work (``use_resource``, ``use_query``,
    transitions, coroutines started by handlers) so assertions see the
    settled tree.
    """
    from .. import runtime

    for _ in range(50):
        idle = runtime.drain(timeout)
        if reconciler is not None:
            reconciler.flush_dirty()
            if reconciler.transitions.pending:
                reconciler.transitions.flush()
                continue
        if idle and (reconciler is None or not reconciler._has_dirty_work()):
            return


class FakeHost:
    """A [`HostNavigator`][pythonnative.navigation.HostNavigator] that records native screen operations.

    Pass as ``render(..., host=FakeHost())`` to render a root stack the
    way a device would: pushes are recorded in ``pushed`` instead of
    creating screens in-tree. ``set_focused`` simulates the platform
    covering / revealing the screen.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None) -> None:
        self.is_focused = True
        self.initial_state = initial_state
        self.pushed: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        self.popped: List[int] = []
        self.replaced: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        self.resets: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        self.options: List[Dict[str, Any]] = []
        self._focus_listeners: List[Callable[[bool], None]] = []

    def initial_navigation_state(self) -> Optional[Dict[str, Any]]:
        """Return the ``initial_state`` the host was constructed with (``None`` for a fresh root)."""
        return self.initial_state

    def push_screen(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Record the push in ``pushed`` instead of creating a native screen."""
        self.pushed.append((state, dict(options)))

    def pop_screens(self, count: int) -> None:
        """Record the requested pop ``count`` in ``popped``."""
        self.popped.append(count)

    def replace_screen(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Record the replacement in ``replaced`` instead of swapping a native screen."""
        self.replaced.append((state, dict(options)))

    def reset_screens(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Record the stack reset in ``resets`` instead of rebuilding native screens."""
        self.resets.append((state, dict(options)))

    def set_screen_options(self, options: Dict[str, Any]) -> None:
        """Append a copy of ``options`` to ``options`` (see the ``title`` property)."""
        self.options.append(dict(options))

    def add_focus_listener(self, callback: Callable[[bool], None]) -> Callable[[], None]:
        """Register a focus callback fired by ``set_focused``; returns an unsubscribe callable."""
        self._focus_listeners.append(callback)
        return lambda: self._focus_listeners.remove(callback)

    def set_focused(self, focused: bool) -> None:
        """Simulate the platform covering (``False``) or revealing (``True``) the screen."""
        self.is_focused = focused
        for cb in list(self._focus_listeners):
            cb(focused)

    @property
    def title(self) -> Optional[str]:
        """The most recent ``title`` passed to ``set_screen_options``."""
        for options in reversed(self.options):
            if "title" in options:
                return options["title"]
        return None


class RenderResult:
    """Handle to a mounted tree: queries, events, re-render, unmount.

    Query methods come in three flavors, mirroring Testing Library:
    ``get_by_*`` returns exactly one match or raises ``LookupError``
    (with the tree dumped in the message), ``query_by_*`` returns the
    match or ``None``, ``get_all_by_*`` returns every match. Matchers
    are exact strings, compiled regexes, or predicates. Views inside a
    ``display: "none"`` subtree (inactive tabs, covered stack screens)
    are skipped unless ``hidden=True`` is passed.
    """

    def __init__(self, reconciler: Any, backend: FakeBackend, wrap: Callable[[Node], Element]) -> None:
        self.reconciler = reconciler
        self.backend = backend
        self._wrap = wrap

    # -- tree -----------------------------------------------------------

    @property
    def root(self) -> Optional[FakeView]:
        """The root native view (``None`` after unmount)."""
        return self.reconciler.root_view()

    def views(self, *, hidden: bool = False) -> List[FakeView]:
        """Every live view, root first (includes detached ``Portal`` overlays)."""
        root = self.root
        out = list(root.walk(include_hidden=hidden)) if root is not None else []
        seen = {id(v) for v in out}
        for view in self.backend.views.values():
            if view.parent is None and view is not root and id(view) not in seen:
                out.extend(view.walk(include_hidden=hidden))
        return out

    def dump(self) -> str:
        """Indented text rendering of the live tree."""
        root = self.root
        return root.dump() if root is not None else "<unmounted>"

    def text(self, *, hidden: bool = False) -> List[str]:
        """Visible strings in document order."""
        return [v.text for v in self.views(hidden=hidden) if v.text is not None]

    # -- queries --------------------------------------------------------

    def _all(self, predicate: Callable[[FakeView], bool], hidden: bool = False) -> List[FakeView]:
        return [v for v in self.views(hidden=hidden) if predicate(v)]

    def _one(self, kind: str, matcher: Any, found: List[FakeView]) -> FakeView:
        if len(found) == 1:
            return found[0]
        detail = "no matches" if not found else f"{len(found)} matches: {found}"
        raise LookupError(f"get_by_{kind}({matcher!r}): {detail}\n\n{self.dump()}")

    def get_all_by_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> List[FakeView]:
        """Return every view whose visible text matches ``matcher`` (``exact=False`` matches substrings)."""
        return self._all(lambda v: _matches(v.text, matcher, exact=exact), hidden)

    def get_by_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> FakeView:
        """Return the single view whose visible text matches ``matcher``; raise ``LookupError`` otherwise."""
        return self._one("text", matcher, self.get_all_by_text(matcher, exact=exact, hidden=hidden))

    def query_by_text(self, matcher: Matcher, *, exact: bool = True, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view whose visible text matches ``matcher``, or ``None``."""
        found = self.get_all_by_text(matcher, exact=exact, hidden=hidden)
        return found[0] if found else None

    def get_all_by_test_id(self, matcher: Matcher, *, hidden: bool = False) -> List[FakeView]:
        """Return every view whose ``test_id`` prop matches ``matcher``."""
        return self._all(lambda v: _matches(v.test_id, matcher, exact=True), hidden)

    def get_by_test_id(self, matcher: Matcher, *, hidden: bool = False) -> FakeView:
        """Return the single view whose ``test_id`` prop matches ``matcher``; raise ``LookupError`` otherwise."""
        return self._one("test_id", matcher, self.get_all_by_test_id(matcher, hidden=hidden))

    def query_by_test_id(self, matcher: Matcher, *, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view whose ``test_id`` prop matches ``matcher``, or ``None``."""
        found = self.get_all_by_test_id(matcher, hidden=hidden)
        return found[0] if found else None

    def get_all_by_label(self, matcher: Matcher, *, hidden: bool = False) -> List[FakeView]:
        """Return every view whose ``accessibility_label`` prop matches ``matcher``."""
        return self._all(lambda v: _matches(v.label, matcher, exact=True), hidden)

    def get_by_label(self, matcher: Matcher, *, hidden: bool = False) -> FakeView:
        """Return the single view whose ``accessibility_label`` matches ``matcher``; raise ``LookupError`` if not."""
        return self._one("label", matcher, self.get_all_by_label(matcher, hidden=hidden))

    def query_by_label(self, matcher: Matcher, *, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view whose ``accessibility_label`` prop matches ``matcher``, or ``None``."""
        found = self.get_all_by_label(matcher, hidden=hidden)
        return found[0] if found else None

    def get_all_by_type(self, type_name: str, *, hidden: bool = False) -> List[FakeView]:
        """Return every view of native type ``type_name`` (for example ``"Text"``)."""
        return self._all(lambda v: v.type_name == type_name, hidden)

    def get_by_type(self, type_name: str, *, hidden: bool = False) -> FakeView:
        """Return the single view of native type ``type_name``; raise ``LookupError`` otherwise."""
        return self._one("type", type_name, self.get_all_by_type(type_name, hidden=hidden))

    def query_by_type(self, type_name: str, *, hidden: bool = False) -> Optional[FakeView]:
        """Return the first view of native type ``type_name``, or ``None``."""
        found = self.get_all_by_type(type_name, hidden=hidden)
        return found[0] if found else None

    # -- events ---------------------------------------------------------

    def fire(self, target: Target, event: str, *args: Any) -> None:
        """Dispatch ``event`` (an ``on_*`` prop name) to ``target`` and settle.

        Raises:
            LookupError: If no handler is registered for the event.
        """
        tag = target.tag if isinstance(target, FakeView) else int(target)
        if not get_event_registry().has(tag, event):
            raise LookupError(f"fire({target!r}, {event!r}): no handler registered\n\n{self.dump()}")
        dispatch_event(tag, event, *args)
        self.settle()

    def press(self, target: Target) -> None:
        """Fire ``on_press`` on ``target``."""
        self.fire(target, "on_press")

    def change_text(self, target: Target, value: str) -> None:
        """Fire ``on_change_text`` on a ``TextInput``."""
        self.fire(target, "on_change_text", value)

    def back(self) -> bool:
        """Simulate the system back action; returns whether a handler consumed it."""
        consumed = bool(self.reconciler.dispatch_back_press())
        self.settle()
        return consumed

    # -- lifecycle ------------------------------------------------------

    def settle(self, timeout: float = 1.0) -> None:
        """Flush pending renders and async work (see [`settle`][pythonnative.testing.settle])."""
        settle(self.reconciler, timeout)

    def rerender(self, element: Node) -> None:
        """Reconcile a new root element (new props from outside the tree)."""
        self.reconciler.reconcile(self._wrap(element))
        self.settle()

    def unmount(self) -> None:
        """Unmount the tree, running effect cleanups and destroying every view."""
        self.reconciler.unmount()

    def __enter__(self) -> "RenderResult":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.unmount()


def render(
    element: Node,
    *,
    viewport: Optional[Tuple[float, float]] = DEFAULT_VIEWPORT,
    backend: Optional[FakeBackend] = None,
    host: Optional[FakeHost] = None,
    settle_first: bool = True,
) -> RenderResult:
    """Mount ``element`` into a [`FakeBackend`][pythonnative.testing.FakeBackend].

    Args:
        element: The element (or component call) to render.
        viewport: Size for the layout pass; ``None`` skips layout.
        backend: Reuse an existing backend (defaults to a fresh one).
        host: Render under a [`HostRoot`][pythonnative.navigation.host.HostRoot]
            with this fake host, so root stacks push native screens
            into ``host.pushed`` instead of the tree.
        settle_first: Drain async work and effects before returning.
    """
    from ..reconciler import Reconciler

    backend = backend if backend is not None else FakeBackend()
    reconciler = Reconciler(backend)
    if viewport is not None:
        reconciler.set_viewport_size(float(viewport[0]), float(viewport[1]))

    def wrap(node: Node) -> Element:
        if host is not None:
            from ..navigation.host import HostRoot

            return HostRoot(node, host=host)
        if isinstance(node, Element):
            return node
        from ..components import Fragment

        return Fragment(*(node if isinstance(node, (list, tuple)) else [node]))

    reconciler.mount(wrap(element))
    result = RenderResult(reconciler, backend, wrap)
    if settle_first:
        result.settle()
    return result


class HookResult(Generic[T]):
    """Handle returned by [`render_hook`][pythonnative.testing.render_hook].

    Attributes:
        current: The hook's most recent return value.
    """

    def __init__(self, result: RenderResult, box: Dict[str, Any], rerender: Callable[..., None]) -> None:
        self._result = result
        self._box = box
        self._rerender = rerender

    @property
    def current(self) -> T:
        """The value the hook returned on its most recent render."""
        return self._box["value"]

    @property
    def render_count(self) -> int:
        """How many times the hook has run since ``render_hook`` was called."""
        return self._box["renders"]

    def act(self, fn: Callable[[], Any]) -> None:
        """Run ``fn`` (typically a state setter) and settle."""
        fn()
        self._result.settle()

    def rerender(self, *args: Any, **kwargs: Any) -> None:
        """Re-run the hook with new arguments."""
        self._rerender(*args, **kwargs)

    def settle(self) -> None:
        """Flush pending renders and async work started by the hook."""
        self._result.settle()

    def unmount(self) -> None:
        """Unmount the harness component, running the hook's effect cleanups."""
        self._result.unmount()


def render_hook(hook: Callable[..., T], *args: Any, host: Optional[FakeHost] = None, **kwargs: Any) -> HookResult[T]:
    """Run ``hook(*args, **kwargs)`` inside a throwaway component.

    ```python
    result = render_hook(lambda: pn.use_state(0))
    value, set_value = result.current
    result.act(lambda: set_value(5))
    assert result.current[0] == 5
    ```
    """
    from ..component import component

    box: Dict[str, Any] = {"value": None, "renders": 0}

    @component
    def Harness(*, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
        box["value"] = hook(*args, **kwargs)
        box["renders"] += 1
        return None

    result = render(Harness(args=tuple(args), kwargs=dict(kwargs)), host=host)

    def rerender(*new_args: Any, **new_kwargs: Any) -> None:
        result.rerender(Harness(args=tuple(new_args) or tuple(args), kwargs={**kwargs, **new_kwargs}))

    return HookResult(result, box, rerender)
