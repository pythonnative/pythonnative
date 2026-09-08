"""Portable animation expressions evaluated by the native UI thread."""

from __future__ import annotations

from typing import Any


def serialize(root: Any) -> dict[str, Any]:
    """Serialize one connected animation graph in dependency order."""
    from .animated import AnimatedInterpolation, AnimatedNode, AnimatedValue, _AnimatedDiffClamp, _AnimatedOperation

    connected: dict[int, Any] = {}

    def discover(node: Any) -> None:
        if not isinstance(node, AnimatedNode) or id(node) in connected:
            return
        connected[id(node)] = node
        for child in list(node._children):
            discover(child)
        for parent in getattr(node, "_parents", [getattr(node, "_parent", None)]):
            discover(parent)

    discover(root)
    encoded: dict[int, dict[str, Any]] = {}

    def encode(node: Any) -> Any:
        if not isinstance(node, AnimatedNode):
            return {"constant": float(node)}
        identity = id(node)
        if identity not in encoded:
            definition: dict[str, Any] = {"id": identity}
            if isinstance(node, AnimatedValue):
                definition.update(kind="value", value=node.value)
            elif isinstance(node, AnimatedInterpolation):
                definition.update(
                    kind="interpolate",
                    inputs=[encode(node._parent)],
                    ranges=node._inputs,
                    outputs=node._outputs,
                    color=node._kind == "color",
                    left=node._left,
                    right=node._right,
                )
            elif isinstance(node, _AnimatedOperation):
                definition.update(kind=node._op, inputs=[encode(parent) for parent in node._parents])
            elif isinstance(node, _AnimatedDiffClamp):
                definition.update(
                    kind="diff_clamp",
                    inputs=[encode(node._parent)],
                    minimum=node._min,
                    maximum=node._max,
                    previous=node._last_input,
                    value=node.value,
                )
            else:
                raise TypeError(f"Unsupported animated node {type(node).__name__}")
            encoded[identity] = definition
        return {"node": identity}

    for node in connected.values():
        encode(node)
    bindings = [[tag, prop, id(node)] for node in connected.values() for tag, prop in node.attachments()]
    return {"id": min(connected), "nodes": list(encoded.values()), "bindings": bindings}


def install(node: Any, *, detached_tag: int | None = None) -> dict[str, Any] | None:
    """Synchronize native graph ownership when a binding is attached or removed."""
    from .animated import _backend

    backend = _backend()
    handler = getattr(backend, "install_animation_graph", None)
    if handler is None:
        return None
    graph = serialize(node)
    tag = graph["bindings"][0][0] if graph["bindings"] else detached_tag
    if tag is not None:
        handler(tag, graph)
    return graph
