"""The ``@component`` decorator and the [`Component`][pythonnative.Component] type.

A component is a plain Python function that takes props and returns a
[`Node`][pythonnative.element.Node]: an [`Element`][pythonnative.Element],
a list of elements, or ``None``. Decorating it with
[`@component`][pythonnative.component.component] turns it into a
[`Component`][pythonnative.Component]: a callable that *describes* a
render (it returns an ``Element`` whose ``type`` is the component)
instead of performing one. The reconciler invokes the function body
later, with hook state installed.

The decorator preserves the function's signature for type checkers via
:class:`typing.ParamSpec`, so ``Greeting(nme="x")`` is a static error
and editors autocomplete props from the function definition.

Children
--------

Children are positional. A component that accepts children declares a
``*children`` parameter, exactly like the built-in containers:

```python
@pn.component
def Card(*children: pn.Element, title: str = "") -> pn.Element:
    return pn.Column(pn.Text(title, style=pn.style(bold=True)), *children)

Card(pn.Text("body"), title="Hello")
```

Positional arguments to a component *without* ``*children`` bind to its
positional parameters, so ``Greeting("World")`` works for
``def Greeting(name: str)``.

Keys
----

Every component accepts ``key=`` at the call site for keyed
reconciliation. ``key`` is consumed by the framework and is not passed
to the function unless the function declares a ``key`` parameter
itself. Declaring it (``key: str | None = None``) is the way to keep
strict type checkers happy when a component is rendered in a list;
otherwise use [`Element.with_key`][pythonnative.element.Element.with_key].
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, ParamSpec, Tuple, Union

from .element import Element, Node

__all__ = ["Component", "RenderFn", "component", "memo", "is_component"]

P = ParamSpec("P")

RenderFn = Callable[P, Union[Node, Awaitable[Node]]]
"""A component body: returns a [`Node`][pythonnative.element.Node], or awaits one when ``async def``."""


class Component(Generic[P]):
    """A render-function wrapped by [`@component`][pythonnative.component.component].

    Calling a ``Component`` does not run the function; it returns an
    [`Element`][pythonnative.Element] describing the call so the
    reconciler can mount it, preserve its hook state across renders,
    and re-run it when its state or props change.

    Attributes:
        fn: The original render function.
        display_name: Name shown in diagnostics and dev tooling
            (defaults to ``fn.__name__``).
        memoized: Whether [`memo`][pythonnative.memo] was applied, in
            which case the reconciler skips re-rendering this component
            when its props are shallowly equal to the previous render.
        accepts_children: Whether ``fn`` declares ``*children``.
    """

    __slots__ = (
        "fn",
        "display_name",
        "memoized",
        "props_equal",
        "accepts_children",
        "_positional",
        "_declares_key",
        "_is_async",
        "__wrapped__",
        "__dict__",
    )

    def __init__(self, fn: RenderFn[P], *, display_name: Optional[str] = None) -> None:
        if isinstance(fn, Component):
            raise TypeError(f"{fn!r} is already a component; remove the duplicate @component")
        sig = inspect.signature(fn)
        positional: List[str] = []
        accepts_children = False
        declares_key = False
        for name, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                positional.append(name)
            elif param.kind is inspect.Parameter.VAR_POSITIONAL:
                accepts_children = True
            if name == "key":
                declares_key = True
        self.fn = fn
        self.display_name = display_name or getattr(fn, "__name__", "Component")
        self.memoized = False
        self.props_equal: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None
        self.accepts_children = accepts_children
        self._positional: Tuple[str, ...] = tuple(positional)
        self._declares_key = declares_key
        self._is_async = inspect.iscoroutinefunction(fn)
        self.__wrapped__ = fn
        functools.update_wrapper(self, fn, updated=())

    # ------------------------------------------------------------------
    # Element construction
    # ------------------------------------------------------------------

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Element:
        """Describe a render of this component with the given props."""
        props: Dict[str, Any] = dict(kwargs)
        key = props.pop("key", None) if not self._declares_key else props.get("key")
        children: List[Any] = []
        if args:
            if self.accepts_children:
                children = list(args)
            else:
                names = self._positional
                if len(args) > len(names):
                    raise TypeError(
                        f"{self.display_name}() takes {len(names)} positional argument(s) but "
                        f"{len(args)} were given. Declare *children to accept child elements."
                    )
                for name, value in zip(names, args):
                    if name in props:
                        raise TypeError(f"{self.display_name}() got multiple values for argument {name!r}")
                    props[name] = value
        return Element(self, props, children, key=key if isinstance(key, str) or key is None else str(key))

    # ------------------------------------------------------------------
    # Rendering (used by the reconciler)
    # ------------------------------------------------------------------

    def render(self, element: Element) -> Any:
        """Invoke the render function for ``element``.

        Children stored on the element are passed positionally; props
        are passed by keyword. Returns whatever the function returned
        (an element, a list, ``None``, or a coroutine for ``async def``
        bodies).
        """
        if self.accepts_children:
            return self.fn(*element.children, **element.props)
        return self.fn(**element.props)  # type: ignore[call-arg]

    @property
    def is_async(self) -> bool:
        """Whether the render function is an ``async def``."""
        return self._is_async

    def __repr__(self) -> str:
        flags = " memo" if self.memoized else ""
        return f"<Component {self.display_name}{flags}>"

    def __get__(self, instance: Any, owner: Any = None) -> "Component[P]":
        # Components stored on classes (rare) should not bind ``self``.
        return self


def component(fn: RenderFn[P]) -> Component[P]:
    """Turn a render function into a [`Component`][pythonnative.Component].

    The decorated function may use hooks (``use_state``, ``use_effect``,
    etc.) and returns an [`Element`][pythonnative.Element] tree, a list
    of elements, or ``None``. Each call site creates an independent
    component instance with its own hook state.

    Args:
        fn: The render function. May be ``async def``; the body is then
            driven by the reconciler and suspends on pending awaits (see
            [`Suspense`][pythonnative.Suspense]).

    Returns:
        A ``Component`` whose call signature mirrors ``fn`` (plus the
        framework ``key=`` keyword).

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Greeting(name: str = "World"):
            return pn.Text(f"Hello, {name}!")
        ```
    """
    return Component(fn)


def memo(
    target: Optional[Component[P]] = None,
    *,
    equal: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None,
) -> Any:
    """Skip a component's render when its props haven't changed.

    Apply on top of ``@component``. When the reconciler re-renders the
    parent tree, a memoized child is skipped (its previously-rendered
    subtree is reused) iff its props and children are equal to the
    previous render and none of its own state setters fired. Props are
    compared shallowly by default: callables by identity, everything
    else by ``==``.

    Pair with [`use_callback`][pythonnative.use_callback] when passing
    callbacks as props, otherwise a fresh closure defeats the memo.

    Args:
        target: A [`Component`][pythonnative.Component].
        equal: Optional custom comparator ``(old_props, new_props) ->
            bool`` replacing the shallow comparison.

    Returns:
        The same component, marked for memoization (or a decorator when
        called with keyword arguments only).

    Example:
        ```python
        @pn.memo
        @pn.component
        def ExpensiveRow(label: str):
            ...

        @pn.memo(equal=lambda a, b: a["id"] == b["id"])
        @pn.component
        def Row(id: int, extra: dict):
            ...
        ```
    """

    def apply(comp: Component[P]) -> Component[P]:
        if not isinstance(comp, Component):
            raise TypeError("@memo must wrap a @component; write @memo above @component")
        comp.memoized = True
        comp.props_equal = equal
        return comp

    if target is None:
        return apply
    return apply(target)


def is_component(obj: Any) -> bool:
    """Return whether ``obj`` is a [`Component`][pythonnative.Component]."""
    return isinstance(obj, Component)
