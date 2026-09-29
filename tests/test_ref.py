"""Tests for the reconciler's ``ref`` prop support and the handles it publishes."""

from __future__ import annotations

from typing import Any, Dict

from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.handles import ScrollViewHandle, TextInputHandle, ViewHandle
from pythonnative.hooks import Ref, use_ref
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend as MockBackend


def test_ref_populated_with_handle_on_mount() -> None:
    ref: Ref[Any] = Ref()
    el = Element("Text", {"text": "hi", "ref": ref}, [])
    backend = MockBackend()
    Reconciler(backend).mount(el)
    assert isinstance(ref.current, ViewHandle)
    assert ref.current.type_name == "Text"
    assert ref.current.tag in backend.views
    assert backend.views[ref.current.tag].type_name == "Text"


def test_ref_handle_type_follows_element_type() -> None:
    field: Ref[Any] = Ref()
    scroller: Ref[Any] = Ref()
    backend = MockBackend()
    Reconciler(backend).mount(
        Element("Column", {}, [Element("TextInput", {"ref": field}, []), Element("ScrollView", {"ref": scroller}, [])])
    )
    assert isinstance(field.current, TextInputHandle)
    assert isinstance(scroller.current, ScrollViewHandle)
    field.current.focus()
    assert backend.commands[-1] == (field.current.tag, "focus", {})


def test_ref_not_passed_to_backend() -> None:
    ref: Ref[Any] = Ref()
    el = Element("Text", {"text": "hi", "ref": ref}, [])
    backend = MockBackend()
    Reconciler(backend).mount(el)
    assert "ref" not in backend.last_create_props


def test_ref_cleared_on_unmount() -> None:
    ref: Ref[Any] = Ref()
    el = Element("Text", {"text": "hi", "ref": ref}, [])
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(el)
    assert ref.current is not None

    # Replace with a different element type; destroys the old tree.
    rec.reconcile(Element("Button", {"title": "ok"}, []))
    assert ref.current is None


def test_ref_repointed_when_ref_swapped() -> None:
    """Swapping the ref on update should populate the new and clear the old."""
    old_ref: Ref[Any] = Ref()
    new_ref: Ref[Any] = Ref()

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(Element("Text", {"text": "a", "ref": old_ref}, []))
    assert old_ref.current is not None
    first_tag = old_ref.current.tag

    rec.reconcile(Element("Text", {"text": "a", "ref": new_ref}, []))
    assert old_ref.current is None
    assert isinstance(new_ref.current, ViewHandle)
    assert new_ref.current.tag == first_tag, "the same native view is described by the new handle"


def test_ref_ignored_when_not_a_ref() -> None:
    """Non-``Ref`` values under ``ref`` are silently ignored, no crashes."""
    el = Element("Text", {"text": "hi", "ref": "not-a-ref"}, [])
    backend = MockBackend()
    Reconciler(backend).mount(el)


def test_ref_diff_does_not_trigger_native_update() -> None:
    """Changing only the ref identity should NOT call update_view."""
    backend = MockBackend()
    rec = Reconciler(backend)
    ref_a: Ref[Any] = Ref()
    ref_b: Ref[Any] = Ref()

    rec.mount(Element("Text", {"text": "x", "ref": ref_a}, []))
    backend.last_update_changes = {}

    rec.reconcile(Element("Text", {"text": "x", "ref": ref_b}, []))
    assert backend.last_update_changes == {}
    assert ref_a.current is None
    assert ref_b.current is not None


def test_use_ref_in_component_populated_after_mount() -> None:
    captured: Dict[str, Any] = {}

    @component
    def Comp() -> Element:
        ref = use_ref(None)
        captured["ref"] = ref
        return Element("Text", {"text": "hi", "ref": ref}, [])

    Reconciler(MockBackend()).mount(Comp())
    ref = captured["ref"]
    assert isinstance(ref.current, ViewHandle)


def test_handle_frame_follows_layout() -> None:
    """The layout pass writes the committed frame onto ``ref.current.frame``."""
    ref: Ref[Any] = Ref()
    backend = MockBackend()
    rec = Reconciler(backend)
    child = Element("View", {"ref": ref, "height": 40}, [])
    rec.mount(Element("View", {}, [child]))
    assert ref.current.frame is None, "no viewport yet, so no frame"
    rec.set_viewport_size(200.0, 100.0)
    frame = ref.current.frame
    assert frame is not None
    assert (frame.width, frame.height) == (200.0, 40.0)

    rec.reconcile(Element("View", {}, [Element("View", {"ref": ref, "height": 70}, [])]))
    assert ref.current.frame.height == 70.0


def test_handle_frame_known_at_mount_when_viewport_set_first() -> None:
    """Frames computed in the mount commit land on the handle even though the ref attaches afterwards."""
    ref: Ref[Any] = Ref()
    rec = Reconciler(MockBackend())
    rec.set_viewport_size(200.0, 100.0)
    rec.mount(Element("View", {}, [Element("View", {"ref": ref, "height": 40}, [])]))
    assert ref.current.frame is not None
    assert ref.current.frame.height == 40.0


def test_ref_has_no_private_tag_or_frame_attributes() -> None:
    ref: Ref[Any] = Ref()
    Reconciler(MockBackend()).mount(Element("Text", {"text": "hi", "ref": ref}, []))
    assert not hasattr(ref, "_pn_tag")
    assert not hasattr(ref, "_pn_frame")
