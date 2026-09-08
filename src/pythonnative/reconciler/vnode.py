"""Mounted-tree nodes and the pure helpers the reconciler shares.

[`VNode`][pythonnative.reconciler.VNode] pairs an
[`Element`][pythonnative.Element] with the identity of the native view
it produced (its **tag**) plus the bookkeeping the reconciler needs
across passes (layout cache, boundary state, hook state).

Everything in this module is side-effect free with respect to the
native layer.
"""

from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional, Set, Tuple

from .. import diagnostics
from ..component import Component
from ..element import ERROR_BOUNDARY, FRAGMENT, SUSPENSE, Element, type_label
from ..hooks import Context, HookState
from ..layout import LayoutNode

__all__ = [
    "DETACHED_TYPES",
    "VNode",
    "next_tag",
    "normalize_children",
    "shallow_equal_props",
]

# Native element types whose subtree is laid out against the viewport
# in a detached pass instead of participating in the main layout flow.
# Their handlers host the children in a separately presented native
# container (a modal, an overlay, a pushed screen).
DETACHED_TYPES = frozenset({"Modal", "Portal"})

# Tags are globally unique so multiple reconcilers (screens, list rows)
# can share one registry without collisions.
_tag_counter = itertools.count(1)


def next_tag() -> int:
    """Allocate a fresh, process-unique view tag."""
    return next(_tag_counter)


def shallow_equal_props(old: dict, new: dict) -> bool:
    """Return whether two prop dicts are equal under shallow comparison.

    Used by [`memo`][pythonnative.memo] to skip re-rendering when none
    of a component's props changed identity. Callables only count as
    equal if they're the *same object*; fresh closures always invalidate
    the memo (matching React's behavior; pair with
    [`use_callback`][pythonnative.use_callback] when stability matters).
    """
    if old is new:
        return True
    if old.keys() != new.keys():
        return False
    for key, ov in old.items():
        nv = new[key]
        if ov is nv:
            continue
        if callable(ov) or callable(nv):
            return False
        try:
            if ov != nv:
                return False
        except Exception:
            return False
    return True


def normalize_children(children: Any, owner: str = "") -> List[Element]:
    """Normalize arbitrary render output into a flat list of Elements.

    Accepts a single element, ``None``, ``True``/``False`` (both
    skipped, enabling inline conditionals like ``cond and Text(...)``),
    lists/tuples/generators (flattened recursively), and unkeyed
    Fragments (expanded inline so they never touch the native tree).
    Keyed Fragments are preserved so they can participate in keyed
    reconciliation as a unit.

    Non-Element values other than the above are dropped with a
    dev-mode warning.
    """
    out: List[Element] = []

    def add(item: Any) -> None:
        if item is None or item is True or item is False:
            return
        if isinstance(item, Element):
            if item.type is FRAGMENT and item.key is None:
                for sub in item.children:
                    add(sub)
                return
            out.append(item)
            return
        if isinstance(item, (str, bytes)):
            diagnostics.warn_once(
                f"Ignoring bare string child {item!r}"
                + (f" under {owner}" if owner else "")
                + ". Wrap text in pn.Text(...).",
                key=f"strchild:{owner}",
            )
            return
        try:
            iterator = iter(item)
        except TypeError:
            diagnostics.warn_once(
                f"Ignoring non-Element child {item!r} ({type(item).__name__})"
                + (f" under {owner}" if owner else "")
                + ". Children must be Elements, iterables of Elements, or None/False for conditionals.",
                key=f"badchild:{owner}:{type(item).__name__}",
            )
            return
        for sub in iterator:
            add(sub)

    add(children)

    if diagnostics.is_dev() and len(out) > 1:
        seen: Set[Any] = set()
        for el in out:
            if el.key is None:
                continue
            if el.key in seen:
                diagnostics.warn_once(
                    f"Duplicate key {el.key!r} among children"
                    + (f" of {owner}" if owner else "")
                    + ". Keys must be unique among siblings; duplicates break "
                    "keyed reconciliation and can cross-wire component state.",
                    key=f"dupkey:{owner}:{el.key!r}",
                )
            seen.add(el.key)
    return out


