"""Tag-based event routing between native views and Python callbacks.

Before the batched-commit overhaul, every event prop (``on_click``,
``on_change``, …) was wired by storing the Python callable on (or next
to) the native view, and every re-render re-pushed fresh closures across
the bridge. This module replaces that with a single dispatch channel:

- The reconciler strips callable props out of the payload sent to
  native handlers and registers them here, keyed by ``(tag, name)``.
- Handlers wire their platform listener **once** at view creation; the
  listener calls [`dispatch_event`][pythonnative.events.dispatch_event]
  with the view's tag and the event name.
- Re-renders only mutate this Python-side registry; no native call is
  made when just a callback identity changes.

The set of event names present on an element is forwarded to handlers
under the [`EVENTS_PROP`][pythonnative.events.EVENTS_PROP] key (a
``frozenset``), so handlers that wire expensive listeners (scroll
delegates, gesture recognizers) can do so conditionally. Dispatching an
event nobody listens to is a cheap dict miss.
"""

import threading
from typing import Any, Callable, Dict, FrozenSet, Optional, Tuple

EVENTS_PROP = "_pn_events"
"""Prop key carrying the ``frozenset`` of event names wired on an element."""

GESTURES_PROP = "gestures"
"""Prop key carrying gesture descriptors (see ``pythonnative.gestures``)."""

# Prop dicts that may carry nested callables, mapped to the event name
# each nested key is hoisted to.
_NESTED_EVENT_PROPS: Dict[str, Dict[str, str]] = {
    "refresh_control": {"on_refresh": "on_refresh"},
}


class EventRegistry:
    """Process-wide map of ``(tag, event name) -> Python callback``.

    Thread-safe: native backends may dispatch from the platform UI
    thread while the reconciler updates registrations from the render
    thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callbacks: Dict[int, Dict[str, Callable[..., Any]]] = {}

    def set_events(self, tag: int, events: Dict[str, Callable[..., Any]]) -> None:
        """Replace every registration for ``tag`` with ``events``."""
        with self._lock:
            if events:
                self._callbacks[tag] = dict(events)
            else:
                self._callbacks.pop(tag, None)

    def clear(self, tag: int) -> None:
        """Drop every registration for ``tag`` (called on view destroy)."""
        with self._lock:
            self._callbacks.pop(tag, None)

    def get(self, tag: int, name: str) -> Optional[Callable[..., Any]]:
        """Return the callback for ``(tag, name)``, or ``None``."""
        with self._lock:
            bucket = self._callbacks.get(tag)
            if bucket is None:
                return None
            return bucket.get(name)

    def has(self, tag: int, name: str) -> bool:
        """Return whether a callback is registered for ``(tag, name)``."""
        return self.get(tag, name) is not None

    def dispatch(self, tag: int, name: str, *args: Any) -> bool:
        """Invoke the callback for ``(tag, name)`` with ``args``.

        Returns:
            ``True`` when a callback existed and was invoked (even if
            it raised: exceptions are swallowed so a buggy app
            callback can't crash the platform's UI thread), ``False``
            when nothing is registered.
        """
        callback = self.get(tag, name)
        if callback is None:
            return False
        try:
            callback(*args)
        except Exception:
            import traceback

            traceback.print_exc()
        return True

    def reset(self) -> None:
        """Drop every registration (test helper)."""
        with self._lock:
            self._callbacks.clear()


_registry = EventRegistry()


def get_event_registry() -> EventRegistry:
    """Return the process-wide [`EventRegistry`][pythonnative.events.EventRegistry]."""
    return _registry


def dispatch_event(tag: int, name: str, *args: Any) -> bool:
    """Dispatch an event from a native view into Python.

    This is the single entry point platform handlers call when a
    native listener fires.

    Args:
        tag: The view's reconciler-assigned tag.
        name: Event name, the original prop name (``"on_click"``,
            ``"on_change"``, …) or a gesture channel (``"gesture:0"``).
        *args: Positional arguments forwarded to the user callback,
            preserving each prop's documented signature.

    Returns:
        Whether a callback was registered for ``(tag, name)``.
    """
    return _registry.dispatch(tag, name, *args)


# ======================================================================
# Prop splitting
# ======================================================================


def extract_events(props: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Callable[..., Any]]]:
    """Split ``props`` into native-safe props and Python event callbacks.

    Rules:

    - Top-level callables named ``on_*`` become events under their prop
      name and are removed from the native payload.
    - ``refresh_control`` dicts have their nested ``on_refresh``
      hoisted to the ``"on_refresh"`` event; the remaining keys
      (``refreshing``, ``tint_color``) stay in the payload.
    - ``gestures`` lists of gesture descriptors are serialized to plain
      dicts (handlers wire recognizers from them) while their callbacks
      are folded into per-gesture ``"gesture:<i>"`` routers.
    - The resulting payload carries ``_pn_events`` (a frozenset of the
      event names present), so handlers can wire listeners
      conditionally and the prop differ can detect listener
      addition/removal without comparing closures.

    Args:
        props: Raw element props (already stripped of reconciler-owned
            keys).

    Returns:
        ``(clean_props, events)`` where ``clean_props`` contains no
        callables and ``events`` maps event names to callbacks.
    """
    clean: Dict[str, Any] = {}
    events: Dict[str, Callable[..., Any]] = {}

    for key, value in props.items():
        if key.startswith("on_") and callable(value):
            events[key] = value
            continue
        nested_spec = _NESTED_EVENT_PROPS.get(key)
        if nested_spec is not None and isinstance(value, dict):
            remainder: Dict[str, Any] = {}
            for nested_key, nested_value in value.items():
                event_name = nested_spec.get(nested_key)
                if event_name is not None and callable(nested_value):
                    events[event_name] = nested_value
                else:
                    remainder[nested_key] = nested_value
            clean[key] = remainder
            continue
        if key == GESTURES_PROP and value:
            from .gestures import serialize_gestures

            specs, gesture_events = serialize_gestures(value)
            clean[key] = specs
            events.update(gesture_events)
            continue
        clean[key] = value

    if events:
        clean[EVENTS_PROP] = frozenset(events)
    return clean, events


def event_names(props: Dict[str, Any]) -> FrozenSet[str]:
    """Return the event-name set a handler should consult for ``props``."""
    names = props.get(EVENTS_PROP)
    if isinstance(names, frozenset):
        return names
    if isinstance(names, (set, list, tuple)):
        return frozenset(names)
    return frozenset()


__all__ = [
    "EVENTS_PROP",
    "GESTURES_PROP",
    "EventRegistry",
    "get_event_registry",
    "dispatch_event",
    "extract_events",
    "event_names",
]
