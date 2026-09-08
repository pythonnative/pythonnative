"""Reconciler package: turns element trees into batched native mutations.

The public surface is [`Reconciler`][pythonnative.reconciler.core.Reconciler] and
[`VNode`][pythonnative.reconciler.vnode.VNode]; the remaining modules are
implementation detail:

- ``core``: render, diff, commit.
- ``boundaries``: ``ErrorBoundary``
  and ``Suspense``.
- ``layout_pass``: the flexbox
  pass and frame diffing.
- ``children``: minimal move
  planning for keyed child lists.
- ``vnode``: the mounted-tree node and
  pure helpers.
"""

from .children import plan_child_moves
from .core import Reconciler
from .vnode import VNode, next_tag, normalize_children, shallow_equal_props

__all__ = [
    "Reconciler",
    "VNode",
    "next_tag",
    "normalize_children",
    "plan_child_moves",
    "shallow_equal_props",
]
