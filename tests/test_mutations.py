"""Tests for the batched mutation protocol between reconciler and backend.

These tests pin down the *transaction semantics* of commits: what ops a
mount/re-render/unmount emits, how they're batched into single
``apply_mutations`` calls, and the minimality guarantees (no-op renders
emit nothing, frame diffing suppresses unchanged frames, callback
identity changes never cross the bridge).
"""

from __future__ import annotations

from typing import Any, List, Tuple

from pythonnative.element import Element
from pythonnative.events import dispatch_event
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend


def _text(value: str, key: str | None = None, **props: Any) -> Element:
    return Element("Text", {"text": value, **props}, [], key=key)


def _column(*children: Element) -> Element:
    return Element("Column", {}, list(children))


def _mounted(el: Element) -> Tuple[Reconciler, FakeBackend]:
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    rec.mount(el)
    return rec, backend


def _ops_since(backend: FakeBackend, marker: int) -> List[Any]:
    return backend.ops[marker:]


# ======================================================================
# Mount transactions
# ======================================================================


def test_mount_commits_single_batch() -> None:
    _rec, backend = _mounted(_column(_text("a"), _text("b")))
    # One apply_mutations call for the whole tree (layout is deferred
    # until the host supplies a viewport).
    assert len(backend.batches) == 1
    kinds = {op[0] for op in backend.batches[0]}
    assert kinds == {"create", "insert_child"}


def test_mount_creates_parents_before_inserting_children() -> None:
    _rec, backend = _mounted(_column(_text("a"), _text("b")))
    seen_kinds = [op[0] for op in backend.ops]
    first_insert = seen_kinds.index("insert_child")
    # Every create that an insert references precedes it; FakeBackend
    # would raise on unknown tags, so here we just pin the shape: 3
    # creates, 2 inserts.
    assert seen_kinds[:first_insert].count("create") >= 2
    assert seen_kinds.count("create") == 3
    assert seen_kinds.count("insert_child") == 2


def test_layout_pass_flushes_frames_as_followup_batch() -> None:
    rec, backend = _mounted(_column(_text("a"), _text("b")))
    marker = len(backend.ops)

    rec.set_viewport_size(320.0, 640.0)

    new_ops = _ops_since(backend, marker)
    assert new_ops, "viewport arrival must trigger a layout flush"
    assert {op[0] for op in new_ops} == {"set_frame"}
    # The root's frame is host-owned and never framed by layout.
    root = backend.views[rec.root_tag]
    assert root.frame == (0.0, 0.0, 0.0, 0.0)
    # Children got real frames (FakeBackend reports 60x16 Text intrinsics).
    text = root.find_first("Text")
    assert text is not None
    assert text.frame[2] > 0 and text.frame[3] > 0


# ======================================================================
# Update minimality
# ======================================================================


def test_prop_change_emits_minimal_update() -> None:
    rec, backend = _mounted(_column(_text("a"), _text("b")))
    marker = len(backend.ops)

    rec.reconcile(_column(_text("a"), _text("B!")))

    new_ops = _ops_since(backend, marker)
    assert new_ops == [("update", "Text", new_ops[0][2], ("text",))]


def test_identical_rerender_emits_nothing() -> None:
    rec, backend = _mounted(_column(_text("a"), _text("b")))
    batches_before = len(backend.batches)

    rec.reconcile(_column(_text("a"), _text("b")))

    assert len(backend.batches) == batches_before


def test_callback_identity_change_never_crosses_the_bridge() -> None:
    hits: List[str] = []

    def first() -> None:
        hits.append("first")

    def second() -> None:
        hits.append("second")

    rec, backend = _mounted(Element("Button", {"title": "Go", "on_press": first}, []))
    tag = rec.root_tag
    assert tag is not None
    batches_before = len(backend.batches)

    rec.reconcile(Element("Button", {"title": "Go", "on_press": second}, []))

    # No native traffic, yet the registry now routes to the new closure.
    assert len(backend.batches) == batches_before
    dispatch_event(tag, "on_press")
    assert hits == ["second"]


