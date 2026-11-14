"""Mounted-tree nodes and the pure helpers the reconciler shares.

[`VNode`][pythonnative.reconciler.VNode] pairs an
[`Element`][pythonnative.Element] with the identity of the native view
it produced (its **tag**) plus the bookkeeping the reconciler needs
across passes (layout cache, boundary state, hook state).

[`child_slots`][pythonnative.reconciler.vnode.child_slots] turns the
children of an element, or the value a component returned, into a
child list: one entry per slot, ``None`` for an empty slot, and a group
element for a list, tuple, or generator.

Everything in this module is side-effect free with respect to the
native layer.
"""

from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .. import diagnostics
from .. import journal as _journal
from ..component import Component
from ..element import ERROR_BOUNDARY, FRAGMENT, STRICT_MODE, SUSPENSE, Element, type_label
from ..hooks import Context, HookState

__all__ = [
    "BOUNDARY",
    "COMPONENT",
    "DETACHED_TYPES",
    "NATIVE",
    "PROVIDER",
    "SUSPENSE_KIND",
    "VNode",
    "WRAPPER",
    "child_slots",
    "kind_of",
    "next_tag",
    "touch",
]

# Native element types whose subtree is laid out against the viewport
# in a detached pass instead of participating in the main layout flow.
# Their handlers host the children in a separately presented native
# container (a modal, an overlay, a pushed screen).
DETACHED_TYPES = frozenset({"Modal", "Portal"})

# Node kinds, fixed when the node is created.
NATIVE = 0
"""A native view: the element's type is a string."""
COMPONENT = 1
"""A ``@component`` instance."""
PROVIDER = 2
"""A context provider."""
BOUNDARY = 3
"""An ``ErrorBoundary``."""
SUSPENSE_KIND = 4
"""A ``Suspense`` boundary."""
WRAPPER = 5
"""A fragment, a group, or a ``StrictMode``: transparent, with only a child list."""

# Tags are globally unique so multiple reconcilers (screens, list rows)
# can share one registry without collisions.
_tag_counter = itertools.count(1)


def next_tag() -> int:
    """Allocate a fresh, process-unique view tag."""
    return next(_tag_counter)


def kind_of(type_obj: Any) -> int:
    """The node kind for an element type.

    Raises:
        TypeError: For anything that isn't an element type.
    """
    if type_obj.__class__ is str:
        return NATIVE
    if isinstance(type_obj, Component):
        return COMPONENT
    if isinstance(type_obj, Context):
        return PROVIDER
    if type_obj is FRAGMENT or type_obj is STRICT_MODE:
        return WRAPPER
    if type_obj is ERROR_BOUNDARY:
        return BOUNDARY
    if type_obj is SUSPENSE:
        return SUSPENSE_KIND
    if isinstance(type_obj, str):
        return NATIVE
    raise TypeError(
        f"Unsupported element type {type_obj!r}. Element types are native view names, "
        "@component functions, contexts (providers), or the structural types."
    )


# ----------------------------------------------------------------------
# Child lists
# ----------------------------------------------------------------------


def child_slots(children: Any, owner: str = "", *, returned: bool = False) -> Sequence[Optional[Element]]:
    """Turn children into a child list: one entry per slot.

    Each entry of ``children`` occupies one slot:

    - an [`Element`][pythonnative.Element] holds that element;
    - ``None``, ``False``, and ``True`` hold nothing, but keep the slot,
      so a conditional child never shifts its siblings;
    - a list, tuple, or generator is a **group**: a fragment element whose
      items form their own child list and are matched among themselves.

    The result is ``children`` itself when every entry is an element, so
    the common case allocates nothing.

    Args:
        children: The positional children of an element, or what a
            component returned.
        owner: Label of the element or component the children belong
            to, for diagnostics.
        returned: Whether ``children`` is a component's return value. A
            component that returns a list returns a child list (not a
            group), and one that returns a single element or ``None``
            returns a child list of one slot or none.
    """
    if returned:
        cls = children.__class__
        if cls is Element:
            return (children,)
        if children is None or children is True or children is False:
            return ()
        if cls is not list and cls is not tuple:
            if isinstance(children, (str, bytes)):
                _warn_string(children, owner)
                return ()
            try:
                children = tuple(children)
            except TypeError:
                _warn_value(children, owner)
                return ()
        slots = _slots(children, owner)
        if diagnostics._dev_mode:
            _check_list(slots, owner)
        return slots
    for child in children:
        if child.__class__ is not Element:
            slots = _slots(children, owner)
            if diagnostics._dev_mode:
                _check_duplicates(slots, owner)
            return slots
    if diagnostics._dev_mode and len(children) > 1:
        _check_duplicates(children, owner)
    return children


