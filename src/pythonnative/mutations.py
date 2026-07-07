"""Batched mutation protocol between the reconciler and native backends.

The reconciler no longer talks to the native layer one call at a time.
Instead, every commit pass produces an ordered list of small mutation
ops referencing integer **tags** (stable per-view identifiers), and the
whole list is applied in a single
[`apply_mutations`][pythonnative.native_views.NativeViewRegistry.apply_mutations]
call. This mirrors React Native's Fabric mounting layer: the diff phase
is pure, and the native side sees one coherent transaction per commit.

Why tags instead of view objects?

- The diff phase runs *before* any native view exists, so ops cannot
  reference views directly.
- Tags give the native side a stable identity to key its own view
  registry, event routing, and animation bookkeeping on.
- A flat list of `(op, tag, payload)` tuples is trivially serializable,
  which keeps the door open for applying mutations from a background
  thread or through a single JNI/ObjC crossing in the future.

Op ordering rules (the reconciler guarantees these):

1. A `CreateOp` for a tag precedes any other op referencing that tag.
2. `InsertOp` ops appear after both the parent and child exist.
3. `DestroyOp` ops are emitted children-first; handlers detach the view
   from its parent as part of destruction.
4. `SetFrameOp` ops are only emitted for frames that actually changed
   since the last layout pass (frame diffing).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Union

__all__ = [
    "CreateOp",
    "UpdateOp",
    "InsertOp",
    "DestroyOp",
    "SetFrameOp",
    "Mutation",
]


@dataclass(frozen=True)
class CreateOp:
    """Create a native view for ``tag`` of element type ``type_name``.

    Attributes:
        tag: Unique integer identity assigned by the reconciler.
        type_name: Element type name (e.g. ``"Text"``).
        props: Initial *clean* props; callables have already been
            routed to the [`EventRegistry`][pythonnative.events.EventRegistry]
            and replaced by the ``_pn_events`` name set.
    """

    tag: int
    type_name: str
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateOp:
    """Apply ``changed_props`` to the view registered under ``tag``.

    Removed props are signaled with a value of ``None``, matching the
    pre-existing handler contract.
    """

    tag: int
    changed_props: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InsertOp:
    """Ensure the child view sits at ``index`` inside the parent view.

    Handlers must treat this as *move-aware*: if the child is already
    attached to the parent at a different position, it is moved rather
    than duplicated. ``index`` is clamped by handlers to the current
    child count.
    """

    parent_tag: int
    child_tag: int
    index: int


@dataclass(frozen=True)
class DestroyOp:
    """Release the native view registered under ``tag``.

    The registry drops its tag record and calls the handler's
    ``destroy`` hook so platform resources (listeners, timers, image
    loads) can be released eagerly instead of waiting for GC.
    """

    tag: int


@dataclass(frozen=True)
class SetFrameOp:
    """Position and size the view registered under ``tag``.

    Coordinates are points relative to the parent's content origin,
    exactly as computed by the layout engine.
    """

    tag: int
    x: float
    y: float
    width: float
    height: float

    @property
    def frame(self) -> Tuple[float, float, float, float]:
        """Return ``(x, y, width, height)`` as a tuple."""
        return (self.x, self.y, self.width, self.height)


Mutation = Union[CreateOp, UpdateOp, InsertOp, DestroyOp, SetFrameOp]
"""Union of every op type carried by a commit transaction."""
