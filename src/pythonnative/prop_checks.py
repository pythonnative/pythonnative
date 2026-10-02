"""Development-mode checks of component props against their annotations.

Static type checking is the primary guard for props: a component's call
signature is its prop list, so ``Card(title=3)`` is a mypy or pyright
error. These checks catch what slips past a type checker (untyped
callers, ``Any`` values, dynamic dispatch) at the call site, in
development builds only.

A mismatch produces one [`diagnostics`][pythonnative.diagnostics]
warning per component and parameter; nothing raises. The checker
understands the common annotation shapes (``str``, ``int``, ``float``
accepting ``int``, ``bool``, ``None``, ``Optional``, unions,
``Literal``, ``Sequence``, ``Mapping``, ``Callable``, dataclasses, and
plain classes) and skips anything it can't evaluate, including
unresolvable forward references and type variables.
"""

from __future__ import annotations

import collections.abc
import types
import typing
import weakref
from typing import Any, Callable, Dict, Optional

from . import diagnostics

__all__ = ["check_props", "matches"]

_UNKNOWN = object()
# Keyed weakly by the render function: an ``id`` key can be reused by a
# later function once the first is collected, which would check props
# against another component's annotations.
_hints_cache: "weakref.WeakKeyDictionary[Callable[..., Any], Optional[Dict[str, Any]]]" = weakref.WeakKeyDictionary()


def _hints(component: Any) -> Optional[Dict[str, Any]]:
    fn = component.fn
    if fn not in _hints_cache:
        try:
            hints = typing.get_type_hints(fn)
        except Exception:
            hints = None
        if hints is not None:
            hints.pop("return", None)
        _hints_cache[fn] = hints
    return _hints_cache[fn]


def matches(value: Any, hint: Any) -> Optional[bool]:
    """Return whether ``value`` satisfies ``hint``, or ``None`` when the hint isn't checkable."""
    if hint is Any or hint is object:
        return True
    if hint is None or hint is type(None):
        return value is None
    if isinstance(hint, typing.TypeVar) or isinstance(hint, typing.ParamSpec):
        return None
    alias_value = getattr(hint, "__value__", _UNKNOWN)
    if alias_value is not _UNKNOWN and isinstance(hint, typing.TypeAliasType):
        return matches(value, alias_value)
    origin = typing.get_origin(hint)
    if origin is typing.Union or origin is types.UnionType:
        results = [matches(value, arg) for arg in typing.get_args(hint)]
        if any(result is True for result in results):
            return True
        if any(result is None for result in results):
            return None
        return False
    if origin is typing.Literal:
        return value in typing.get_args(hint)
    if origin is typing.Annotated:
        return matches(value, typing.get_args(hint)[0])
    if origin is collections.abc.Callable:
        return callable(value)
    if origin is not None:
        return isinstance(value, origin) if isinstance(origin, type) else None
    if hint is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if hint is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if hint is complex:
        return isinstance(value, (int, float, complex)) and not isinstance(value, bool)
    if isinstance(hint, type):
        if typing.is_typeddict(hint):
            return isinstance(value, dict)
        if getattr(hint, "_is_protocol", False):
            if getattr(hint, "_is_runtime_protocol", False):
                return isinstance(value, hint)
            return None
        if hint is collections.abc.Callable:
            return callable(value)
        try:
            return isinstance(value, hint)
        except TypeError:
            return None
    return None


def check_props(component: Any, props: Dict[str, Any]) -> None:
    """Warn once per parameter when a prop doesn't match its annotation (dev mode only)."""
    hints = _hints(component)
    if not hints:
        return
    parameters = component._signature.parameters
    for name, value in props.items():
        hint = hints.get(name)
        parameter = parameters.get(name)
        if hint is None or parameter is None or parameter.kind is parameter.VAR_KEYWORD:
            continue
        if matches(value, hint) is False:
            label = getattr(hint, "__name__", None) or repr(hint)
            diagnostics.warn_once(
                f"{component.display_name}() received {name}={value!r} ({type(value).__name__}), "
                f"which doesn't match its annotation {label}.",
                key=f"prop-type:{component.__module__}.{component.display_name}.{name}",
            )
