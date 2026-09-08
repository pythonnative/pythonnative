"""Conservative component compatibility for Fast Refresh."""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any, Callable


def hook_signature(function: Callable[..., Any], _seen: frozenset[int] = frozenset()) -> tuple[str, ...] | None:
    """Record hook order and binding names before the source file changes.

    Binding names distinguish inserting or moving hooks of the same kind.
    Uninspectable functions remount instead of risking slot corruption.
    """
    if id(function) in _seen:
        return None
    _seen = _seen | {id(function)}
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError, SyntaxError):
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
        if inspect.isfunction(target) and not target.__module__.startswith("pythonnative."):
            nested = hook_signature(target, _seen)
            if nested is None:
                return None
            signature += repr(nested)
        result.append((node.lineno, node.col_offset, signature))
    return tuple(value for _, _, value in sorted(result))
