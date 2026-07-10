"""Shared in-memory backend implementing the batched mutation protocol.

Every unit test that drives a :class:`~pythonnative.reconciler.Reconciler`
uses this module instead of defining its own mock. ``FakeBackend``
implements the same protocol as
:class:`~pythonnative.native_views.NativeViewRegistry` (``apply_mutations``,
``resolve_view``, ``measure_intrinsic``, ``command``, plus the animation
hooks) while keeping a real tree of :class:`FakeView` objects so tests
can assert on structure, props, and frames.

Unlike the production registry (which isolates per-op failures so a bad
prop can't desync a device), the fake **raises** on malformed
transactions (unknown tags, double-destroys, inserting into a destroyed
parent) so reconciler bugs fail tests loudly instead of being swallowed.

Recorded op shapes (in ``FakeBackend.ops``):

- ``("create", type_name, view.id)``
- ``("update", type_name, view.id, tuple(sorted(changed_keys)))``
- ``("insert_child", parent.id, child.id, index)``
- ``("remove_child", parent.id, child.id)``
- ``("destroy", view.id)``
- ``("set_frame", view.id, x, y, w, h)``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from pythonnative.mutations import (
    CreateOp,
    DestroyOp,
    InsertOp,
    Mutation,
    SetFrameOp,
    UpdateOp,
)

# Intrinsic sizes reported for content-sized leaves, mirroring what the
# platform measure hooks would return for short sample content.
DEFAULT_INTRINSIC: Dict[str, Tuple[float, float]] = {
    "Text": (60.0, 16.0),
    "Button": (80.0, 32.0),
    "Image": (40.0, 40.0),
    "TextInput": (120.0, 32.0),
    "TabBar": (320.0, 49.0),
}


class FakeView:
    """Simulated native view: type, props, children, and last frame."""

    _next_id = 0

    def __init__(self, tag: int, type_name: str, props: Dict[str, Any]) -> None:
        FakeView._next_id += 1
        self.id = FakeView._next_id
        self.tag = tag
        self.type_name = type_name
        self.props: Dict[str, Any] = dict(props)
        self.children: List["FakeView"] = []
        self.parent: Optional["FakeView"] = None
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.destroyed = False

    def __repr__(self) -> str:
        return f"FakeView({self.type_name}#{self.id} tag={self.tag})"

    # -- tree helpers used by assertions ------------------------------

    def find_all(self, type_name: str) -> List["FakeView"]:
        """Return every view of ``type_name`` in this subtree (depth-first)."""
        out: List[FakeView] = []
        if self.type_name == type_name:
            out.append(self)
        for child in self.children:
            out.extend(child.find_all(type_name))
        return out

    def find_first(self, type_name: str) -> Optional["FakeView"]:
        """Return the first view of ``type_name`` in this subtree, or ``None``."""
        found = self.find_all(type_name)
        return found[0] if found else None


class FakeBackend:
    """Tag-table backend recording one tuple per applied mutation."""

    def __init__(self, intrinsic: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        self.intrinsic = dict(DEFAULT_INTRINSIC if intrinsic is None else intrinsic)
        self.views: Dict[int, FakeView] = {}
        self.ops: List[Any] = []
        self.batches: List[List[Any]] = []
        self.measure_calls: List[int] = []
        self.commands: List[Tuple[int, str, Dict[str, Any]]] = []
        self.animated: List[Tuple[int, str, Any]] = []
        # Convenience mirrors for prop-flow assertions (test_ref).
        self.last_create_props: Dict[str, Any] = {}
        self.last_update_changes: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Commit channel
    # ------------------------------------------------------------------

    def apply_mutations(self, ops: Sequence[Mutation]) -> None:
        batch: List[Any] = []
        for op in ops:
            recorded = self._apply_one(op)
            self.ops.append(recorded)
            batch.append(recorded)
        self.batches.append(batch)

    def _apply_one(self, op: Mutation) -> Tuple[Any, ...]:
        if isinstance(op, CreateOp):
            if op.tag in self.views:
                raise AssertionError(f"create: tag {op.tag} already registered")
            view = FakeView(op.tag, op.type_name, op.props)
            self.views[op.tag] = view
            self.last_create_props = dict(op.props)
            return ("create", op.type_name, view.id)

        if isinstance(op, UpdateOp):
            view = self._require(op.tag, "update")
            view.props.update(op.changed_props)
            self.last_update_changes = dict(op.changed_props)
            return ("update", view.type_name, view.id, tuple(sorted(op.changed_props)))

        if isinstance(op, InsertOp):
            parent = self._require(op.parent_tag, "insert_child")
            child = self._require(op.child_tag, "insert_child")
            # Move-aware: re-position when already attached (anywhere).
            if child.parent is not None:
                child.parent.children.remove(child)
                child.parent = None
            index = max(0, min(op.index, len(parent.children)))
            parent.children.insert(index, child)
            child.parent = parent
            return ("insert_child", parent.id, child.id, index)

        if isinstance(op, DestroyOp):
            view = self.views.pop(op.tag, None)
            if view is None:
                raise AssertionError(f"destroy: unknown tag {op.tag}")
            # Real handlers detach from the parent on destroy; the
            # reconciler's child diffing relies on this.
            if view.parent is not None:
                view.parent.children.remove(view)
                view.parent = None
            view.destroyed = True
            return ("destroy", view.id)

        if isinstance(op, SetFrameOp):
            view = self._require(op.tag, "set_frame")
            view.frame = (op.x, op.y, op.width, op.height)
            return ("set_frame", view.id, op.x, op.y, op.width, op.height)

        raise AssertionError(f"unknown mutation op: {op!r}")

    def _require(self, tag: int, op_name: str) -> FakeView:
        view = self.views.get(tag)
        if view is None:
            raise AssertionError(f"{op_name}: unknown tag {tag}")
        return view

    # ------------------------------------------------------------------
    # Imperative escape hatches
    # ------------------------------------------------------------------

    def resolve_view(self, tag: int) -> Optional[FakeView]:
        return self.views.get(tag)

    def measure_intrinsic(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        view = self.views.get(tag)
        if view is None:
            return (0.0, 0.0)
        self.measure_calls.append(view.id)
        return self.intrinsic.get(view.type_name, (0.0, 0.0))

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        self.commands.append((tag, name, dict(args or {})))
        return None

    def set_animated_property(self, tag: int, prop_name: str, value: Any) -> None:
        self.animated.append((tag, prop_name, value))

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
        return False

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        return None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def live_view_count(self) -> int:
        return len(self.views)

    def ops_of(self, kind: str) -> List[Any]:
        """Return every recorded op tuple whose first element is ``kind``."""
        return [op for op in self.ops if op[0] == kind]

    def detached_views(self, type_name: Optional[str] = None) -> List[FakeView]:
        """Return live views that were never inserted into a parent.

        ``Portal`` overlays are the main case: the reconciler creates
        them and inserts *children into them*, but never inserts the
        overlay itself anywhere (real handlers self-attach to a
        top-level container). Optionally filter by ``type_name``.
        """
        out = [v for v in self.views.values() if v.parent is None]
        if type_name is not None:
            out = [v for v in out if v.type_name == type_name]
        return out