def _slots(children: Any, owner: str) -> List[Optional[Element]]:
    out: List[Optional[Element]] = []
    for child in children:
        if child.__class__ is Element or isinstance(child, Element):
            out.append(child)
        elif child is None or child is True or child is False:
            out.append(None)
        else:
            out.append(_group(child, owner))
    return out


def _group(items: Any, owner: str) -> Optional[Element]:
    """An implicit fragment for a list, tuple, or iterator child."""
    if isinstance(items, (str, bytes)):
        _warn_string(items, owner)
        return None
    try:
        entries = tuple(items)
    except TypeError:
        _warn_value(items, owner)
        return None
    group = Element(FRAGMENT, None, entries)
    if diagnostics.is_dev():
        _check_list(_slots(group.children, owner), owner)
    return group


def _warn_string(item: Any, owner: str) -> None:
    diagnostics.warn_once(
        f"Ignoring bare string child {item!r}" + (f" under {owner}" if owner else "") + ". Wrap text in pn.Text(...).",
        key=f"strchild:{owner}",
    )


def _warn_value(item: Any, owner: str) -> None:
    diagnostics.warn_once(
        f"Ignoring non-Element child {item!r} ({type(item).__name__})"
        + (f" under {owner}" if owner else "")
        + ". Children must be Elements, lists of Elements, or None/False for conditionals.",
        key=f"badchild:{owner}:{type(item).__name__}",
    )


def _check_list(slots: Sequence[Optional[Element]], owner: str) -> None:
    """Warn once per owner about a dynamic list whose elements lack keys, and about duplicate keys."""
    elements = [el for el in slots if el is not None]
    if len(elements) >= 2 and any(el.key is None for el in elements):
        diagnostics.warn_once(
            f"{owner or 'A component'} rendered a list of {len(elements)} sibling elements without keys. "
            "Give each element in a dynamic list a stable key (Row(item).with_key(item.id), or key= on built-ins) "
            "so inserts and reorders keep the right state and native views.",
            key=f"unkeyed:{owner}",
        )
    _check_duplicates(slots, owner)


def _check_duplicates(slots: Sequence[Optional[Element]], owner: str) -> None:
    seen: Set[Any] = set()
    for el in slots:
        if el is None or el.key is None:
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


# ----------------------------------------------------------------------
# Nodes
# ----------------------------------------------------------------------


