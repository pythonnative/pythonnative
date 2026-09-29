"""Unit tests for the typed event records and how the built-ins deliver them."""

from __future__ import annotations

import dataclasses

import pytest

import pythonnative as pn
from pythonnative.components._base import _layout_callback, _LayoutCallback
from pythonnative.sdk.schema import COMPONENTS


@pytest.mark.parametrize(
    "record",
    [
        pn.LayoutEvent(x=1, y=2, width=3, height=4),
        pn.ScrollEvent(x=0, y=10),
        pn.SelectionEvent(start=1, end=2),
        pn.KeyPressEvent(key="a"),
        pn.ContentSizeEvent(width=100, height=20),
        pn.ImageLoadEvent(width=10, height=10),
        pn.WebNavigationEvent(url="https://a.b", loading=False, can_go_back=False, can_go_forward=False),
    ],
)
def test_event_records_are_frozen_and_slotted(record: object) -> None:
    assert dataclasses.is_dataclass(record)
    assert not hasattr(record, "__dict__")
    field = dataclasses.fields(record)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(record, field, None)


def test_scroll_event_geometry_defaults_to_zero() -> None:
    event = pn.ScrollEvent(x=1.0, y=2.0)
    assert (event.content_width, event.content_height, event.viewport_width, event.viewport_height) == (0, 0, 0, 0)


# ======================================================================
# Native payloads decode into the records through the contract
# ======================================================================


def test_scroll_view_on_scroll_decodes_offset_only_payload() -> None:
    (event,) = COMPONENTS["ScrollView"].decode_event("on_scroll", [{"x": 0, "y": 42}])
    assert event == pn.ScrollEvent(x=0.0, y=42.0)
    (full,) = COMPONENTS["ScrollView"].decode_event(
        "on_scroll_end_drag",
        [
            {
                "x": 0,
                "y": 42,
                "content_width": 320,
                "content_height": 2000,
                "viewport_width": 320,
                "viewport_height": 600,
            }
        ],
    )
    assert full.content_height == 2000.0
    assert full.viewport_height == 600.0


def test_text_input_events_decode_into_records() -> None:
    schema = COMPONENTS["TextInput"]
    (selection,) = schema.decode_event("on_selection_change", [{"start": 1, "end": 3}])
    assert selection == pn.SelectionEvent(start=1, end=3)
    (key,) = schema.decode_event("on_key_press", [{"key": "Backspace"}])
    assert key == pn.KeyPressEvent(key="Backspace")
    (size,) = schema.decode_event("on_content_size_change", [{"width": 200, "height": 48}])
    assert size == pn.ContentSizeEvent(width=200.0, height=48.0)


def test_on_layout_is_typed_on_every_view() -> None:
    for name in ("View", "Column", "Row", "Pressable", "Text", "Image", "ScrollView"):
        (event,) = COMPONENTS[name].decode_event("on_layout", [{"x": 1, "y": 2, "width": 3, "height": 4}])
        assert event == pn.LayoutEvent(x=1.0, y=2.0, width=3.0, height=4.0)


def test_text_span_press_event_carries_the_span_index() -> None:
    assert COMPONENTS["Text"].decode_event("on_span_press", [2]) == [2]
    with pytest.raises(TypeError):
        COMPONENTS["Text"].decode_event("on_span_press", ["nope"])


def test_accessibility_action_event_carries_the_action_name() -> None:
    assert COMPONENTS["View"].decode_event("on_accessibility_action", ["increment"]) == ["increment"]


# ======================================================================
# on_layout wrapper (the layout pass reports frames as dicts)
# ======================================================================


def test_layout_callback_converts_dict_payloads_and_passes_records_through() -> None:
    seen: list = []
    wrapped = _layout_callback(seen.append)
    assert isinstance(wrapped, _LayoutCallback)
    wrapped({"x": 1, "y": 2, "width": 3, "height": 4})
    wrapped(pn.LayoutEvent(x=5, y=6, width=7, height=8))
    assert seen == [pn.LayoutEvent(x=1.0, y=2.0, width=3.0, height=4.0), pn.LayoutEvent(x=5, y=6, width=7, height=8)]
    assert _layout_callback(None) is None
    assert _layout_callback(wrapped) is wrapped


def test_layout_callback_leaves_animated_events_alone() -> None:
    value = pn.AnimatedValue(0.0)
    handler = pn.Animated.event(width=value)
    assert _layout_callback(handler) is handler
    el = pn.View(on_layout=handler)
    assert el.props["on_layout"] is handler


def test_factories_wrap_on_layout() -> None:
    frames: list = []
    el = pn.View(on_layout=frames.append)
    el.props["on_layout"]({"x": 0, "y": 0, "width": 10, "height": 20})
    assert frames == [pn.LayoutEvent(x=0.0, y=0.0, width=10.0, height=20.0)]


def test_scroll_event_fields_match_the_animated_event_binding_names() -> None:
    """``Animated.event(on_scroll, y=value)`` reads payload attributes by name, so the wire keys are the field names."""
    import dataclasses

    names = {field.name for field in dataclasses.fields(pn.ScrollEvent)}
    assert {"x", "y", "content_width", "content_height", "viewport_width", "viewport_height"} == names
    event = pn.ScrollEvent(x=0, y=33)
    assert getattr(event, "y") == 33
