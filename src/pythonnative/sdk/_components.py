"""Custom native-component definition.

Implements [`define_component`][pythonnative.sdk.define_component] and
the supporting helpers that let third-party packages contribute new
element types to the reconciler.

A custom component is rendered by a Swift ``PNComponentManager`` and a
Kotlin ``ComponentManager`` registered under the same type name by the
package's native plugin (see ``docs/guides/custom-native-components.md``);
the browser preview draws unknown types as labeled placeholders. The
Python side declares the element name and its typed props, which is
what the contract generator, the commit validator, and the element
factory all read:

1. A typed, immutable [`Props`][pythonnative.sdk.Props] dataclass
   declaring the component's public surface.
2. ``define_component(name, props)``, which registers the props schema
   and returns a typed element factory
   ([`element_factory`][pythonnative.sdk.element_factory] builds the same
   factory for an already-defined name).

Definitions are process-wide. PyPI packages that declare an entry point
under [`ENTRY_POINT_GROUP`][pythonnative.sdk.ENTRY_POINT_GROUP] are
imported once, before the first native commit, so their definitions are
in place without the app importing them explicitly.

Example:
    ```python
    from dataclasses import dataclass
    import pythonnative as pn
    from pythonnative.sdk import Props, define_component


    @dataclass(frozen=True)
    class BadgeProps(Props):
        text: str = ""
        color: str = "#FF3B30"
        style: pn.StyleProp = None


    Badge = define_component("Badge", BadgeProps)
    Badge(text="3", color="#0A84FF")
    ```
"""

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Callable, Dict, List, Optional

from ..element import Element

ENTRY_POINT_GROUP = "pythonnative.handlers"
"""Entry-point group used by PyPI packages to define native components.

Packages declare entries like:

```toml
[project.entry-points."pythonnative.handlers"]
my_blur = "my_pkg.blur:register"
```

PythonNative imports the referenced module the first time the view
backend is created; the ``define_component`` calls inside that module
register the package's components during import.
"""


@dataclass(frozen=True)
class Props:
    """Optional base class for typed prop dataclasses.

    Subclassing is not strictly required (any
    ``@dataclass(frozen=True)`` works), but inheriting from
    ``Props`` gives third-party components a clear, searchable marker
    in their public API and a stable place to add framework-wide
    behavior in the future.

    Example:
        ```python
        from dataclasses import dataclass
        from pythonnative.sdk import Props

        @dataclass(frozen=True)
        class BadgeProps(Props):
            text: str = ""
            color: str = "#FF3B30"
        ```
    """


# ---------------------------------------------------------------------- #
# Internal registry
# ---------------------------------------------------------------------- #

# name -> props dataclass type
_REGISTRY: Dict[str, type] = {}

# Caches entry-point discovery so it runs once per process.
_DISCOVERED: bool = False


def define_component(
    name: str, props: type, *, platforms: tuple[str, ...] = ("ios", "android")
) -> Callable[..., Element]:
    """Declare a custom native component and return its typed element factory.

    Registers ``props`` as the component's schema (so the contract
    generator emits it, the commit validator checks it, and the factory
    validates keyword arguments against it) and returns the
    [`element_factory`][pythonnative.sdk.element_factory] for ``name``.
    Defining the same ``name`` again replaces the earlier schema.

    Args:
        name: Element type name (``"Badge"``). Native component
            managers register under the same name.
        props: A ``@dataclass`` type describing the component's props.
            Every field is a keyword argument of the returned factory;
            ``style`` is added when the dataclass doesn't declare it.
        platforms: Platforms with an actual renderer. Browser
            placeholders don't count as native support.

    Returns:
        A callable producing [`Element`][pythonnative.Element] instances
        of type ``name``.

    Raises:
        TypeError: If ``props`` is not a dataclass type.
    """
    if not (isinstance(props, type) and is_dataclass(props)):
        raise TypeError(f"define_component({name!r}): props must be a @dataclass type, got {props!r}")
    from dataclasses import replace
    from typing import get_type_hints

    from ..style import Style, StyleProp
    from .schema import COMPONENTS, RUNTIME_PROPS, ComponentSchema, register_schema, type_schema

    schema = ComponentSchema.from_dataclass(name, props, platforms=platforms)
    common = COMPONENTS.get("View")
    style_keys = get_type_hints(Style)
    styles = {key: value for key, value in (common.props.items() if common else ()) if key in style_keys}
    wire = styles | schema.props | RUNTIME_PROPS
    wire["style"] = {**type_schema(StyleProp), "native": {"python_only": True}}
    register_schema(replace(schema, props=wire))
    _REGISTRY[name] = props
    return element_factory(name)


