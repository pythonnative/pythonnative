"""Read and edit the mounted component tree for DevTools.

Every [`ScreenHost`][pythonnative.hosts.ScreenHost] owns a reconciler
whose mounted [`VNode`][pythonnative.reconciler.VNode]s form the tree
DevTools shows. Node ids are ``id(vnode)``: nodes are reused across
renders, so an id stays valid while the node is mounted, and every lookup
walks the live trees, so a stale id simply isn't found.

Values are summarized with [`summarize`][pythonnative.devtools.inspector.summarize]
before they leave the process: DevTools sees short, typed descriptions,
never the objects themselves.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import os
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

__all__ = [
    "find_node",
    "find_node_by_tag",
    "inspect_node",
    "node_label_path",
    "set_state",
    "summarize",
    "tree",
]

_MAX_REPR = 240
_MAX_ITEMS = 25
_MAX_DEPTH = 3
_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep

Roots = Callable[[], Sequence[Any]]


# ======================================================================
# Live roots
# ======================================================================


def live_reconcilers() -> List[Tuple[str, Any]]:
    """``(label, reconciler)`` for every live screen host."""
    from ..hosts import live_hosts

    found: List[Tuple[str, Any]] = []
    for host in live_hosts():
        reconciler = getattr(host, "reconciler", None)
        if reconciler is not None and getattr(reconciler, "root", None) is not None:
            label = getattr(host, "component_path", "") or "screen"
            found.append((str(label), reconciler))
    return found


def _walk(node: Any) -> Iterator[Any]:
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def find_node(node_id: int, reconcilers: Optional[Iterable[Tuple[str, Any]]] = None) -> Optional[Any]:
    """The mounted node whose id is ``node_id``, or ``None``."""
    for _label, reconciler in reconcilers if reconcilers is not None else live_reconcilers():
        for node in _walk(reconciler.root):
            if id(node) == node_id and node.mounted:
                return node
    return None


def find_node_by_tag(tag: int, reconcilers: Optional[Iterable[Tuple[str, Any]]] = None) -> Optional[Any]:
    """The native node that owns view ``tag``, or ``None``."""
    for _label, reconciler in reconcilers if reconcilers is not None else live_reconcilers():
        node = getattr(reconciler, "_tag_nodes", {}).get(int(tag))
        if node is not None and node.mounted and node.is_native:
            return node
    return None


# ======================================================================
# Summaries
# ======================================================================


def _type_name(value: Any) -> str:
    return type(value).__qualname__


def _truncate(text: str, limit: int = _MAX_REPR) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summarize(value: Any, depth: int = 0) -> Dict[str, Any]:
    """A short, JSON-safe description of ``value`` for DevTools.

    Returns a dict with ``type`` (the class name), ``repr`` (a truncated
    one-line description), and, for containers and dataclasses within
    the depth limit, ``items`` (a list of ``[key, summary]`` pairs).
    """
    from ..element import Element

    kind = _type_name(value)
    if value is None or isinstance(value, (bool, int, float)):
        return {"type": kind, "repr": repr(value), "literal": True}
    if isinstance(value, str):
        return {"type": "str", "repr": _truncate(repr(value)), "literal": len(value) <= _MAX_REPR}
    if isinstance(value, bytes):
        return {"type": "bytes", "repr": f"<{len(value)} bytes>"}
    if isinstance(value, Element):
        from ..element import type_label

        return {"type": "Element", "repr": f"<{type_label(value.type)}>"}
    if isinstance(value, enum.Enum):
        return {"type": kind, "repr": f"{kind}.{value.name}"}
    if callable(value) and not isinstance(value, type) and not dataclasses.is_dataclass(value):
        name = getattr(value, "__qualname__", None) or getattr(value, "__name__", None) or kind
        return {"type": "function", "repr": f"ƒ {name}()"}
    summary: Dict[str, Any] = {"type": kind}
    items: Optional[List[Tuple[str, Any]]] = None
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        items = [(f.name, getattr(value, f.name, None)) for f in dataclasses.fields(value)]
        summary["repr"] = f"{kind}(…)"
    elif isinstance(value, dict):
        items = [(repr(k) if not isinstance(k, str) else k, v) for k, v in list(value.items())[: _MAX_ITEMS + 1]]
        summary["repr"] = f"dict({len(value)})"
    elif isinstance(value, (list, tuple, set, frozenset)):
        seq = list(value)[: _MAX_ITEMS + 1]
        items = [(str(index), item) for index, item in enumerate(seq)]
        summary["repr"] = f"{kind}({len(value)})"
    else:
        try:
            text = repr(value)
        except Exception as exc:  # A broken __repr__ shouldn't break DevTools.
            text = f"<{kind}: repr failed: {exc!r}>"
        summary["repr"] = _truncate(text)
    if items is not None:
        if depth < _MAX_DEPTH:
            summary["items"] = [[key, summarize(item, depth + 1)] for key, item in items[:_MAX_ITEMS]]
            if len(items) > _MAX_ITEMS:
                summary["more"] = True
        try:
            literal = repr(value)
            ast.literal_eval(literal)
            if len(literal) <= 4 * _MAX_REPR:
                summary["literal"] = True
                summary["source"] = literal
        except Exception:
            pass
    return summary


# ======================================================================
# Tree
# ======================================================================


def _kind(node: Any) -> str:
    if node.is_native:
        return "native"
    if node.is_component:
        return "component"
    if node.is_provider:
        return "provider"
    if node.is_error_boundary:
        return "boundary"
    if node.is_suspense:
        return "suspense"
    return "fragment"


def _source(node: Any) -> Optional[Dict[str, Any]]:
    fn = getattr(node.element.type, "fn", None)
    code = getattr(fn, "__code__", None)
    if code is None:
        return None
    from ..errors import project_path

    return {"file": project_path(code.co_filename), "line": int(code.co_firstlineno)}


def _is_framework(node: Any) -> bool:
    if node.is_provider:
        return str(getattr(node.element.type, "module", "")).startswith("pythonnative")
    fn = getattr(node.element.type, "fn", None)
    code = getattr(fn, "__code__", None)
    if code is None:
        return not node.is_native
    return os.path.abspath(code.co_filename).startswith(_PACKAGE_ROOT)


def _text_preview(node: Any) -> Optional[str]:
    props = node.element.props
    if node.element.type in ("Button", "TextInput"):
        label = props.get("title") or props.get("value") or props.get("placeholder")
        return _truncate(label, 60) if isinstance(label, str) and label else None
    if node.element.type != "Text":
        return None
    value = props.get("text")
    if isinstance(value, str):
        return _truncate(value, 60)
    parts = [part for part in node.element.children if isinstance(part, str)]
    return _truncate("".join(parts), 60) if parts else None


def _serialize(node: Any) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "id": id(node),
        "name": node.label,
        "kind": _kind(node),
        "children": [_serialize(child) for child in node.children],
    }
    if node.element.key is not None:
        entry["key"] = _truncate(repr(node.element.key), 60)
    if node.tag is not None:
        entry["tag"] = node.tag
    if node.is_component:
        source = _source(node)
        if source is not None:
            entry["source"] = source
    if (node.is_component or node.is_provider) and _is_framework(node):
        entry["framework"] = True
    text = _text_preview(node)
    if text:
        entry["text"] = text
    if node.error is not None:
        entry["error"] = _truncate(f"{type(node.error).__name__}: {node.error}", 120)
    return entry


def tree(reconcilers: Optional[Iterable[Tuple[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Every live screen's tree, as nested ``{"id", "name", "kind", ...}`` dicts."""
    screens: List[Dict[str, Any]] = []
    for label, reconciler in reconcilers if reconcilers is not None else live_reconcilers():
        screens.append({"screen": label, "root": _serialize(reconciler.root)})
    return screens