class VNode:
    """A mounted [`Element`][pythonnative.Element] plus its native identity.

    The reconciler walks parallel trees of ``VNode`` and incoming
    ``Element`` to compute the minimal set of native mutations.

    Attributes:
        element: The ``Element`` last rendered into this slot.
        tag: Integer identity of the underlying native view. Native
            elements own a fresh tag; transparent wrappers (components,
            providers, boundaries, keyed fragments) delegate the tag of
            their first native root. ``None`` when the subtree renders
            no native view.
        native_view: The platform-native view object, resolved from the
            backend after commit. ``None`` for wrappers that rendered
            nothing.
        children: Ordered list of child ``VNode`` instances.
        parent: The owning ``VNode``, or ``None`` for the tree root.
        hook_state: The component's
            [`HookState`][pythonnative.hooks.HookState] when the node
            wraps a component, otherwise ``None``.
        mounted: ``False`` once the node has been destroyed, so stale
            entries in the reconciler's dirty set are skipped.
    """

    __slots__ = (
        "element",
        "tag",
        "native_view",
        "children",
        "parent",
        "hook_state",
        "mounted",
        "rendered",
        "clean_props",
        "measure_cache",
        "last_frame",
        "layout_node",
        "layout_dirty",
        "error",
        "suspense_showing_fallback",
        "suspense_hydration",
        "suspense_waits",
    )

    def __init__(self, element: Element, children: Optional[List["VNode"]] = None, tag: Optional[int] = None) -> None:
        self.element = element
        self.tag = tag
        self.native_view: Any = None
        self.children: List[VNode] = children if children is not None else []
        self.parent: Optional[VNode] = None
        self.hook_state: Optional[HookState] = None
        self.mounted: bool = True
        # The normalized element list a component body last produced.
        self.rendered: Optional[List[Element]] = None
        # Native-safe props (events and reconciler-owned keys stripped)
        # from the last commit; the baseline for prop diffing.
        self.clean_props: Dict[str, Any] = {}
        # Cache for the leaf intrinsic-size measure callback:
        # ``(max_w, max_h, width, height)``. Invalidated whenever the
        # node's props change, so unchanged leaves skip native
        # ``measure_intrinsic`` calls entirely.
        self.measure_cache: Optional[Tuple[float, float, float, float]] = None
        # Last frame sent to the native side; unchanged frames are
        # skipped (frame diffing).
        self.last_frame: Optional[Tuple[float, float, float, float]] = None
        # Cached LayoutNode reused across passes while the subtree is
        # clean (see the layout mixin).
        self.layout_node: Optional[LayoutNode] = None
        # True when this node's layout-relevant props or child list
        # changed since the last layout pass.
        self.layout_dirty: bool = True
        # For error-boundary nodes: the caught exception while the
        # fallback is showing, else ``None``.
        self.error: Optional[BaseException] = None
        # For Suspense nodes: whether the fallback is showing, the hook
        # states of suspended descendants preserved for the next retry
        # (keyed by ``(component identity, element key)``), and the ids
        # of waitables already wired to trigger a retry.
        self.suspense_showing_fallback: bool = False
        self.suspense_hydration: Optional[Dict[Tuple[int, Any], List[HookState]]] = None
        self.suspense_waits: Optional[Set[int]] = None

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @property
    def is_native(self) -> bool:
        """Whether this node owns a native view."""
        return isinstance(self.element.type, str)

    @property
    def is_component(self) -> bool:
        """Whether this node renders a user component (a ``@component`` function)."""
        return isinstance(self.element.type, Component)

    @property
    def is_provider(self) -> bool:
        """Whether this node is a context provider."""
        return isinstance(self.element.type, Context)

    @property
    def is_error_boundary(self) -> bool:
        """Whether this node is an ``ErrorBoundary``."""
        return self.element.type is ERROR_BOUNDARY

    @property
    def is_suspense(self) -> bool:
        """Whether this node is a ``Suspense`` boundary."""
        return self.element.type is SUSPENSE

    @property
    def label(self) -> str:
        """Human-readable name of the element type (for diagnostics and tree dumps)."""
        return type_label(self.element.type)

    def depth(self) -> int:
        """Return the number of ancestors above this node (the root has depth 0)."""
        depth = 0
        node = self.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    def __repr__(self) -> str:
        return f"VNode({self.label!r}, tag={self.tag}, children={len(self.children)})"
