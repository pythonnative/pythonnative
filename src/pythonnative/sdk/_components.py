"""Custom native-component registration.

Implements the [`@native_component`][pythonnative.sdk.native_component]
decorator and supporting helpers that let third-party packages contribute
new element types to the reconciler.

The registration model is intentionally small. A custom component is a
three-part agreement:

1. A typed, immutable
   [`Props`][pythonnative.sdk.Props] dataclass declaring the
   component's public surface.
2. One or more
   [`ViewHandler`][pythonnative.sdk.ViewHandler] subclasses
   (one per platform) implementing the platform-side rendering.
3. A name (string) used by the reconciler to look up the handler.

The decorator stores the (name, props_type, handler_instance) tuple
in a process-wide registry. The
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
calls
[`install_into_registry`][pythonnative.sdk.install_into_registry] on
first use; that helper performs entry-point discovery (importing any
modules registered under
[`ENTRY_POINT_GROUP`][pythonnative.sdk.ENTRY_POINT_GROUP]) and copies
every handler matching the active platform into the registry.

Example:
    ```python
    from dataclasses import dataclass
    import pythonnative as pn
    from pythonnative.sdk import Props, ViewHandler, element_factory, native_component


    @dataclass(frozen=True)
    class BadgeProps(Props):
        text: str = ""
        color: str = "#FF3B30"
        style: pn.StyleProp = None


    @native_component("Badge", props=BadgeProps, platforms=("ios",))
    class IOSBadgeHandler(ViewHandler):
        def create(self, tag, props):
            ...

        def update(self, view, changed):
            ...


    Badge = element_factory("Badge")
    ```
"""

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from ..element import Element
from ..native_views.base import ViewHandler

