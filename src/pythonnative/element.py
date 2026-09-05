"""Lightweight element descriptors for the virtual view tree.

An [`Element`][pythonnative.Element] is an immutable description of a UI
node, analogous to a React element. It captures a type, a props dict,
and an ordered list of children without creating any native platform
objects. The reconciler consumes these trees to determine what native
views must be created, updated, or removed.

An element's ``type`` is one of three things:

- a ``str`` naming a **native view** (``"Text"``, ``"View"``, ...),
- a [`Component`][pythonnative.Component] produced by
  [`@component`][pythonnative.component.component], or
- a **structural type**: one of the singletons defined here
  ([`FRAGMENT`][pythonnative.element.FRAGMENT],
  [`ERROR_BOUNDARY`][pythonnative.element.ERROR_BOUNDARY],
  [`SUSPENSE`][pythonnative.element.SUSPENSE]) or a
  [`Context`][pythonnative.Context] (whose elements are providers).

Structural types are real objects rather than magic strings so the
reconciler can dispatch on them with identity checks and no user
element can collide with them.

Elements are produced by built-in factories such as
[`Text`][pythonnative.Text], [`Button`][pythonnative.Button], and
[`Column`][pythonnative.Column], or by calling components.

Example:
    ```python
    from pythonnative import Element

    node = Element("Text", {"text": "Hello"}, [])
    ```
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Union

__all__ = [
    "ERROR_BOUNDARY",
    "FRAGMENT",
    "SUSPENSE",
    "Element",
    "Node",
    "StructuralType",
    "type_label",
]


class StructuralType:
    """Identity object naming a reconciler-owned element kind.

    Instances are singletons compared by identity; ``repr`` shows the
    kind for debugging (``<Fragment>``).
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


FRAGMENT = StructuralType("Fragment")
"""Type of [`Fragment`][pythonnative.Fragment] elements: a transparent group."""

ERROR_BOUNDARY = StructuralType("ErrorBoundary")
"""Type of [`ErrorBoundary`][pythonnative.ErrorBoundary] elements."""

SUSPENSE = StructuralType("Suspense")
"""Type of [`Suspense`][pythonnative.Suspense] elements."""


class Element:
    """Immutable description of a single UI node.

    Built-in elements use a string ``type`` (``"Text"``, ``"Button"``,
    ``"Column"``, etc.); components use the
    [`Component`][pythonnative.Component] object itself as ``type``;
    structural elements use a [`StructuralType`][pythonnative.element.StructuralType]
    or a [`Context`][pythonnative.Context]. The reconciler dispatches on
    this distinction when mounting the tree.

    Attributes:
        type: The element kind (see the module docstring).
        props: Dict of properties passed to the native handler or the
            component function.
        children: Ordered list of child nodes. ``None`` and ``False``
            entries are permitted and dropped during reconciliation, so
            conditional children (``cond and Text(...)``) need no special
            casing. Components receive these as their ``*children``.
        key: Optional stable identity used by the reconciler when
            diffing keyed lists. Two elements with the same ``type`` and
            ``key`` are treated as the same logical node across renders.
    """

    __slots__ = ("type", "props", "children", "key")

    def __init__(
        self,
        type_: Any,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[Iterable[Any]] = None,
        key: Optional[str] = None,
    ) -> None:
        self.type = type_
        self.props: Dict[str, Any] = props if props is not None else {}
        self.children: List[Any] = list(children) if children is not None else []
        self.key = key

    def __repr__(self) -> str:
        return f"Element({type_label(self.type)!r}, props={sorted(self.props)}, children={len(self.children)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Element):
            return NotImplemented
        return (
            self.type == other.type
            and self.props == other.props
            and self.children == other.children
            and self.key == other.key
        )

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    __hash__ = None  # type: ignore[assignment,unused-ignore]

    def with_key(self, key: Optional[str]) -> "Element":
        """Return a copy of this element carrying ``key``.

        Handy when a factory result needs a key after the fact, for
        example while building a list comprehension over elements
        produced by a helper that doesn't take ``key``.
        """
        return Element(self.type, self.props, self.children, key=key)


Node = Union[Element, None, bool, Iterable[Any]]
"""Anything a component may render: an element, ``None`` / ``False``
for "nothing", or a (possibly nested) iterable of nodes."""


def type_label(type_obj: Any) -> str:
    """Return a human-readable name for an element type (for messages)."""
    if isinstance(type_obj, str):
        return type_obj
    if isinstance(type_obj, StructuralType):
        return type_obj.name
    name = getattr(type_obj, "display_name", None) or getattr(type_obj, "__name__", None)
    if name:
        return str(name)
    return repr(type_obj)
