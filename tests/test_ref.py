"""Tests for the reconciler's ``ref`` prop support."""

from __future__ import annotations

from typing import Any, Dict

from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.hooks import Ref, use_ref
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend as MockBackend
from pythonnative.testing import FakeView as MockView


def test_ref_populated_on_mount() -> None:
    ref: Ref[Any] = Ref()
    el = Element("Text", {"text": "hi", "ref": ref}, [])
    backend = MockBackend()
    Reconciler(backend).mount(el)
    assert ref.current is not None
    assert isinstance(ref.current, MockView)
    assert ref.current.type_name == "Text"
    assert ref._pn_tag is not None


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
    first_view = old_ref.current

    rec.reconcile(Element("Text", {"text": "a", "ref": new_ref}, []))
    assert old_ref.current is None
    assert new_ref.current is first_view


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
    assert ref.current is not None
    assert isinstance(ref.current, MockView)


def test_ref_frame_mirrored_after_layout() -> None:
    """The layout pass mirrors the committed frame onto ``ref._pn_frame``."""
    ref: Ref[Any] = Ref()
    backend = MockBackend()
    rec = Reconciler(backend)
    child = Element("View", {"ref": ref, "height": 40}, [])
    rec.mount(Element("View", {}, [child]))
    rec.set_viewport_size(200.0, 100.0)
    assert ref._pn_frame is not None
    _x, _y, w, h = ref._pn_frame
    assert (w, h) == (200.0, 40.0)