def node_label_path(node: Any) -> List[str]:
    """Component names from the root down to ``node``, skipping framework components."""
    names: List[str] = []
    current = node
    while current is not None:
        if current.is_component and not _is_framework(current):
            names.append(current.label)
        elif current is node:
            names.append(current.label)
        current = current.parent
    return list(reversed(names))


def owner_component(node: Any) -> Any:
    """The nearest component at or above ``node`` (``node`` itself for components)."""
    current = node
    while current is not None and not current.is_component:
        current = current.parent
    return current


def native_root_tag(node: Any) -> Optional[int]:
    """The tag of the first native view ``node`` renders, if any."""
    if node.tag is not None:
        return int(node.tag)
    for child in _walk(node):
        if child.tag is not None:
            return int(child.tag)
    return None


# ======================================================================
# Inspection
# ======================================================================


def _hooks(state: Any) -> List[Dict[str, Any]]:
    signature: Sequence[str] = list(state._hook_signature or [])
    counters: Dict[str, int] = {}
    hooks: List[Dict[str, Any]] = []
    effect_kinds = {"use_effect": "effects", "use_layout_effect": "layout_effects"}
    for position, kind in enumerate(signature):
        bucket = "state" if kind in ("use_state", "use_reducer") else kind
        index = counters.get(bucket, 0)
        counters[bucket] = index + 1
        entry: Dict[str, Any] = {"hook": kind, "position": position}
        try:
            if bucket == "state":
                entry["index"] = index
                entry["value"] = summarize(state.states[index])
                entry["editable"] = kind == "use_state" and index in state._setters
            elif kind == "use_ref":
                entry["value"] = summarize(state.refs[index].current)
            elif kind == "use_memo":
                deps, value = state.memos[index]
                entry["value"] = summarize(value)
                entry["deps"] = summarize(deps)
            elif kind in effect_kinds:
                deps, _cleanup = getattr(state, effect_kinds[kind])[index]
                entry["deps"] = summarize(deps)
            elif kind == "use_resource":
                deps, resource = state.resources[index]
                entry["value"] = summarize(resource)
                entry["deps"] = summarize(deps)
        except (IndexError, ValueError, TypeError):
            pass
        hooks.append(entry)
    if not signature:
        # Release-mode states don't record hook kinds; show raw slots.
        for index, value in enumerate(state.states):
            hooks.append(
                {"hook": "state", "index": index, "value": summarize(value), "editable": index in state._setters}
            )
    return hooks