def test_removed_prop_signaled_with_none() -> None:
    rec, backend = _mounted(_text("a", color="#ff0000"))
    marker = len(backend.ops)

    rec.reconcile(_text("a"))

    new_ops = _ops_since(backend, marker)
    assert len(new_ops) == 1
    assert new_ops[0][0] == "update" and new_ops[0][3] == ("color",)
    assert backend.views[rec.root_tag].props["color"] is None


def test_frame_diffing_suppresses_unchanged_frames() -> None:
    rec, backend = _mounted(_column(_text("a"), _text("b")))
    rec.set_viewport_size(320.0, 640.0)
    marker = len(backend.ops)

    # FakeBackend reports the same intrinsic size for any text, so this
    # re-render changes a prop but no geometry.
    rec.reconcile(_column(_text("a"), _text("c")))

    new_ops = _ops_since(backend, marker)
    assert [op[0] for op in new_ops] == ["update"]


# ======================================================================
# Reorders and removals
# ======================================================================


def test_keyed_reorder_moves_views_without_recreating() -> None:
    rec, backend = _mounted(_column(_text("a", key="a"), _text("b", key="b"), _text("c", key="c")))
    root = backend.views[rec.root_tag]
    ids_before = [c.id for c in root.children]
    marker = len(backend.ops)

    rec.reconcile(_column(_text("c", key="c"), _text("a", key="a"), _text("b", key="b")))

    new_ops = _ops_since(backend, marker)
    kinds = {op[0] for op in new_ops}
    assert "create" not in kinds and "destroy" not in kinds
    assert "insert_child" in kinds, "a reorder is expressed as move-aware inserts"
    assert [c.id for c in root.children] == [ids_before[2], ids_before[0], ids_before[1]]


def test_dropping_a_child_destroys_only_that_child() -> None:
    rec, backend = _mounted(_column(_text("a", key="a"), _text("b", key="b")))
    marker = len(backend.ops)

    rec.reconcile(_column(_text("a", key="a")))

    new_ops = _ops_since(backend, marker)
    assert [op[0] for op in new_ops].count("destroy") == 1
    assert backend.live_view_count() == 2  # Column + remaining Text


def test_subtree_replacement_destroys_children_first() -> None:
    inner = Element("Row", {}, [_text("deep")])
    rec, backend = _mounted(_column(inner))
    root = backend.views[rec.root_tag]
    row = root.find_first("Row")
    deep = root.find_first("Text")
    assert row is not None and deep is not None
    marker = len(backend.ops)

    # Changing the element type forces a teardown of the Row subtree.
    rec.reconcile(_column(_text("flat")))

    destroys = [op for op in _ops_since(backend, marker) if op[0] == "destroy"]
    assert [op[1] for op in destroys] == [deep.id, row.id], "children precede parents"


def test_unmount_destroys_every_view_in_one_batch() -> None:
    rec, backend = _mounted(_column(_text("a"), _text("b")))
    batches_before = len(backend.batches)

    rec.unmount()

    assert backend.live_view_count() == 0
    assert len(backend.batches) == batches_before + 1
    assert {op[0] for op in backend.batches[-1]} == {"destroy"}


# ======================================================================
# State-driven local re-renders
# ======================================================================


def test_flush_dirty_commits_one_transaction_for_many_setters() -> None:
    from pythonnative.component import component
    from pythonnative.hooks import use_state

    setters: List[Any] = []

    @component
    def Cell(label: str) -> Element:
        value, set_value = use_state(0)
        setters.append(set_value)
        return _text(f"{label}:{value}")

    rec, backend = _mounted(_column(Cell(label="x"), Cell(label="y")))
    batches_before = len(backend.batches)

    # Two independent components dirtied, one flush => one batch.
    setters[0](1)
    setters[1](1)
    rec.flush_dirty()

    assert len(backend.batches) == batches_before + 1
    assert [op[0] for op in backend.batches[-1]] == ["update", "update"]
