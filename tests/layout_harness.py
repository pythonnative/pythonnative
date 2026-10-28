"""Lay out small view trees in the renderer core's Yoga engine.

Layout runs in the shared C++ core (RFC 0007). ``lay_out`` commits a tree
of [`Box`][tests.layout_harness.Box] nodes to its own fake surface,
requests a layout, and copies each node's frame back onto it, so tests
read ``x``, ``y``, ``width``, and ``height`` relative to the parent the
way the platforms receive them.

Frames come from the commit's layout result rather than from mounted
views, so view flattening doesn't hide layout-only nodes.

The core always lays out in a finite viewport. Passing ``math.inf`` for
one axis lays the root out as a ``VirtualList`` row instead, which the
core sizes with an undefined main axis, as an unbounded parent would.
Passing it for both places the root in a content-sized slot.
"""

from __future__ import annotations

import itertools
import json
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pythonnative  # noqa: F401  # registers the built-in contracts
from pythonnative.bridge import contract_document
from pythonnative.bridge.core import PROTOCOL_VERSION
from pythonnative.bridge.fake import FakeTransport

Measure = Callable[[float, float], Tuple[float, float]]
"""``measure(max_width, max_height) -> (width, height)`` for a leaf; ``inf`` means unbounded."""

_surfaces = itertools.count(2000)

# The viewport's size on an unbounded axis, which the root never sees.
_SLOT = (320.0, 480.0)
_EMPTY_DATASET: Dict[str, Any] = {"base": 0, "revision": 1, "changes": [["reset", []]]}


class Box:
    """One node in a layout scenario: a component, its props, and its children.

    Args:
        style: Props for the component (layout style keys and anything
            else the component's contract accepts).
        children: Child boxes, in order.
        measure: Natural size for a leaf. A box with ``measure`` is a
            ``Text`` the fake platform measures with this function.
        component: The built-in component to create (``View`` by
            default, ``Text`` when ``measure`` is given).
    """

    def __init__(
        self,
        style: Optional[Dict[str, Any]] = None,
        children: Optional[Sequence["Box"]] = None,
        *,
        measure: Optional[Measure] = None,
        component: Optional[str] = None,
    ) -> None:
        self.style: Dict[str, Any] = dict(style or {})
        self.children: List[Box] = list(children or [])
        self.measure = measure
        self.component = component or ("Text" if measure is not None else "View")
        self.tag = 0
        self.x = self.y = self.width = self.height = 0.0

    @property
    def frame(self) -> Tuple[float, float, float, float]:
        """``(x, y, width, height)`` relative to the parent."""
        return (self.x, self.y, self.width, self.height)

    def walk(self) -> Iterable["Box"]:
        """This box and every descendant, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def __repr__(self) -> str:
        return f"<Box {self.component} tag={self.tag} frame={self.frame}>"


class Layout:
    """A laid-out tree on its own core surface, which tests can update and lay out again."""

    def __init__(self, root: Box, width: float, height: float) -> None:
        self.root = root
        self.surface = next(_surfaces)
        self.transport = FakeTransport(surface=self.surface)
        self.transport.set_callback(lambda kind, tag, name, payload: None)
        self.transport.load_contracts(contract_document())
        self.transport.measurer = self._measure
        self.revision = 0
        self.frames: Dict[int, Tuple[float, float, float, float]] = {}
        tags = itertools.count(1)
        ops: List[List[Any]] = []

        def create(box: Box) -> int:
            box.tag = next(tags)
            ops.append(["c", box.tag, box.component, dict(box.style)])
            for index, child in enumerate(box.children):
                ops.append(["i", box.tag, create(child), index])
            return box.tag

        unbounded_width, unbounded_height = math.isinf(width), math.isinf(height)
        self.viewport = (
            _SLOT[0] if unbounded_width else float(width),
            _SLOT[1] if unbounded_height else float(height),
        )
        if unbounded_width and unbounded_height:
            # No core path lays a root out with both axes undefined, so the
            # root sits on the main axis of a row and then a column, both
            # aligned to the start: its width and height fit its content.
            # Yoga sizes it in a measure pass there, so percentages under it
            # resolve against the slot rather than to auto, and a baseline
            # row doesn't grow for a fixed-size container's descent.
            column = Box({"align_items": "flex_start"}, [root])
            top = create(Box({"flex_direction": "row", "align_items": "flex_start"}, [column]))
        elif unbounded_width or unbounded_height:
            # A list lays its rows out with an undefined main axis and its
            # own size on the cross axis, exactly as Yoga lays out a root
            # whose available size is undefined on one axis.
            extent = {"height": self.viewport[1]} if unbounded_width else {"width": self.viewport[0]}
            rows = Box(
                {"dataset": _EMPTY_DATASET, "horizontal": unbounded_width, **extent}, [root], component="VirtualList"
            )
            top = create(Box({}, [rows]))
        else:
            top = create(root)
        self._boxes: Dict[int, Box] = {box.tag: box for box in root.walk()}
        self.roots = [top]
        self._commit(ops)

    def _measure(
        self, tag: int, component: str, props: Dict[str, Any], max_width: float, max_height: float
    ) -> Tuple[float, float]:
        box = self._boxes.get(tag)
        if box is None or box.measure is None:
            return (0.0, 0.0)
        return box.measure(max_width, max_height)

    def _commit(self, ops: List[List[Any]]) -> None:
        envelope = {
            "version": PROTOCOL_VERSION,
            "application": "layout",
            "surface": self.surface,
            "revision": self.revision + 1,
            "ops": ops,
            "layout": {
                "roots": self.roots,
                "width": self.viewport[0],
                "height": self.viewport[1],
                "selective": False,
            },
        }
        ack = json.loads(self.transport.commit(json.dumps(envelope)))
        if not ack.get("ok"):
            raise ValueError(f"The core rejected the commit: {ack.get('error')}")
        self.revision += 1
        # The core reports only frames that changed, so merge them.
        for tag, x, y, w, h in ack["layout"]["frames"]:
            self.frames[int(tag)] = (float(x), float(y), float(w), float(h))
        for tag, box in self._boxes.items():
            if tag not in self.frames:
                raise AssertionError(f"the core never laid out {box!r}")
            box.x, box.y, box.width, box.height = self.frames[tag]

    def update(self, box: Box, props: Optional[Dict[str, Any]] = None, removed: Sequence[str] = ()) -> None:
        """Change ``box``'s props, then lay the tree out again."""
        props = dict(props or {})
        box.style.update(props)
        for key in removed:
            box.style.pop(key, None)
        self._commit([["u", box.tag, props, list(removed)]])


def lay_out(root: Box, width: float = 320, height: float = 480) -> Layout:
    """Lay out ``root`` in a ``width`` by ``height`` space (``math.inf`` for unbounded)."""
    return Layout(root, width, height)


__all__ = ["Box", "Layout", "Measure", "lay_out"]
