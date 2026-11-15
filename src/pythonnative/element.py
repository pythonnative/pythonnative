"""Lightweight element descriptors for the virtual view tree.

An [`Element`][pythonnative.Element] is an immutable description of a UI
node, analogous to a React element. It captures a type, a read-only property snapshot,
and an immutable sequence of children without creating any native platform
objects. The reconciler consumes these trees to determine what native
views must be created, updated, or removed.

An element's ``type`` is one of three things:

- a ``str`` naming a **native view** (``"Text"``, ``"View"``, ...),
- a [`Component`][pythonnative.Component] produced by
  [`@component`][pythonnative.component.component], or
- a **structural type**: one of the singletons defined here
  ([`FRAGMENT`][pythonnative.element.FRAGMENT],
  [`ERROR_BOUNDARY`][pythonnative.element.ERROR_BOUNDARY],
  [`SUSPENSE`][pythonnative.element.SUSPENSE],
  [`STRICT_MODE`][pythonnative.element.STRICT_MODE]) or a
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

from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping, Optional

__all__ = [
    "ERROR_BOUNDARY",
    "FRAGMENT",
    "STRICT_MODE",
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


STRICT_MODE = StructuralType("StrictMode")
"""Type of [`StrictMode`][pythonnative.StrictMode] elements."""

_PLAIN_CHILDREN = (type(None), bool, list, tuple)


class Element:
    """Immutable description of a single UI node.

    Built-in elements use a string ``type`` (``"Text"``, ``"Button"``,
    ``"Column"``, etc.); components use the
    [`Component`][pythonnative.Component] object itself as ``type``;
    structural elements use a [`StructuralType`][pythonnative.element.StructuralType]
    or a [`Context`][pythonnative.Context]. The reconciler dispatches on
    this distinction when mounting the tree.

    An element is immutable: assigning an attribute raises
    ``AttributeError``. The ``props`` mapping is the one the caller
    passed, not a copy, so factories hand over a dict they just built and
    nothing else keeps a reference to it. Copy an element with
    [`with_key`][pythonnative.element.Element.with_key].

    Attributes:
        type: The element kind (see the module docstring).
        props: Properties passed to the native handler or the component
            function. Treat it as read-only.
        children: Immutable tuple of child nodes. Each entry occupies one
            slot of the child list: an element, ``None`` or a ``bool``
            for an empty slot (``cond and Text(...)``), or a list or tuple
            that forms a group whose items are matched among themselves.
            Components receive these as their ``*children``.
        key: Optional stable identity used by the reconciler when
            diffing child lists. Two elements with the same ``type`` and
            ``key`` are treated as the same logical node across renders.
    """

    __slots__ = ("type", "props", "children", "key")

    type: Any
    props: Mapping[str, Any]
    children: tuple[Any, ...]
    key: Optional[str]

    def __init__(
        self,
        type_: Any,
        props: Optional[Mapping[str, Any]] = None,
        children: Optional[Iterable[Any]] = None,
        key: Optional[str] = None,
    ) -> None:
        if children is None:
            children = ()
        else:
            if type(children) is not tuple:
                children = tuple(children)
            for child in children:
                if child.__class__ is not Element and child.__class__ not in _PLAIN_CHILDREN:
                    children = tuple(map(_materialize, children))
                    break
        _set_type(self, type_)
        _set_props(self, _EMPTY if props is None else props)
        _set_children(self, children)
        _set_key(self, key)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"Element is immutable; use with_key() to copy one (tried to set {name!r})")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"Element is immutable (tried to delete {name!r})")

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

    def __copy__(self) -> "Element":
        return self

    def __deepcopy__(self, memo: Any) -> "Element":
        return self

    def __reduce__(self) -> Any:
        return (Element, (self.type, dict(self.props), self.children, self.key))

    @classmethod
    def __native_schema__(cls) -> dict[str, Any]:
        """An element prop (``refresh_control``) crosses the bridge as the object its factory unwraps."""
        return {"type": "object"}

    def with_key(self, key: object) -> "Element":
        """Return a copy of this element carrying ``key``.

        This is the typed way to key a user component, whose call
        signature can't include ``key=`` (PEP 612 forbids keyword
        parameters next to a ``ParamSpec``):

        ```python
        pn.Column([Row(item).with_key(item.id) for item in items])
        ```

        Built-in factories also accept ``key=`` directly. Non-string
        keys are converted with ``str``; ``None`` clears the key. The
        copy shares this element's props and children.
        """
        copy = _new(Element)
        _set_type(copy, self.type)
        _set_props(copy, self.props)
        _set_children(copy, self.children)
        _set_key(copy, None if key is None else (key if key.__class__ is str else str(key)))
        return copy


_new = object.__new__
_slots: Any = Element.__dict__
_set_type = _slots["type"].__set__
_set_props = _slots["props"].__set__
_set_children = _slots["children"].__set__
_set_key = _slots["key"].__set__
_EMPTY: Mapping[str, Any] = MappingProxyType({})


def _materialize(child: Any) -> Any:
    """Freeze a one-shot iterator child (a generator expression) into a tuple.

    Children are read on every render of the element (a component passes
    its ``*children`` through again when its own state changes), so an
    iterator would be empty the second time.
    """
    if child is None or isinstance(child, (Element, bool, list, tuple)):
        return child
    if isinstance(child, Iterator):
        return tuple(map(_materialize, child))
    return child


type Node = Element | None | bool | list[Node] | tuple[Node, ...] | Iterator[Node]
"""Anything that can appear in an element tree.

An element, ``None`` or a ``bool`` for an empty slot (so ``cond and
pn.Text(...)`` and ``pn.Text(...) if cond else None`` both work, and the
siblings after them keep their identity), or a possibly nested list,
tuple, or iterator (a generator expression) of nodes, which forms a group
whose items are matched among themselves. The alias names those containers rather than ``Iterable`` so a
bare string, which is an iterable of strings, is a type error. Every built-in container declares
``*children: Node`` and component bodies return a ``Node``. Strings
aren't nodes: wrap text in [`Text`][pythonnative.Text]."""


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
