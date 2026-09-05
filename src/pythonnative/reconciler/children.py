"""Pure planning of native child-list moves.

Given the tags a native container currently holds and the tags it
should hold after a pass, [`plan_child_moves`][pythonnative.reconciler.children.plan_child_moves]
returns the minimal sequence of ``(tag, index)`` insertions (with
move-aware ``insert_child`` semantics: a child already attached is
re-positioned) that transforms one into the other.

The algorithm keeps the longest increasing subsequence of surviving
children in place and moves only the rest, processing right to left so
every moved child is inserted directly before an already-settled
neighbor. That yields ``n - len(LIS)`` operations, the optimum for a
move-aware insert primitive.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["longest_increasing_subsequence", "plan_child_moves"]


def longest_increasing_subsequence(values: Sequence[int]) -> List[int]:
    """Return the indices (into ``values``) of one longest strictly increasing subsequence."""
    if not values:
        return []
    tails: List[int] = []  # values
    tails_idx: List[int] = []  # index into values of each tail
    prev: List[int] = [-1] * len(values)
    for i, v in enumerate(values):
        pos = bisect_left(tails, v)
        if pos == len(tails):
            tails.append(v)
            tails_idx.append(i)
        else:
            tails[pos] = v
            tails_idx[pos] = i
        prev[i] = tails_idx[pos - 1] if pos > 0 else -1
    out: List[int] = []
    cursor = tails_idx[-1]
    while cursor != -1:
        out.append(cursor)
        cursor = prev[cursor]
    out.reverse()
    return out


def plan_child_moves(before: Sequence[int], after: Sequence[int]) -> List[Tuple[int, int]]:
    """Compute ``(tag, index)`` insert ops turning ``before`` into ``after``.

    Args:
        before: Tags currently attached to the container, in order.
            Tags absent from ``after`` are assumed to be detached
            already (the reconciler destroys them first) and must not
            appear here.
        after: Desired child tags, in order. Tags absent from
            ``before`` are fresh children.

    Returns:
        Ordered insert operations. Applying each as "detach ``tag`` if
        attached, then insert at ``index``" reproduces ``after``.
    """
    if list(before) == list(after):
        return []
    position_after: Dict[int, int] = {tag: i for i, tag in enumerate(after)}
    # Surviving children in their current order, mapped to their target
    # positions; the LIS of that sequence is the set we never touch.
    surviving_targets = [position_after[tag] for tag in before if tag in position_after]
    keep_positions = set(surviving_targets[i] for i in longest_increasing_subsequence(surviving_targets))

    sim: List[int] = list(before)
    ops: List[Tuple[int, int]] = []
    anchor: Optional[int] = None
    for i in range(len(after) - 1, -1, -1):
        tag = after[i]
        if i in keep_positions:
            anchor = tag
            continue
        try:
            sim.remove(tag)
        except ValueError:
            pass
        index = sim.index(anchor) if anchor is not None else len(sim)
        sim.insert(index, tag)
        ops.append((tag, index))
        anchor = tag
    return ops
