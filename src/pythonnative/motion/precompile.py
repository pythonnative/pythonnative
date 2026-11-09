"""Compile every worklet in a staged tree before release builds drop the sources (RFC 0009).

Release builds ship sourceless bytecode, so a worklet can't be compiled
from its source on the device. Staging runs
[`precompile_tree`][pythonnative.motion.precompile.precompile_tree] first:
it finds every ``@worklet`` function and every inline lambda passed to an
API that only accepts worklets, compiles them, and writes
``pn_worklets.json`` at the root of the tree, which is on ``sys.path`` in
the app. At run time a code object is looked up by its file, first line,
and name, and a lambda by where its body starts, which both ``ast`` and
``co_positions()`` report.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .compiler import WorkletError, compile_node

__all__ = ["TABLE_NAME", "WORKLET_APIS", "find_worklets", "precompile_source", "precompile_tree"]

TABLE_NAME = "pn_worklets.json"

WORKLET_APIS = frozenset(
    {
        "worklet",
        "use_animated_style",
        "use_derived_value",
        "use_animated_reaction",
        "use_frame_callback",
    }
)
"""Calls whose inline lambda arguments are worklets."""

_WORKLET_KEYWORDS = frozenset({"on_finish", "entering", "exiting", "layout"})
"""Keyword arguments whose inline lambdas are worklets, whatever the call."""

_HINTS = ("worklet", *WORKLET_APIS, *_WORKLET_KEYWORDS)


def _callee_name(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_worklet_decorator(node: ast.expr) -> bool:
    return _callee_name(node) == "worklet"


def find_worklets(tree: ast.Module) -> Iterator[Any]:
    """Every ``FunctionDef`` marked ``@worklet`` and every ``Lambda`` passed to a worklet API."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            _is_worklet_decorator(decorator) for decorator in node.decorator_list
        ):
            yield node
        elif isinstance(node, ast.Call):
            if _callee_name(node.func) in WORKLET_APIS:
                for argument in node.args:
                    if isinstance(argument, ast.Lambda):
                        yield argument
            for keyword in node.keywords:
                if isinstance(keyword.value, ast.Lambda) and (
                    keyword.arg in _WORKLET_KEYWORDS or _callee_name(node.func) in WORKLET_APIS
                ):
                    yield keyword.value


def _qualnames(tree: ast.Module) -> Dict[int, str]:
    """``id(node) -> qualified name`` for every function and lambda, as CPython names them."""
    names: Dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                names[id(child)] = name
                visit(child, f"{name}.<locals>.")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, ast.Lambda):
                name = f"{prefix}<lambda>"
                names[id(child)] = name
                visit(child, f"{name}.<locals>.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return names


def precompile_source(source: str, filename: str) -> Tuple[Dict[str, Any], List[WorkletError]]:
    """Compile the worklets in one module's source into table entries."""
    entries: Dict[str, Any] = {}
    errors: List[WorkletError] = []
    try:
        tree = ast.parse(source, filename)
    except SyntaxError:
        return entries, errors  # byte-compiling reports it
    qualnames = _qualnames(tree)
    seen = set()
    for node in find_worklets(tree):
        if id(node) in seen:
            continue
        seen.add(id(node))
        name = qualnames.get(id(node), "<lambda>" if isinstance(node, ast.Lambda) else node.name)
        if isinstance(node, ast.Lambda):
            line = node.lineno
        else:
            line = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        try:
            program = compile_node(node, filename, name, line)
        except WorkletError as error:
            errors.append(error)
            continue
        if isinstance(node, ast.Lambda):
            entries.setdefault(f"{line}:<lambda>", []).append(
                {"body": [node.body.lineno, node.body.col_offset], "program": program.to_json()}
            )
        else:
            entries[f"{line}:{node.name}"] = program.to_json()
    return entries, errors


def precompile_tree(root: Path, label: str = "") -> List[WorkletError]:
    """Write ``root/pn_worklets.json`` for every module under ``root``; return the worklets that failed.

    Args:
        root: The staged directory (the app, or a packages directory).
        label: The bundle-relative directory the bytecode records for
            ``root`` (``"app"``), so file names match ``co_filename``.
    """
    table: Dict[str, Dict[str, Any]] = {}
    errors: List[WorkletError] = []
    for path in sorted(root.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(hint in source for hint in _HINTS):
            continue
        relative = path.relative_to(root).as_posix()
        filename = f"{label}/{relative}" if label else relative
        entries, failed = precompile_source(source, filename)
        errors.extend(failed)
        if entries:
            table[filename] = entries
    target = root / TABLE_NAME
    if table:
        target.write_text(json.dumps(table, separators=(",", ":")), encoding="utf-8")
    elif target.exists():
        target.unlink()
    return errors