class VNode:
    """A mounted [`Element`][pythonnative.Element] plus its native identity.

    The reconciler walks parallel trees of ``VNode`` and incoming
    ``Element`` to compute the minimal set of native mutations. Nodes
    are plain slotted objects: the reconciler records a node in the
    render journal (``touch``) before it first changes it in a pass, so
    a rolled-back pass restores it.

    Attributes:
        element: The ``Element`` last rendered into this slot.
        kind: The node kind (``NATIVE``, ``COMPONENT``, ``PROVIDER``,
            ``BOUNDARY``, ``SUSPENSE_KIND``, or ``WRAPPER``), fixed at
            creation.
        slot: The node's slot in its parent's child list.
        tag: Integer identity of the underlying native view. Native
            elements own a fresh tag; transparent wrappers (components,
            providers, boundaries, fragments, groups) delegate the tag
            of their first native root. ``None`` when the subtree
            renders no native view.
        native_view: The platform-native view object, resolved from the
            backend after commit. ``None`` for wrappers that rendered
            nothing.
        children: Ordered list of child ``VNode`` instances. Empty slots
            aren't stored; each child records its ``slot``.
        parent: The owning ``VNode``, or ``None`` for the tree root.
        hook_state: The component's
            [`HookState`][pythonnative.hooks.HookState] when the node
            wraps a component, otherwise ``None``.
        events: For native nodes, the Python event handlers by event name
            (``None`` without any). The event registry reads them when
            native reports an event.
        mounted: ``False`` once the node has been destroyed, so stale
            entries in the reconciler's dirty set are skipped.
    """

    __slots__ = (
        "element",
        "kind",
        "slot",
        "tag",
        "native_view",
        "children",
        "parent",
        "hook_state",
        "mounted",
        "rendered",
        "clean_props",
        "events",
        "last_frame",
        "hidden_by_suspense",
        "error",
        "suspense_showing_fallback",
        "suspense_hidden",
        "suspense_hydration",
        "suspense_waits",
        "context_consumers",
        "_journal_stamp",
    )

    def __init__(
        self,
        element: Element,
        children: Optional[List["VNode"]] = None,
        tag: Optional[int] = None,
        kind: Optional[int] = None,
    ) -> None:
        # A node created during a render pass belongs to it: a rollback
        # discards the node, so the pass's journal never captures it.
        self._journal_stamp = _journal.stamp()
        self.element = element
        self.kind = kind_of(element.type) if kind is None else kind
        self.slot = 0
        self.tag = tag
        self.native_view: Any = None
        self.children: List[VNode] = children if children is not None else []
        self.parent: Optional[VNode] = None
        self.hook_state: Optional[HookState] = None
        self.mounted: bool = True
        # The child list a component body last produced.
        self.rendered: Optional[Sequence[Optional[Element]]] = None
        # Native-safe props (events and reconciler-owned keys stripped)
        # from the last commit; the baseline for prop diffing.
        self.clean_props: Dict[str, Any] = {}
        self.events: Optional[Dict[str, Any]] = None
        # The last frame the core reported for this node.
        self.last_frame: Optional[Tuple[float, float, float, float]] = None
        # True while an enclosing Suspense boundary hides this native
        # root (``display: "none"`` override) during an update-time
        # suspension.
        self.hidden_by_suspense: bool = False
        # For error-boundary nodes: the caught exception while the
        # fallback is showing, else ``None``.
        self.error: Optional[BaseException] = None
        # For Suspense nodes: whether the fallback is showing; the
        # committed content nodes kept mounted (and hidden) while the
        # fallback shows after an update-time suspension; the hook
        # states of suspended descendants preserved for the next retry
        # (keyed by ``(component identity, element key)``); and the ids
        # of waitables already wired to trigger a retry.
        self.suspense_showing_fallback: bool = False
        self.suspense_hidden: Optional[List[VNode]] = None
        self.suspense_hydration: Optional[Dict[Tuple[int, Any], List[HookState]]] = None
        self.suspense_waits: Optional[Set[int]] = None
        # For provider nodes: components that read this provider's
        # context, registered by ``use_context``.
        self.context_consumers: Any = None

    # ------------------------------------------------------------------
    # Journal support
    # ------------------------------------------------------------------

    def _capture(self) -> Tuple[Any, ...]:
        """The fields a render pass can change. Containers are replaced, never mutated, except the Suspense ones."""
        hydration = self.suspense_hydration
        waits = self.suspense_waits
        return (
            self.element,
            self.slot,
            self.tag,
            self.native_view,
            self.children,
            self.parent,
            self.hook_state,
            self.mounted,
            self.rendered,
            self.clean_props,
            self.events,
            self.hidden_by_suspense,
            self.error,
            self.suspense_showing_fallback,
            self.suspense_hidden,
            None if hydration is None else {key: list(states) for key, states in hydration.items()},
            None if waits is None else set(waits),
        )

    def _restore(self, values: Tuple[Any, ...]) -> None:
        (
            self.element,
            self.slot,
            self.tag,
            self.native_view,
            self.children,
            self.parent,
            self.hook_state,
            self.mounted,
            self.rendered,
            self.clean_props,
            self.events,
            self.hidden_by_suspense,
            self.error,
            self.suspense_showing_fallback,
            self.suspense_hidden,
            self.suspense_hydration,
            self.suspense_waits,
        ) = values

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @property
    def is_native(self) -> bool:
        """Whether this node owns a native view."""
        return self.kind == NATIVE

    @property
    def is_component(self) -> bool:
        """Whether this node renders a user component (a ``@component`` function)."""
        return self.kind == COMPONENT

    @property
    def is_provider(self) -> bool:
        """Whether this node is a context provider."""
        return self.kind == PROVIDER

    @property
    def is_error_boundary(self) -> bool:
        """Whether this node is an ``ErrorBoundary``."""
        return self.kind == BOUNDARY

    @property
    def is_suspense(self) -> bool:
        """Whether this node is a ``Suspense`` boundary."""
        return self.kind == SUSPENSE_KIND

    @property
    def is_strict_mode(self) -> bool:
        """Whether this node is a ``StrictMode`` wrapper."""
        return self.element.type is STRICT_MODE

    @property
    def key(self) -> Optional[str]:
        """The key of the element in this slot."""
        return self.element.key

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


def touch(node: VNode) -> None:
    """Record ``node`` in the active render journal before its first change in a pass.

    Nodes created during the pass, and nodes already recorded, cost one
    comparison. Outside a pass this does nothing.
    """
    journal = _journal.active
    if journal is not None and node._journal_stamp != journal.identity:
        journal.record(node)
