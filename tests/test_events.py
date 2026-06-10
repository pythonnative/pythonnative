"""Tests for tag-based event routing (`pythonnative.events`).

Covers the prop splitter (`extract_events`), the process-wide
`EventRegistry`, and the reconciler integration: callables never reach
the native payload, dispatch hits the *latest* closure, and destroy
clears registrations.
"""

from __future__ import annotations

from typing import Any, List

from fake_backend import FakeBackend

from pythonnative.element import Element
from pythonnative.events import (
    EVENTS_PROP,
    EventRegistry,
    dispatch_event,
    event_names,
    extract_events,
    get_event_registry,
)
from pythonnative.reconciler import Reconciler

# ======================================================================
# extract_events: prop splitting
# ======================================================================


def test_extract_strips_on_callables_into_events() -> None:
    pressed: List[int] = []
    props = {"title": "Go", "on_press": lambda: pressed.append(1), "enabled": True}

    clean, events = extract_events(props)

    assert set(events) == {"on_press"}
    assert "on_press" not in clean
    assert clean["title"] == "Go" and clean["enabled"] is True
    assert clean[EVENTS_PROP] == frozenset({"on_press"})


def test_extract_keeps_non_callable_on_props() -> None:
    clean, events = extract_events({"on_press": "not-a-callback"})
    assert events == {}
    assert clean["on_press"] == "not-a-callback"
    assert EVENTS_PROP not in clean


def test_extract_without_events_adds_no_marker() -> None:
    clean, events = extract_events({"text": "hi"})
    assert events == {}
    assert clean == {"text": "hi"}


def test_extract_hoists_nested_refresh_control_callback() -> None:
    refreshed: List[int] = []
    props = {
        "refresh_control": {
            "refreshing": True,
            "tint_color": "#123456",
            "on_refresh": lambda: refreshed.append(1),
        }
    }

    clean, events = extract_events(props)

    assert set(events) == {"on_refresh"}
    assert clean["refresh_control"] == {"refreshing": True, "tint_color": "#123456"}
    events["on_refresh"]()
    assert refreshed == [1]


def test_extract_serializes_gestures_to_plain_specs() -> None:
    from pythonnative.gestures import Tap

    taps: List[Any] = []
    clean, events = extract_events({"gestures": [Tap(on_tap=taps.append, n_taps=2)]})

    assert clean["gestures"] == [{"kind": "tap", "n_taps": 2, "max_distance": 12.0}]
    assert set(events) == {"gesture:0"}
    assert clean[EVENTS_PROP] == frozenset({"gesture:0"})
    # The router converts the raw payload into a GestureEvent.
    events["gesture:0"]({"kind": "tap", "state": "ended", "x": 5.0, "y": 6.0})
    assert len(taps) == 1
    assert taps[0].x == 5.0 and taps[0].y == 6.0


def test_event_names_accepts_multiple_shapes() -> None:
    assert event_names({EVENTS_PROP: frozenset({"on_press"})}) == frozenset({"on_press"})
    assert event_names({EVENTS_PROP: ["on_a", "on_b"]}) == frozenset({"on_a", "on_b"})
    assert event_names({}) == frozenset()


# ======================================================================
# EventRegistry
# ======================================================================


def test_registry_set_get_dispatch() -> None:
    registry = EventRegistry()
    hits: List[Any] = []
    registry.set_events(7, {"on_change": lambda v: hits.append(v)})

    assert registry.has(7, "on_change")
    assert registry.dispatch(7, "on_change", "abc") is True
    assert hits == ["abc"]
    assert registry.dispatch(7, "on_other") is False
    assert registry.dispatch(99, "on_change") is False


def test_registry_set_events_replaces_previous_bucket() -> None:
    registry = EventRegistry()
    registry.set_events(1, {"on_a": lambda: None, "on_b": lambda: None})
    registry.set_events(1, {"on_a": lambda: None})
    assert registry.has(1, "on_a")
    assert not registry.has(1, "on_b")

    registry.set_events(1, {})
    assert not registry.has(1, "on_a")


def test_registry_clear_drops_tag() -> None:
    registry = EventRegistry()
    registry.set_events(3, {"on_press": lambda: None})
    registry.clear(3)
    assert registry.dispatch(3, "on_press") is False


def test_dispatch_swallows_callback_exceptions() -> None:
    registry = EventRegistry()

    def boom() -> None:
        raise RuntimeError("user bug")

    registry.set_events(5, {"on_press": boom})
    # Returns True (a callback ran) without propagating — a buggy app
    # callback must not crash the platform UI thread.
    assert registry.dispatch(5, "on_press") is True


# ======================================================================
# Reconciler integration
# ======================================================================


def _mounted(el: Element) -> tuple:
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None
    rec.mount(el)
    return rec, backend


def test_mounted_view_routes_events_by_tag() -> None:
    pressed: List[int] = []
    rec, backend = _mounted(Element("Button", {"title": "Go", "on_press": lambda: pressed.append(1)}, []))
    tag = rec.root_tag()
    assert tag is not None

    # The native payload carries the marker, never the closure.
    button = backend.views[tag]
    assert "on_press" not in button.props
    assert button.props[EVENTS_PROP] == frozenset({"on_press"})

    assert dispatch_event(tag, "on_press") is True
    assert pressed == [1]


def test_event_args_forwarded_to_callback() -> None:
    seen: List[Any] = []
    rec, _backend = _mounted(Element("TextInput", {"on_change": seen.append}, []))
    tag = rec.root_tag()
    assert tag is not None

    dispatch_event(tag, "on_change", "hello")
    assert seen == ["hello"]


def test_destroy_clears_event_registrations() -> None:
    pressed: List[int] = []
    rec, _backend = _mounted(Element("Button", {"title": "Go", "on_press": lambda: pressed.append(1)}, []))
    tag = rec.root_tag()
    assert tag is not None

    rec.unmount()

    assert dispatch_event(tag, "on_press") is False
    assert pressed == []
    assert get_event_registry().get(tag, "on_press") is None


def test_listener_removal_updates_marker_prop() -> None:
    rec, backend = _mounted(Element("Button", {"title": "Go", "on_press": lambda: None}, []))
    tag = rec.root_tag()
    assert tag is not None

    # Dropping the listener must update _pn_events so handlers can
    # unwire, and dispatch must stop routing.
    rec.reconcile(Element("Button", {"title": "Go"}, []))
    assert event_names(backend.views[tag].props) == frozenset()
    assert dispatch_event(tag, "on_press") is False
