"""Conservative component compatibility for Fast Refresh.

A component's signature lists its hook calls in order, with the names they
bind, so inserting, removing, or moving a hook makes two versions
incompatible (Fast Refresh then remounts instead of reusing hook state).

Signatures come from source, but nothing is parsed when a component is
defined. [`remember`][pythonnative.refresh.remember] keeps the source lines
of the component's module (read once per module load) and of the modules
holding hooks it calls; [`hook_signature`][pythonnative.refresh.hook_signature]
parses them when Fast Refresh first compares two versions. Reading the source
as it was at load matters: by the time Fast Refresh runs, the file on disk
holds the new version.
"""

from __future__ import annotations

import ast
import linecache
import sys
import types
from typing import Any, Callable, Optional, TypeGuard, Union

__all__ = ["SourceLoad", "hook_signature", "remember", "remember_module"]

_FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]

_KEPT_LOADS = 3
"""Loads kept per file: the current one, the one Fast Refresh compares it with, and one spare."""

_loads: dict[str, list[SourceLoad]] = {}


class SourceLoad:
    """One module's source as it was when the module (re)loaded.

    Attributes:
        namespace: The module's globals for that load.
        lines: Its source lines, read when the first component was defined.
    """

    __slots__ = ("namespace", "lines", "_functions")

    def __init__(self, namespace: dict[str, Any], lines: list[str]) -> None:
        self.namespace = namespace
        self.lines = lines
        self._functions: Optional[dict[tuple[str, int], _FunctionNode]] = None

    def function(self, code: types.CodeType) -> Optional[_FunctionNode]:
        """The definition of ``code`` in this source (parsed once, on first use)."""
        if self._functions is None:
            self._functions = {}
            try:
                tree = ast.parse("".join(self.lines))
            except (SyntaxError, ValueError):
                return None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
                    self._functions.setdefault((node.name, start), node)
                    self._functions.setdefault((node.name, node.lineno), node)
        return self._functions.get((code.co_name, code.co_firstlineno))


def _load_for(function: types.FunctionType, *, read: bool) -> Optional[SourceLoad]:
    """The recorded load of ``function``'s module, reading its source now when ``read`` is set."""
    return _load(function.__code__.co_filename, function.__globals__, read=read)


def _load(filename: str, namespace: dict[str, Any], *, read: bool) -> Optional[SourceLoad]:
    loads = _loads.get(filename)
    if loads:
        for load in reversed(loads):
            if load.namespace is namespace:
                return load
    if not read:
        return None
    linecache.checkcache(filename)
    load = SourceLoad(namespace, linecache.getlines(filename, namespace))
    loads = _loads.setdefault(filename, [])
    loads.append(load)
    del loads[:-_KEPT_LOADS]
    return load


def _is_framework(value: Any) -> bool:
    module = value.__name__ if isinstance(value, types.ModuleType) else getattr(value, "__module__", None)
    return str(module or "").split(".")[0] == "pythonnative"


def _is_app_function(value: Any) -> TypeGuard[types.FunctionType]:
    return isinstance(value, types.FunctionType) and not _is_framework(value)


def _is_live(function: types.FunctionType) -> bool:
    """Whether ``function``'s module is still the one ``sys.modules`` holds (so its file is that load's)."""
    module = sys.modules.get(function.__module__)
    return module is not None and getattr(module, "__dict__", None) is function.__globals__


def remember_module(module: types.ModuleType) -> None:
    """Keep ``module``'s source now, if no component did (hot reload calls this for unchanged files)."""
    filename = getattr(module, "__file__", None)
    if isinstance(filename, str) and filename.endswith(".py"):
        _load(filename, module.__dict__, read=True)


def _remember_hooks(code: types.CodeType, namespace: dict[str, Any], seen: set[types.CodeType]) -> None:
    """Keep the source of every application hook ``code`` may call, without parsing anything.

    Mirrors how ``hook_signature`` resolves calls: ``use_x(...)`` through the
    globals, and ``owner.use_x(...)`` through a global module or class.
    """
    if code in seen:
        return
    seen.add(code)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            _remember_hooks(const, namespace, seen)
    hooks = [name for name in code.co_names if name.startswith("use_")]
    if not hooks:
        return
    for name in code.co_names:
        value = namespace.get(name)
        if isinstance(value, (types.ModuleType, type)):
            if _is_framework(value):
                continue
            targets = [getattr(value, hook, None) for hook in hooks]
        elif name.startswith("use_"):
            targets = [value]
        else:
            continue
        for target in targets:
            if _is_app_function(target) and target.__code__ not in seen:
                _load_for(target, read=True)
                _remember_hooks(target.__code__, target.__globals__, seen)


def remember(function: Callable[..., Any]) -> Optional[SourceLoad]:
    """Keep the source Fast Refresh will need for ``function``; called when a component is defined.

    Reads ``function``'s module source once per load of the module, and the
    source of modules holding application hooks it calls. Nothing is parsed.

    Returns:
        The load to pass to [`hook_signature`][pythonnative.refresh.hook_signature],
        or ``None`` for a function that has no inspectable source.
    """
    if not isinstance(function, types.FunctionType):
        return None
    load = _load_for(function, read=True)
    _remember_hooks(function.__code__, function.__globals__, set())
    return load


def hook_signature(
    function: Callable[..., Any], load: Optional[SourceLoad] = None, _seen: frozenset[int] = frozenset()
) -> tuple[str, ...] | None:
    """Return the hook order and binding names of ``function``.

    Binding names distinguish inserting or moving hooks of the same kind.
    Uninspectable functions, and hooks whose source wasn't kept when their
    module loaded, have no signature, so they remount instead of risking
    slot corruption. Framework functions never change under Fast Refresh
    and have no signature.

    Args:
        function: A component's render function, or a hook it calls.
        load: The source ``remember`` kept for ``function``. Defaults to
            the one recorded for its module's current namespace.
    """
    if id(function) in _seen or getattr(function, "__module__", "").startswith("pythonnative."):
        return None
    if not isinstance(function, types.FunctionType):
        return None
    _seen = _seen | {id(function)}
    if load is None:
        # A module no component kept the source of is safe to read only while
        # it's still the loaded one: its file then matches what's running.
        load = _load_for(function, read=_is_live(function))
    tree = load.function(function.__code__) if load is not None else None
    if tree is None:
        return None
    result = []
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if not name.startswith("use_"):
            continue
        owner = parents.get(id(node))
        binding = (
            ast.dump(owner.targets[0])
            if isinstance(owner, ast.Assign)
            else ast.dump(owner.target) if isinstance(owner, ast.AnnAssign) else ""
        )
        signature = name + ":" + binding
        target = None
        if isinstance(node.func, ast.Name):
            target = function.__globals__.get(node.func.id)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            owner = function.__globals__.get(node.func.value.id)
            target = getattr(owner, node.func.attr, None)
        if _is_app_function(target):
            nested = hook_signature(target, None, _seen)
            if nested is None:
                return None
            signature += repr(nested)
        result.append((node.lineno, node.col_offset, signature))
    return tuple(value for _, _, value in sorted(result))
