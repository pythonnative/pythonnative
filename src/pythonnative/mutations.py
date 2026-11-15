"""Batched mutation protocol between the reconciler and native backends.

Every commit pass produces an ordered list of small mutation ops
referencing integer **tags** (stable per-view identifiers), and the
whole list is applied in a single
[`apply_mutations`][pythonnative.native_views.bridge_backend.BridgeBackend.apply_mutations]
call. The renderer core validates the batch, lays it out, and turns it
into a mount transaction for the platform's UI thread (RFC 0007); frames
never travel as ops.

Why tags instead of view objects?

- The diff phase runs *before* any native view exists, so ops cannot
  reference views directly.
- Tags give the native side a stable identity to key its own view
  registry, event routing, and animation bookkeeping on.
- A flat list of `(op, tag, payload)` tuples serializes directly into
  the bridge's transaction envelope, so one commit is one crossing.

Op ordering rules (the reconciler guarantees these):

1. A `CreateOp` for a tag precedes any other op referencing that tag.
2. `InsertOp` ops appear after both the parent and child exist.
3. `DestroyOp` ops are emitted children-first; handlers detach the view
   from its parent as part of destruction.
"""

from enum import Enum
from typing import Any, Dict, Optional, Union

__all__ = [
    "UNSET",
    "UnsetType",
    "CreateOp",
    "UpdateOp",
    "InsertOp",
    "DestroyOp",
    "Mutation",
]


class UnsetType(Enum):
    """The explicit absence of a native property, distinct from null."""

    VALUE = 0

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType.VALUE
"""Remove a property and restore its native default on the next commit."""


class _Op:
    """Shared value semantics for the op records: compared by type and fields. Treat them as immutable."""

    __slots__ = ()
    _fields: tuple[str, ...] = ()

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in self._fields)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={getattr(self, name)!r}" for name in self._fields)
        return f"{type(self).__name__}({fields})"


class CreateOp(_Op):
    """Create a native view for ``tag`` of element type ``type_name``.

    Attributes:
        tag: Unique integer identity assigned by the reconciler.
        type_name: Element type name (e.g. ``"Text"``).
        props: Initial *clean* props; callables have already been
            moved to the view's event handlers and replaced by the
            ``_pn_events`` name set.
    """

    __slots__ = ("tag", "type_name", "props")
    _fields = __slots__
    tag: int
    type_name: str
    props: Dict[str, Any]

    def __init__(self, tag: int, type_name: str, props: Optional[Dict[str, Any]] = None) -> None:
        self.tag = tag
        self.type_name = type_name
        self.props = {} if props is None else props


class UpdateOp(_Op):
    """Apply ``changed_props`` to the view registered under ``tag``.

    Removed props are signaled with ``UNSET``. ``None`` sets a nullable
    property to an explicit native null value.

    Attributes:
        tag: Unique integer identity of the target view.
        changed_props: Mapping of modified prop names to their new values.
            Removed props appear with the ``UNSET`` sentinel.
    """

    __slots__ = ("tag", "changed_props")
    _fields = __slots__
    tag: int
    changed_props: Dict[str, Any]

    def __init__(self, tag: int, changed_props: Optional[Dict[str, Any]] = None) -> None:
        self.tag = tag
        self.changed_props = {} if changed_props is None else changed_props


class InsertOp(_Op):
    """Ensure the child view sits at ``index`` inside the parent view.

    Handlers must treat this as *move-aware*: if the child is already
    attached to the parent at a different position, it is moved rather
    than duplicated. ``index`` is clamped by handlers to the current
    child count.

    Attributes:
        parent_tag: Integer tag of the container view.
        child_tag: Integer tag of the child view to insert or move.
        index: Zero-based insertion index, clamped by handlers to the
            current child count.
    """

    __slots__ = ("parent_tag", "child_tag", "index")
    _fields = __slots__
    parent_tag: int
    child_tag: int
    index: int

    def __init__(self, parent_tag: int, child_tag: int, index: int) -> None:
        self.parent_tag = parent_tag
        self.child_tag = child_tag
        self.index = index


class DestroyOp(_Op):
    """Release the native view registered under ``tag``.

    The backend drops its tag record and the native component manager
    releases platform resources (listeners, timers, image loads)
    eagerly instead of waiting for GC.

    Attributes:
        tag: Unique integer identity of the view to destroy.
    """

    __slots__ = ("tag",)
    _fields = __slots__
    tag: int

    def __init__(self, tag: int) -> None:
        self.tag = tag


Mutation = Union[CreateOp, UpdateOp, InsertOp, DestroyOp]
"""Union of every op type carried by a commit transaction."""
