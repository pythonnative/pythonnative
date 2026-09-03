"""In-memory backend implementing the batched mutation protocol.

[`FakeBackend`][pythonnative.testing.FakeBackend] speaks the same
protocol as the platform registries (``apply_mutations``,
``resolve_view``, ``measure_intrinsic``, ``command``, plus the animation
hooks) while keeping a real tree of
[`FakeView`][pythonnative.testing.FakeView] objects, so tests can assert
on structure, props, and frames without a device.

Unlike the production registries (which isolate per-op failures so a
bad prop can't desync a device), the fake **raises** on malformed
transactions (unknown tags, double destroys, inserting into a destroyed
parent) so reconciler bugs fail tests loudly.

Recorded op shapes (in ``FakeBackend.ops``):

- ``("create", type_name, view.id)``
- ``("update", type_name, view.id, tuple(sorted(changed_keys)))``
- ``("insert_child", parent.id, child.id, index)``
- ``("destroy", view.id)``
- ``("set_frame", view.id, x, y, w, h)``
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from ..mutations import CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp

__all__ = ["DEFAULT_INTRINSIC", "FakeBackend", "FakeView"]

DEFAULT_INTRINSIC: Dict[str, Tuple[float, float]] = {
    "Text": (60.0, 16.0),
    "Button": (80.0, 32.0),
    "Image": (40.0, 40.0),
    "TextInput": (120.0, 32.0),
    "TabBar": (320.0, 49.0),
}
"""Intrinsic sizes reported for content-sized leaves (what platform measure hooks would return)."""


class FakeView:
    """Simulated native view: type, props, children, and last frame.

    Attributes:
        tag: The reconciler-assigned tag (use with ``fire`` / events).
        type_name: Native type, e.g. ``"Text"``.
        props: Native-safe props (event callbacks are stripped; they
            live in the event registry keyed by ``tag``).
        children: Child views in order.
        frame: ``(x, y, width, height)`` from the last layout pass.
    """

    _next_id = 0

    def __init__(self, tag: int, type_name: str, props: Dict[str, Any]) -> None:
        FakeView._next_id += 1
        self.id = FakeView._next_id
        self.tag = tag
        self.type_name = type_name
        self.props: Dict[str, Any] = dict(props)
        self.children: List[FakeView] = []
        self.parent: Optional[FakeView] = None
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.destroyed = False

    def __repr__(self) -> str:
        label = self.text
        suffix = f" {label!r}" if label else ""
        return f"<{self.type_name} tag={self.tag}{suffix}>"

    # -- content --------------------------------------------------------

    @property
    def text(self) -> Optional[str]:
        """Visible text for text-bearing views (``Text.text``, ``Button.title``, ``TextInput.value``)."""
        for key in ("text", "title", "value", "placeholder"):
            value = self.props.get(key)
            if isinstance(value, str):
                return value
        return None

    @property
    def hidden(self) -> bool:
        """Whether this view is removed from layout (``display: "none"``)."""
        return self.props.get("display") == "none"

    @property
    def test_id(self) -> Optional[str]:
        """The ``test_id`` prop, if set."""
        return self.props.get("test_id")

    @property
    def label(self) -> Optional[str]:
        """The ``accessibility_label`` prop, if set."""
        return self.props.get("accessibility_label")

    # -- traversal ------------------------------------------------------

    def walk(self, *, include_hidden: bool = True) -> Iterator["FakeView"]:
        """Yield this view and every descendant, depth-first.

        With ``include_hidden=False`` subtrees under a ``display: "none"``
        view are skipped (what a user can see).
        """
        if not include_hidden and self.hidden:
            return
        yield self
        for child in self.children:
            yield from child.walk(include_hidden=include_hidden)

    def find_all(self, predicate_or_type: Any) -> List["FakeView"]:
        """Every view in this subtree matching a type name or predicate."""
        if isinstance(predicate_or_type, str):
            wanted = predicate_or_type

            def predicate(v: "FakeView") -> bool:
                return v.type_name == wanted

        else:
            predicate = predicate_or_type
        return [v for v in self.walk() if predicate(v)]

    def find_first(self, predicate_or_type: Any) -> Optional["FakeView"]:
        """Return the first view in this subtree matching a type name or predicate, or ``None``."""
        found = self.find_all(predicate_or_type)
        return found[0] if found else None

    def dump(self, indent: int = 0) -> str:
        """Indented, human-readable subtree (for failing-test output)."""
        line = " " * indent + repr(self)
        x, y, w, h = self.frame
        if w or h:
            line += f" @({x:g},{y:g} {w:g}x{h:g})"
        return "\n".join([line, *(c.dump(indent + 2) for c in self.children)])


class FakeBackend:
    """Tag-table backend recording one tuple per applied mutation.

    Args:
        intrinsic: Override the intrinsic sizes used by
            ``measure_intrinsic`` (defaults to
            [`DEFAULT_INTRINSIC`][pythonnative.testing.backend.DEFAULT_INTRINSIC]).
    """

    def __init__(self, intrinsic: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        self.intrinsic = dict(DEFAULT_INTRINSIC if intrinsic is None else intrinsic)
        self.views: Dict[int, FakeView] = {}
        self.ops: List[Any] = []
        self.batches: List[List[Any]] = []
        self.measure_calls: List[int] = []
        self.commands: List[Tuple[int, str, Dict[str, Any]]] = []
        self.animated: List[Tuple[int, str, Any]] = []
        self.last_create_props: Dict[str, Any] = {}
        self.last_update_changes: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Commit channel
    # ------------------------------------------------------------------

    def apply_mutations(self, ops: Sequence[Mutation]) -> None:
        """Apply one committed batch to the view tree, recording each op in ``ops`` and ``batches``.

        Raises ``AssertionError`` on malformed transactions (unknown tags, double creates or destroys).
        """
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
        """Return the live view registered under ``tag``, or ``None``."""
        return self.views.get(tag)

    def measure_intrinsic(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Return the configured intrinsic size for the view's type and record the call in ``measure_calls``.

        Unknown tags and types without an entry measure as ``(0.0, 0.0)``; the constraints are ignored.
        """
        view = self.views.get(tag)
        if view is None:
            return (0.0, 0.0)
        self.measure_calls.append(view.id)
        return self.intrinsic.get(view.type_name, (0.0, 0.0))

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Record an imperative view command in ``commands`` and return ``None``."""
        self.commands.append((tag, name, dict(args or {})))
        return None

    def set_animated_property(self, tag: int, prop_name: str, value: Any) -> None:
        """Record an animated property write in ``animated`` without touching ``props``."""
        self.animated.append((tag, prop_name, value))

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
        """Decline native animation (return ``False``) so animations run through the Python driver."""
        return False

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        """Do nothing; the fake never starts native animations."""
        return None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def live_view_count(self) -> int:
        """Return how many views are currently registered (created and not yet destroyed)."""
        return len(self.views)

    def ops_of(self, kind: str) -> List[Any]:
        """Every recorded op tuple whose first element is ``kind``."""
        return [op for op in self.ops if op[0] == kind]

    def detached_views(self, type_name: Optional[str] = None) -> List[FakeView]:
        """Live views never inserted into a parent (``Portal`` overlays, the root)."""
        out = [v for v in self.views.values() if v.parent is None]
        if type_name is not None:
            out = [v for v in out if v.type_name == type_name]
        return out