def _frame(node: Any) -> Optional[Dict[str, float]]:
    target = node
    if target.tag is None:
        for child in _walk(node):
            if child.tag is not None:
                target = child
                break
    frame = getattr(target, "last_frame", None)
    if not frame:
        return None
    x, y, width, height = frame
    return {"x": float(x), "y": float(y), "width": float(width), "height": float(height)}


def inspect_node(node: Any) -> Dict[str, Any]:
    """Props, hooks, context, frame, and source of one node."""
    props = {key: summarize(value) for key, value in node.element.props.items() if key != "children"}
    result: Dict[str, Any] = {
        "id": id(node),
        "name": node.label,
        "kind": _kind(node),
        "props": props,
        "path": node_label_path(node),
    }
    if node.element.key is not None:
        result["key"] = summarize(node.element.key)
    if node.tag is not None:
        result["tag"] = node.tag
    source = _source(node) if node.is_component else None
    if source is not None:
        result["source"] = source
    frame = _frame(node)
    if frame is not None:
        result["frame"] = frame
    state = node.hook_state
    if state is not None:
        result["hooks"] = _hooks(state)
        if state.context_deps:
            result["context"] = [summarize(value) for value in state.context_deps.values()]
    if node.is_provider:
        result["value"] = summarize(node.element.props.get("value"))
    if node.error is not None:
        result["error"] = f"{type(node.error).__name__}: {node.error}"
    return result


def set_state(node: Any, index: int, source: str) -> None:
    """Replace ``use_state`` slot ``index`` of a component with a Python literal.

    Raises:
        ValueError: When ``source`` isn't a literal or the slot has no setter.
    """
    state = node.hook_state
    if state is None:
        raise ValueError(f"{node.label} has no hooks")
    setter = state._setters.get(int(index))
    if setter is None:
        raise ValueError(f"{node.label} has no use_state slot {index}")
    try:
        value = ast.literal_eval(source)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"not a Python literal: {source!r}") from exc
    # A callable would be treated as an updater; literals never are.
    setter(value)
