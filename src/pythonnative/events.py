"""Tag-based event routing between native views and Python callbacks.

Event props such as ``on_press`` and ``on_change`` stay in Python.
Native views send a tag and event name through the bridge:

- The reconciler strips callable props out of the payload sent to
  native handlers and keeps them on the view's node
  ([`VNode.events`][pythonnative.reconciler.VNode]).
- When a view is committed, its node is registered here under its tag.
  Handlers wire their platform listener **once** at view creation; the
  listener calls [`dispatch_event`][pythonnative.events.dispatch_event]
  with the view's tag and the event name, and the registry reads the
  handler from the node.
- Re-renders only change the node's handler table; no native call and
  no registry write is made when just a callback identity changes. A
  render pass that's rolled back restores the node's table with the
  rest of the node.

The set of event names present on an element is forwarded to handlers
under the [`EVENTS_PROP`][pythonnative.events.EVENTS_PROP] key (a
``frozenset``), so handlers that wire expensive listeners (scroll
delegates, gesture recognizers) can do so conditionally. Dispatching an
event nobody listens to is a cheap dict miss.
"""

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
    """Process-wide map of view tag to the node holding that view's handlers.

    A registered *source* is anything with an ``events`` attribute that
    is a mapping of event name to callback, or ``None``: the
    reconciler registers each committed native node. Registration,
    lookup, and dispatch happen on the application thread; bridge
    backends queue native input there before dispatching it.
    """

    def __init__(self) -> None:
        self._sources: Dict[int, Any] = {}
        self._scopes: Dict[int, Any] = {}

    def register(self, tag: int, source: Any, scope: Any = None) -> None:
        """Route events for ``tag`` to ``source.events``, run in the owning component's ``scope``."""
        self._sources[tag] = source
        self._scopes[tag] = scope

    def invoke(self, tag: int, name: str, *args: Any) -> Any:
        """Invoke a sync or async handler with component cancellation."""
        from .runtime import invoke

        callback = self.get(tag, name)
        if callback is not None:
            return invoke(callback, *args, scope=self._scopes.get(tag))
        return None

    def clear(self, tag: int) -> None:
        """Drop the registration for ``tag`` (called on view destroy)."""
        self._sources.pop(tag, None)
        self._scopes.pop(tag, None)

    def get(self, tag: int, name: str) -> Optional[Callable[..., Any]]:
        """Return the callback for ``(tag, name)``, or ``None``."""
        source = self._sources.get(tag)
        if source is None:
            return None
        events = source.events
        return events.get(name) if events else None

    def has(self, tag: int, name: str) -> bool:
        """Return whether a callback is registered for ``(tag, name)``."""
        return self.get(tag, name) is not None

    def dispatch(self, tag: int, name: str, *args: Any) -> bool:
        """Invoke the callback for ``(tag, name)`` with ``args``.

        Returns:
            ``True`` when a callback existed and was invoked (even if
            it raised: exceptions never propagate into the platform's
            UI thread; in dev mode they are routed to the RedBox via
            [`report_error`][pythonnative.diagnostics.report_error],
            otherwise the traceback is printed), ``False`` when nothing
            is registered.
        """
        callback = self.get(tag, name)
        if callback is None:
            return False
        try:
            self.invoke(tag, name, *args)
        except Exception as exc:
            from . import diagnostics

            if not diagnostics.report_error(exc, phase="event"):
                import traceback

                traceback.print_exc()
        return True

    def reset(self) -> None:
        """Drop every registration (test helper)."""
        self._sources.clear()
        self._scopes.clear()


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
        name: Event name, the original prop name (``"on_press"``,
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


MOTION_PROP = "_pn_motion"
"""Prop key carrying a view's animated style and worklet handler bindings (RFC 0009)."""

WorkletBinder = Callable[[Callable[..., Any]], Optional[int]]
"""Turns an event or gesture worklet into the handler binding the core runs, or ``None`` without a core."""


def extract_events(
    props: Dict[str, Any], bind_worklet: Optional[WorkletBinder] = None
) -> Tuple[Dict[str, Any], Dict[str, Callable[..., Any]]]:
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
    - With ``bind_worklet``, an ``on_*`` callback marked ``@worklet`` runs
      in the renderer core instead (RFC 0009): it stays in ``_pn_events`` so
      the platform reports the event, and its handler binding goes in
      ``_pn_motion["events"]`` rather than in Python's registry. Gesture
      worklets are bound the same way. Animated style bindings that
      ``resolve_style`` collected become ``_pn_motion["style"]``.

    Args:
        props: Raw element props (already stripped of reconciler-owned
            keys).
        bind_worklet: Installs a worklet handler and returns its binding,
            or ``None`` when no core can run it (it then runs in Python).

    Returns:
        ``(clean_props, events)`` where ``clean_props`` contains no
        callables and ``events`` maps event names to callbacks.
    """
    from .motion.worklets import is_worklet
    from .style import MOTION_STYLE_KEY

    clean: Dict[str, Any] = {}
    events: Dict[str, Callable[..., Any]] = {}
    native: Dict[str, int] = {}
    styles: Tuple[int, ...] = ()

    for key, value in props.items():
        if key == MOTION_STYLE_KEY:
            styles = tuple(value)
            continue
        if key.startswith("on_") and callable(value):
            binding = bind_worklet(value) if bind_worklet is not None and is_worklet(value) else None
            if binding is not None:
                native[key] = binding
            else:
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

            specs, gesture_events = serialize_gestures(value, bind_worklet)
            clean[key] = specs
            events.update(gesture_events)
            continue
        clean[key] = value

    if events or native:
        clean[EVENTS_PROP] = frozenset(events) | frozenset(native)
    if styles or native:
        motion: Dict[str, Any] = {}
        if styles:
            motion["style"] = list(styles)
        if native:
            motion["events"] = native
        clean[MOTION_PROP] = motion
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
    "MOTION_PROP",
    "WorkletBinder",
    "EventRegistry",
    "get_event_registry",
    "dispatch_event",
    "extract_events",
    "event_names",
]
