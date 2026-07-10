"""Lightweight element descriptors for the virtual view tree.

An [`Element`][pythonnative.Element] is an immutable description of a UI
node, analogous to a React element. It captures a type (name string or
component function), a props dict, and an ordered list of children
without creating any native platform objects. The reconciler consumes
these trees to determine what native views must be created, updated, or
removed.

Elements are produced by built-in factories such as
[`Text`][pythonnative.Text], [`Button`][pythonnative.Button], and
[`Column`][pythonnative.Column], or by calling functions decorated with
[`component`][pythonnative.component].

Example:
    ```python
    from pythonnative import Element

    node = Element("Text", {"text": "Hello"}, [])
    ```
"""

from typing import Any, Dict, List, Optional, Union


class Element:
    """Immutable description of a single UI node.

    Built-in elements use a string `type` (`"Text"`, `"Button"`,
    `"Column"`, etc.); function components use the function itself as
    `type`. The reconciler dispatches on this distinction when mounting
    the tree.

    Attributes:
        type: A string for built-in elements or a callable for function
            components decorated with [`component`][pythonnative.component].
        props: Dict of properties passed to the native handler or
            component function.
        children: Ordered list of child `Element` instances. `None` and
            `False` entries are permitted and dropped during
            reconciliation, so conditional children (`cond and Text(...)`)
            need no special casing.
        key: Optional stable identity used by the reconciler when
            diffing keyed lists. Two elements with the same `type` and
            `key` are treated as the same logical node across renders.
    """

    __slots__ = ("type", "props", "children", "key")

    def __init__(
        self,
        type_name: Union[str, Any],
        props: Dict[str, Any],
        children: List[Any],
        key: Optional[str] = None,
    ) -> None:
        self.type = type_name
        self.props = props
        self.children = children
        self.key = key

    def __repr__(self) -> str:
        t = self.type if isinstance(self.type, str) else getattr(self.type, "__name__", repr(self.type))
        return f"Element({t!r}, props={set(self.props)}, children={len(self.children)})"

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
