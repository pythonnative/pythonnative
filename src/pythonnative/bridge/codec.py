"""JSON encoding for the native bridge.

The bridge speaks JSON in both directions (see ``docs/concepts/bridge.md``).
Prop values coming out of the reconciler are almost, but not quite,
JSON: they may contain ``frozenset`` event-name sets, tuples, floats
that are infinite, and Python callables that native must never see.
[`to_jsonable`][pythonnative.bridge.codec.to_jsonable] normalizes a
value into something ``json.dumps`` accepts. Callbacks and declared
Python-only fields stay in the backend's sidecar; unsupported native
values raise an error.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import math
from collections.abc import Mapping
from typing import Any, Dict, List, Sequence, Tuple, Union

from ..mutations import UNSET, CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp

__all__ = [
    "INF",
    "NEG_INF",
    "build_transaction",
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
            JSON representation.
    """
    if isinstance(value, enum.Enum):
        return to_jsonable(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_jsonable(getattr(value, field.name)) for field in dataclasses.fields(value) if field.init
        }
    if isinstance(value, _SCALARS):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return None
        return INF if value > 0 else NEG_INF
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Native mappings require string keys")
        return {key: to_jsonable(item) for key, item in value.items()}
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


def split_props(
    props: Dict[str, Any], python_only: frozenset[str] = frozenset()
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split ``props`` into ``(wire_props, python_props)``.

    ``wire_props`` is JSON-ready; ``python_props`` holds callbacks and
    fields explicitly declared Python-only. Other unsupported values
    fail encoding. The backend keeps Python props in a per-tag sidecar.
    (The reconciler has already published ``Animated.event`` bindings
    under ``_pn_animated_events`` before props reach the codec.)
    """
    wire: Dict[str, Any] = {}
    python: Dict[str, Any] = {}
    for key, value in props.items():
        if value is UNSET:
            continue
        if key in python_only or (callable(value) and not isinstance(value, type)):
            python[key] = value
            continue
        wire[key] = to_jsonable(value)
    return wire, python


def build_transaction(
    ops: Sequence[Mutation], types: Mapping[int, str] | None = None
) -> Tuple[List[Any], List[Tuple[int, Dict[str, Any]]]]:
    """Build the wire operations for a mutation batch, JSON-ready but not yet serialized.

    Args:
        ops: Ordered mutations from the reconciler.
        types: Native component names for tags, used to identify Python-only props.

    Returns:
        ``(wire_ops, python_props)`` where ``wire_ops`` is the list the
        transaction envelope carries under ``"ops"`` (every value already
        normalized by [`to_jsonable`][pythonnative.bridge.codec.to_jsonable])
        and ``python_props`` lists ``(tag, props)`` pairs for values that
        stayed Python-side (for ``c`` and ``u`` ops). The backend removes
        sidecar entries using ``UNSET`` values in the original update
        operations.
    """
    from ..sdk.schema import COMPONENTS

    names: dict[int, str] = {}
    base_names = types or {}
    fields_cache: dict[str, frozenset[str]] = {}

    def python_fields(name: str) -> frozenset[str]:
        if name in fields_cache:
            return fields_cache[name]
        schema = COMPONENTS.get(name)
        fields_cache[name] = (
            frozenset(key for key, field in schema.props.items() if field.get("native", {}).get("python_only"))
            if schema
            else frozenset()
        )
        return fields_cache[name]

    encoded: List[Any] = []
    sidecar: List[Tuple[int, Dict[str, Any]]] = []
    for op in ops:
        if isinstance(op, CreateOp):
            names[op.tag] = op.type_name
            wire, python = split_props(op.props, python_fields(op.type_name))
            encoded.append(["c", op.tag, op.type_name, wire])
            if python:
                sidecar.append((op.tag, python))
        elif isinstance(op, UpdateOp):
            removed = [key for key, value in op.changed_props.items() if value is UNSET]
            wire, python = split_props(op.changed_props, python_fields(names.get(op.tag) or base_names.get(op.tag, "")))
            encoded.append(["u", op.tag, wire, removed])
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
    return encoded, sidecar


def encode_transaction(
    ops: Sequence[Mutation], types: Mapping[int, str] | None = None
) -> Tuple[str, List[Tuple[int, Dict[str, Any]]]]:
    """Encode a mutation batch as the bridge's transaction JSON.

    A convenience over [`build_transaction`][pythonnative.bridge.codec.build_transaction]
    for callers that want the serialized op list alone (tests and
    tooling); the backend serializes the whole envelope itself.

    Returns:
        ``(json_text, python_props)``; see ``build_transaction``.
    """
    encoded, sidecar = build_transaction(ops, types)
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