def unregister_component(name: str) -> None:
    """Remove a previously defined component (primarily for tests).

    Args:
        name: The element type name to forget.
    """
    _REGISTRY.pop(name, None)
    from .schema import COMPONENTS

    COMPONENTS.pop(name, None)


def list_components() -> List[str]:
    """Return the names of every defined custom component, sorted."""
    return sorted(_REGISTRY)


def get_props_type(name: str) -> Optional[type]:
    """Return the props dataclass defined for ``name`` (or ``None``)."""
    return _REGISTRY.get(name)


def discover_components() -> None:
    """Import every module registered under ``ENTRY_POINT_GROUP``.

    Idempotent and safe to call repeatedly; the actual discovery only
    runs once per process. Exceptions raised by individual entry points
    are swallowed (with the offending name printed to stderr) so a
    single broken plugin never prevents the rest of the process from
    rendering. The view backend calls this before its first commit.
    """
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True

    from importlib.metadata import entry_points

    selected = entry_points(group=ENTRY_POINT_GROUP)
    for ep in selected:
        name = getattr(ep, "name", "?")
        try:
            ep.load()
        except Exception as exc:  # pragma: no cover - defensive
            import sys

            print(
                f"[pythonnative.sdk] Failed to load component entry point {name!r}: {exc!r}",
                file=sys.stderr,
                flush=True,
            )


def _reset_discovery_state_for_tests() -> None:
    """Reset the entry-point discovery flag (for tests only)."""
    global _DISCOVERED
    _DISCOVERED = False


# ---------------------------------------------------------------------- #
# Element factories
# ---------------------------------------------------------------------- #


def _props_to_dict(value: Any) -> Dict[str, Any]:
    """Convert a typed props dataclass to a flat dict of non-None fields."""
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if v is not None}
    if is_dataclass(value):
        out: Dict[str, Any] = {}
        for f in fields(value):
            field_value = getattr(value, f.name)
            if field_value is not None:
                out[f.name] = field_value
        return out
    raise TypeError(f"Expected a dataclass instance or dict, got {type(value).__name__!r}")


def element_factory(name: str) -> Callable[..., Element]:
    """Return a callable that builds [`Element`][pythonnative.Element] instances of type ``name``.

    The returned factory accepts:

    - Children as positional arguments (any number).
    - ``key=`` (optional, keyword-only) for keyed reconciliation.
    - Either ``props=`` (a dataclass instance) or per-field keyword
      arguments matching the defined props dataclass.

    Args:
        name: An element type name previously declared with
            [`define_component`][pythonnative.sdk.define_component].

    Returns:
        A callable producing fresh
        [`Element`][pythonnative.Element] instances of type ``name``.

    Raises:
        KeyError: If ``name`` is not defined.

    Example:
        ```python
        Badge = element_factory("Badge")
        Badge(text="3", color="#0A84FF")
        Badge(props=BadgeProps(text="3"))
        ```
    """
    if name not in _REGISTRY:
        raise KeyError(f"No component defined under name {name!r}. Call define_component(name, props) first.")

    def factory(*children: Element, key: Optional[str] = None, props: Any = None, **kwargs: Any) -> Element:
        from ..mutations import UNSET

        explicit_style = kwargs.pop("style", UNSET)
        props_type = get_props_type(name)
        if props is not None:
            if kwargs:
                raise TypeError("Pass either props=... or keyword props, not both")
            props_dict = _props_to_dict(props)
        elif props_type is not None:
            try:
                instance = props_type(**kwargs)
            except TypeError as exc:
                raise TypeError(f"Invalid props for {name!r}: {exc}") from exc
            props_dict = _props_to_dict(instance)
        else:
            props_dict = dict(kwargs)
        if explicit_style is not UNSET:
            props_dict["style"] = explicit_style
        if props_type is not None:
            from .schema import COMPONENTS

            COMPONENTS[name].validate(props_dict)
        # Style props pass through resolve_style at the boundary so list
        # forms / None get flattened identically to built-in factories.
        from ..style import resolve_style as _resolve

        style_value = props_dict.pop("style", None)
        style_dict = _resolve(style_value)
        merged: Dict[str, Any] = {**style_dict, **props_dict}
        return Element(name, merged, list(children), key=key)

    import inspect

    props_type = get_props_type(name)
    if props_type is not None:
        signature = inspect.signature(props_type)
        if "style" not in signature.parameters:
            from ..style import StyleProp

            signature = signature.replace(
                parameters=[
                    *signature.parameters.values(),
                    inspect.Parameter("style", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=StyleProp),
                ]
            )
        factory.__signature__ = signature
    factory.__name__ = name
    factory.__doc__ = f"Construct an Element of type {name!r}."
    return factory


__all__ = [
    "ENTRY_POINT_GROUP",
    "Props",
    "define_component",
    "discover_components",
    "element_factory",
    "get_props_type",
    "list_components",
    "unregister_component",
]
