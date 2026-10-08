"""Conservative component compatibility for Fast Refresh."""

from __future__ import annotations

import ast
import linecache
import types
from typing import Any, Callable, Optional, Union

_FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]

# One parsed tree per source file, keyed by the exact ``linecache`` lines it
# came from, so every component in a module shares a single parse.
_trees: dict[str, tuple[list[str], ast.Module]] = {}


def _function_node(function: Any) -> Optional[_FunctionNode]:
    """Find ``function``'s definition in its module's current source."""
    code = getattr(function, "__code__", None)
    if code is None:
        return None
    filename = code.co_filename
    linecache.checkcache(filename)
    lines = linecache.getlines(filename, getattr(function, "__globals__", None))
    if not lines:
        return None
    cached = _trees.get(filename)
    if cached is None or cached[0] is not lines:
        try:
            tree = ast.parse("".join(lines), filename)
        except (SyntaxError, ValueError):
            return None
        _trees[filename] = cached = (lines, tree)
    first = code.co_firstlineno
    for node in ast.walk(cached[1]):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == code.co_name:
            start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            if first in (start, node.lineno):
                return node
    return None


def hook_signature(function: Callable[..., Any], _seen: frozenset[int] = frozenset()) -> tuple[str, ...] | None:
    """Record hook order and binding names when a component is defined.

    Binding names distinguish inserting or moving hooks of the same kind.
    Uninspectable functions remount instead of risking slot corruption.
    Framework functions never change under Fast Refresh and have no
    signature.
    """
    if id(function) in _seen or getattr(function, "__module__", "").startswith("pythonnative."):
        return None
    _seen = _seen | {id(function)}
    tree = _function_node(function)
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
        if isinstance(target, types.FunctionType) and not target.__module__.startswith("pythonnative."):
            nested = hook_signature(target, _seen)
            if nested is None:
                return None
            signature += repr(nested)
        result.append((node.lineno, node.col_offset, signature))
    return tuple(value for _, _, value in sorted(result))
