"""JSON encoding for the native bridge.

The bridge speaks JSON in both directions (see ``docs/concepts/bridge.md``).
Prop values coming out of the reconciler are almost, but not quite,
JSON: they may contain ``frozenset`` event-name sets, tuples, floats
that are infinite, and Python callables that native must never see.
[`to_jsonable`][pythonnative.bridge.codec.to_jsonable] normalizes a
value into something ``json.dumps`` accepts and reports the keys it had
to drop so the backend can keep them Python-side.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Sequence, Tuple, Union

from ..mutations import CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp

__all__ = [
    "INF",
    "NEG_INF",
    "dumps",
    "encode_transaction",
    "loads",
    "split_props",
    "to_jsonable",
]

INF = "inf"
"""Wire spelling of ``math.inf`` (JSON has no infinity literal)."""

NEG_INF = "-inf"
"""Wire spelling of ``-math.inf``."""

_SCALARS = (str, int, bool, type(None))


def to_jsonable(value: Any) -> Any:
    """Return a JSON-serializable copy of ``value``.

    - ``set`` / ``frozenset`` / ``tuple`` become lists (sets are sorted
      when their members are strings so the output is deterministic).
    - Infinite floats become the strings ``"inf"`` / ``"-inf"``; NaN
      becomes ``None`` (native clamps missing geometry to zero).
    - Dataclass-like objects with ``to_json()`` are converted through
      it.

    Raises:
        TypeError: When ``value`` (or something nested in it) has no
            JSON representation; callers decide whether to drop it.
    """
    if isinstance(value, _SCALARS):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return None
        return INF if value > 0 else NEG_INF
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = list(value)
        try:
            items.sort()
        except TypeError:
            pass
        return [to_jsonable(v) for v in items]
    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        return to_jsonable(to_json())
    raise TypeError(f"value of type {type(value).__name__} is not bridge-serializable")


def split_props(props: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split ``props`` into ``(wire_props, python_props)``.

    ``wire_props`` is JSON-ready; ``python_props`` holds every prop
    that can't cross the bridge (callables such as ``render_row``,
    arbitrary objects). The backend keeps the latter in a per-tag
    sidecar so native-backed handlers that need them (virtualized
    list rows) can still reach them.
    """
    wire: Dict[str, Any] = {}
    python: Dict[str, Any] = {}
    for key, value in props.items():
        if callable(value) and not isinstance(value, type):
            python[key] = value
            continue
        try:
            wire[key] = to_jsonable(value)
        except TypeError:
            python[key] = value
    return wire, python


def encode_transaction(
    ops: Sequence[Mutation], prop_filter: Any = None
) -> Tuple[str, List[Tuple[int, Dict[str, Any]]]]:
    """Encode a mutation batch as the bridge's transaction JSON.

    Args:
        ops: Ordered mutations from the reconciler.
        prop_filter: Unused hook kept for symmetry with the desktop
            registry; reserved for per-type prop rewriting.

    Returns:
        ``(json_text, python_props)`` where ``python_props`` lists
        ``(tag, props)`` pairs for values that stayed Python-side (for
        ``c`` and ``u`` ops). An update that *removes* a Python-side
        prop reports it as ``None`` so the sidecar can drop it.
    """
    del prop_filter
    encoded: List[Any] = []
    sidecar: List[Tuple[int, Dict[str, Any]]] = []
    for op in ops:
        if isinstance(op, CreateOp):
            wire, python = split_props(op.props)
            encoded.append(["c", op.tag, op.type_name, wire])
            if python:
                sidecar.append((op.tag, python))
        elif isinstance(op, UpdateOp):
            wire, python = split_props(op.changed_props)
            encoded.append(["u", op.tag, wire])
            if python:
                sidecar.append((op.tag, python))
        elif isinstance(op, InsertOp):
            encoded.append(["i", op.parent_tag, op.child_tag, op.index])
        elif isinstance(op, DestroyOp):
            encoded.append(["d", op.tag])
        elif isinstance(op, SetFrameOp):
            encoded.append(["f", op.tag, _num(op.x), _num(op.y), _num(op.width), _num(op.height)])
        else:  # pragma: no cover - the reconciler only emits the five op kinds
            raise TypeError(f"Unknown mutation op: {op!r}")
    return dumps(encoded), sidecar


def _num(value: float) -> float:
    """Clamp a frame coordinate to a finite float (native treats NaN/inf as 0)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return f if math.isfinite(f) else 0.0


def dumps(value: Any) -> str:
    """Compact ``json.dumps`` used for every bridge payload."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def loads(text: Union[str, bytes, bytearray, None]) -> Any:
    """Parse a bridge payload (``str`` or UTF-8 bytes); empty / ``None`` input yields ``None``."""
    if text is None:
        return None
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8")
    text = text.strip()
    if not text:
        return None
    return json.loads(text)