ENTRY_POINT_GROUP = "pythonnative.handlers"
"""Entry-point group used by PyPI packages to register native handlers.

Packages declare entries like:

```toml
[project.entry-points."pythonnative.handlers"]
my_blur = "my_pkg.blur:register"
```

PythonNative imports the referenced module the first time the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry] is
materialized; the decorators inside that module populate the registry
during import.
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

# name -> (props_type or None, {platform_name: handler_instance})
_REGISTRY: Dict[str, Tuple[Optional[type], Dict[str, ViewHandler]]] = {}

# Caches `_install_into_registry` runs to avoid repeated entry-point
# discovery once the registry has been populated for a given platform.
_DISCOVERED: bool = False


H = TypeVar("H", bound=ViewHandler)


def native_component(
    name: str,
    *,
    props: Optional[type] = None,
    platforms: Optional[Tuple[str, ...]] = None,
) -> Callable[[Type[H]], Type[H]]:
    """Decorator that registers a [`ViewHandler`][pythonnative.sdk.ViewHandler] under ``name``.

    The handler class is instantiated immediately and stored in the
    process-wide registry. Decorate the same ``name`` once per platform
    when shipping platform-specific implementations; the decorator
    accumulates entries in a ``{platform: handler}`` mapping per name.

    Args:
        name: Element type name (e.g., ``"Badge"``). Must be a valid
            identifier-like string. Used by the reconciler at lookup time.
        props: Optional dataclass type describing the component's
            typed props. When supplied, the
            [`element_factory`][pythonnative.sdk.element_factory] helper
            uses this type to validate kwargs and produce frozen prop
            instances.
        platforms: Tuple of platform identifiers
            (``"ios"`` / ``"android"``) the handler implements. Defaults
            to ``("android", "ios")`` so a single cross-platform handler
            registers everywhere.

    Returns:
        A decorator that, when applied to a
        [`ViewHandler`][pythonnative.sdk.ViewHandler] subclass, registers
        it and returns the class unchanged.

    Raises:
        TypeError: If the decorated object is not a class subclassing
            ``ViewHandler``.

    Example:
        ```python
        from dataclasses import dataclass
        from pythonnative.sdk import Props, ViewHandler, native_component


        @dataclass(frozen=True)
        class BadgeProps(Props):
            text: str = ""
            color: str = "#FF3B30"


        @native_component("Badge", props=BadgeProps, platforms=("ios",))
        class IOSBadgeHandler(ViewHandler):
            def create(self, tag, props):
                ...
        ```
    """
    plats: Tuple[str, ...] = platforms if platforms is not None else ("android", "ios")

    def decorator(handler_cls: Type[H]) -> Type[H]:
        if not isinstance(handler_cls, type) or not issubclass(handler_cls, ViewHandler):
            raise TypeError(
                f"@native_component({name!r}) must decorate a ViewHandler subclass; " f"got {handler_cls!r}"
            )
        register_component(name=name, props=props, handlers={plat: handler_cls() for plat in plats})
        return handler_cls

    return decorator


def register_component(
    *,
    name: str,
    props: Optional[type] = None,
    handlers: Dict[str, ViewHandler],
) -> None:
    """Register a custom native component imperatively.

    Equivalent to applying [`@native_component`][pythonnative.sdk.native_component]
    one or more times, but useful when constructing handlers
    programmatically (e.g., parameterized handler instances). Subsequent
    calls for the same ``name`` merge their ``handlers`` into the
    existing entry, replacing any previously-registered handler for the
    same platform.

    Args:
        name: Element type name.
        props: Optional dataclass type describing the typed props.
        handlers: ``{platform_name: handler_instance}`` mapping. Common
            keys are ``"ios"`` and ``"android"``.

    Raises:
        TypeError: If any handler is not a
            [`ViewHandler`][pythonnative.sdk.ViewHandler] instance, or
            if ``props`` is not a dataclass type.
    """
    if props is not None and not (isinstance(props, type) and is_dataclass(props)):
        raise TypeError(f"register_component({name!r}): props must be a @dataclass type, got {props!r}")
    for plat, handler in handlers.items():
        if not isinstance(handler, ViewHandler):
            raise TypeError(f"register_component({name!r}): handler for {plat!r} must be a ViewHandler instance")

    existing = _REGISTRY.get(name)
    if existing is None:
        _REGISTRY[name] = (props, dict(handlers))
        return
    existing_props, plat_map = existing
    new_props = props if props is not None else existing_props
    plat_map.update(handlers)
    _REGISTRY[name] = (new_props, plat_map)


def unregister_component(name: str) -> None:
    """Remove a previously-registered component (primarily for tests).

    Args:
        name: The element type name to unregister.
    """
    _REGISTRY.pop(name, None)


def list_components() -> List[str]:
    """Return the names of every registered custom component.

    Useful for diagnostics and tests.

    Returns:
        Sorted list of names registered via
        [`@native_component`][pythonnative.sdk.native_component] or
        [`register_component`][pythonnative.sdk.register_component].
    """
    return sorted(_REGISTRY)


def get_props_type(name: str) -> Optional[type]:
    """Return the registered props dataclass for ``name`` (or ``None``)."""
    entry = _REGISTRY.get(name)
    return entry[0] if entry is not None else None


def install_into_registry(registry: Any, platform_name: str) -> None:
    """Copy registered handlers into a [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry].

    Called once by the registry on first use. Triggers entry-point
    discovery on the first call so PyPI-installed handlers register
    themselves before the registry snapshot is taken.

    Args:
        registry: A
            [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
            (or duck-compatible object) with a ``register(name, handler)``
            method.
        platform_name: The active platform identifier
            (``"ios"`` or ``"android"``).
    """
    _discover_entry_points()
    for name, (_props_type, plat_map) in _REGISTRY.items():
        handler = plat_map.get(platform_name)
        if handler is not None:
            registry.register(name, handler)


def _discover_entry_points() -> None:
    """Import every module registered under ``ENTRY_POINT_GROUP``.

    Idempotent and safe to call repeatedly; the actual discovery only
    runs once per process. Exceptions raised by individual entry points
    are swallowed (with the offending name printed to stderr) so a
    single broken plugin never prevents the rest of the process from
    rendering.
    """
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True

    try:
        from importlib.metadata import entry_points
    except ImportError:
        return

    try:
        eps = entry_points()
    except Exception:
        return

    # importlib.metadata's API changed across Python versions; both
    # ``select`` and direct ``.get`` are normalized here.
    selected: List[Any] = []
    if hasattr(eps, "select"):
        try:
            selected = list(eps.select(group=ENTRY_POINT_GROUP))
        except Exception:
            selected = []
    if not selected:
        try:
            getter = getattr(eps, "get", None)
            if getter is not None:
                selected = list(getter(ENTRY_POINT_GROUP, []))
        except Exception:
            selected = []

    for ep in selected:
        name = getattr(ep, "name", "?")
        try:
            ep.load()
        except Exception as exc:  # pragma: no cover - defensive
            import sys

            print(
                f"[pythonnative.sdk] Failed to load handler entry point {name!r}: {exc!r}",
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
      arguments matching the registered props dataclass.

    If no ``props`` dataclass was registered for ``name``, kwargs flow
    through unmodified — useful when iterating before locking down a
    prop schema.

    Args:
        name: An element type name previously registered via
            [`@native_component`][pythonnative.sdk.native_component] or
            [`register_component`][pythonnative.sdk.register_component].

    Returns:
        A callable producing fresh
        [`Element`][pythonnative.Element] instances of type ``name``.

    Raises:
        KeyError: If ``name`` is not registered.

    Example:
        ```python
        Badge = element_factory("Badge")
        Badge(text="3", color="#0A84FF")
        Badge(props=BadgeProps(text="3"))
        ```
    """
    if name not in _REGISTRY:
        raise KeyError(
            f"No component registered under name {name!r}. " "Use @native_component or register_component first."
        )

    def factory(*children: Element, key: Optional[str] = None, props: Any = None, **kwargs: Any) -> Element:
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
        # Style props pass through resolve_style at the boundary so list
        # forms / None get flattened identically to built-in factories.
        from ..style import resolve_style as _resolve

        style_value = props_dict.pop("style", None)
        style_dict = _resolve(style_value)
        merged: Dict[str, Any] = {**style_dict, **props_dict}
        return Element(name, merged, list(children), key=key)

    factory.__name__ = name
    factory.__doc__ = f"Construct an Element of type {name!r}."
    return factory


__all__ = [
    "ENTRY_POINT_GROUP",
    "Props",
    "element_factory",
    "get_props_type",
    "install_into_registry",
    "list_components",
    "native_component",
    "register_component",
    "unregister_component",
]
