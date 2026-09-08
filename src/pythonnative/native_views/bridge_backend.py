"""Revisioned native view backend.

Each commit is validated, sent as a protocol-2 envelope, and acknowledged before
Python updates its native tag index. Rejected commits poison the surface until
it is remounted. Native events carry application, revision, sequence, and text
edit identities. NativeViewRef holds a live native tag rather than a UI object.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..bridge import codec, get_transport
from ..bridge.commits import PROTOCOL_VERSION, CommitError, CommitState
from ..mutations import CreateOp, DestroyOp, Mutation, UpdateOp

__all__ = ["BridgeBackend", "NativeViewRef"]

_MEASURE_UNBOUNDED = 1e6


class NativeViewRef:
    """Opaque handle to a native view living on the other side of the bridge.

    Attributes:
        tag: The reconciler-assigned tag; pass it to
            ``Reconciler.dispatch_command`` or ``get_registry().command``.
        type_name: The element type (``"Text"``, ``"ScrollView"``, ...).
    """

    __slots__ = ("tag", "type_name")

    def __init__(self, tag: int, type_name: str) -> None:
        self.tag = tag
        self.type_name = type_name

    def __repr__(self) -> str:
        return f"<NativeViewRef {self.type_name} tag={self.tag}>"

    def __int__(self) -> int:
        return self.tag


class BridgeBackend:
    """Registry protocol implementation that forwards to the native runtime."""

    def __init__(self, transport: Any = None) -> None:
        self._transport = transport
        self._commit = CommitState(str(uuid.uuid4()), 1)
        self._births: dict[int, int] = {}
        self._event_sequences: dict[tuple[int, str], int] = {}
        self._edit_revisions: dict[int, int] = {}
        self._failed = False
        self.on_layout: Any = None
        self._types: Dict[int, str] = {}
        self._refs: Dict[int, NativeViewRef] = {}
        self._python_props: Dict[int, Dict[str, Any]] = {}
        self._handlers: Dict[str, Any] = {}

    @property
    def transport(self) -> Any:
        """The transport in use (resolved lazily on first access)."""
        if self._transport is None:
            self._transport = get_transport()
        return self._transport

    @property
    def native_layout(self) -> bool:
        """Whether layout runs beside the renderer's native widgets."""
        return self.transport.name in {"ios", "android", "web"}

    def compute_layout(self, roots: list[int], width: float, height: float) -> None:
        """Compute native Yoga layout in one request, returning changed frames."""
        raw = self.transport.call(
            "Layout", "compute", codec.dumps({"call_id": 0, "args": {"roots": roots, "width": width, "height": height}})
        )
        result = codec.loads(raw)
        if not isinstance(result, dict) or not result.get("ok"):
            raise CommitError(f"Native layout failed: {result!r}")
        if self.on_layout is not None:
            self.on_layout(result.get("value", []))

    # ------------------------------------------------------------------
    # Registration (kept for protocol parity with NativeViewRegistry)
    # ------------------------------------------------------------------

    def register(self, type_name: str, handler: Any) -> None:
        """Record a Python handler for diagnostics only.

        On device, rendering is native; a Python ``ViewHandler`` can't
        create platform views. The registration is kept so
        ``handler_for`` can answer introspection questions and so the
        SDK's install step doesn't fail, but it is never invoked.
        """
        self._handlers[type_name] = handler

    def handler_for(self, type_name: str) -> Any:
        """Return the diagnostic Python handler registered for ``type_name``."""
        return self._handlers.get(type_name)

    # ------------------------------------------------------------------
    # Tag table
    # ------------------------------------------------------------------

    def resolve_view(self, tag: int) -> Optional[NativeViewRef]:
        """Return the handle for ``tag`` (``None`` if the view is gone)."""
        return self._refs.get(tag)

    def type_of(self, tag: int) -> Optional[str]:
        """Return the element type registered for ``tag``."""
        return self._types.get(tag)

    def live_view_count(self) -> int:
        """Number of views currently alive on the native side."""
        return len(self._types)

    def python_props(self, tag: int) -> Dict[str, Any]:
        """Props held Python-side for ``tag`` (callables never sent to native)."""
        return self._python_props.get(tag, {})

    # ------------------------------------------------------------------
    # Commit channel
    # ------------------------------------------------------------------

    def apply_mutations(self, ops: Sequence[Mutation]) -> None:
        """Serialize ``ops`` and apply them natively in one crossing."""
        if not ops:
            return
        if self._failed:
            raise CommitError("Native surface failed; remount the application with a new backend")
        payload, sidecar = codec.encode_transaction(ops)
        wire_ops = codec.loads(payload)
        for op in wire_ops:
            if op[0] == "u" and self._types.get(op[1]) == "TextInput" and "value" in op[2]:
                op[2]["_pn_edit_revision"] = self._edit_revisions.get(op[1], 0)
        envelope = {
            "version": PROTOCOL_VERSION,
            "application": self._commit.application,
            "surface": self._commit.surface,
            "revision": self._commit.revision + 1,
            "ops": wire_ops,
        }
        from ..profiling import count

        count("bridge.commits")
        count("bridge.operations", len(ops))
        count("bridge.bytes", len(payload.encode("utf-8")))
        candidate = self._commit.prepare(envelope)
        try:
            ack = codec.loads(self.transport.apply(codec.dumps(envelope)))
            if ack != candidate.acknowledgement():
                raise CommitError(f"Native commit {candidate.revision} rejected: {ack!r}")
        except Exception:
            self._failed = True
            raise
        self._commit = candidate
        destroyed: List[int] = []
        for op in ops:
            if isinstance(op, CreateOp):
                self._types[op.tag] = op.type_name
                self._births[op.tag] = candidate.revision
                self._refs[op.tag] = NativeViewRef(op.tag, op.type_name)
            elif isinstance(op, DestroyOp):
                destroyed.append(op.tag)
        for tag, props in sidecar:
            self._python_props.setdefault(tag, {}).update(props)
        for op in ops:
            if isinstance(op, UpdateOp):
                # A prop that changed from a callable to None arrives
                # as None in the wire dict; drop the stale sidecar copy.
                bucket = self._python_props.get(op.tag)
                if bucket:
                    for key, value in op.changed_props.items():
                        if value is None:
                            bucket.pop(key, None)
                    if not bucket:
                        self._python_props.pop(op.tag, None)
        for tag in destroyed:
            self._forget(tag)

    def accept_event(self, tag: int, name: str, envelope: Any) -> bool:
        """Reject events from destroyed views, earlier applications, and replayed input."""
        if self._failed or not isinstance(envelope, dict):
            return False
        if envelope.get("application") != self._commit.application or envelope.get("surface") != self._commit.surface:
            return False
        revision, sequence = envelope.get("revision"), envelope.get("sequence")
        if type(revision) is not int or type(sequence) is not int or tag not in self._births:
            return False
        key = (tag, name)
        if not self._births[tag] <= revision <= self._commit.revision or sequence <= self._event_sequences.get(key, 0):
            return False
        self._event_sequences[key] = sequence
        if name == "on_change" and self._types.get(tag) == "TextInput":
            edit = envelope.get("edit_revision")
            if type(edit) is int:
                self._edit_revisions[tag] = max(edit, self._edit_revisions.get(tag, 0))
        return isinstance(envelope.get("args"), list)

    def _forget(self, tag: int) -> None:
        self._types.pop(tag, None)
        self._births.pop(tag, None)
        self._edit_revisions.pop(tag, None)
        for key in tuple(self._event_sequences):
            if key[0] == tag:
                del self._event_sequences[key]
        self._refs.pop(tag, None)
        self._python_props.pop(tag, None)

    # ------------------------------------------------------------------
    # Imperative escape hatches
    # ------------------------------------------------------------------

    def measure_intrinsic(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Ask native for the natural size of ``tag`` under the constraints."""
        if tag not in self._types:
            return (0.0, 0.0)
        w, h = self.transport.measure(tag, _bound(max_width), _bound(max_height))
        return (max(0.0, float(w)), max(0.0, float(h)))

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run an imperative command on one view; returns its JSON result or ``None``."""
        if tag not in self._types:
            raise CommitError(f"Command {name!r} addressed stale view {tag}")
        result = self.transport.command(tag, name, codec.dumps(codec.to_jsonable(args or {})))
        return codec.loads(result)

    def set_animated_property(self, tag: int, prop_name: str, value: Any) -> None:
        """Write one animated property value without animating (a Python-driven frame)."""
        if tag not in self._types:
            return
        self.transport.animate(tag, codec.dumps({"op": "set", "prop": prop_name, "value": codec.to_jsonable(value)}))

    def install_animation_graph(self, tag: int, graph: dict[str, Any]) -> None:
        """Install native expression nodes and view bindings in one crossing."""
        if tag in self._types:
            self.transport.animate(tag, codec.dumps({"op": "graph", "graph": graph}))

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
        """Start a native-driven animation; returns whether native accepted it."""
        if tag not in self._types:
            return False
        request = {"op": "start", "id": int(anim_id), "prop": prop_name, "spec": codec.to_jsonable(spec)}
        result = codec.loads(self.transport.animate(tag, codec.dumps(request)))
        return bool(isinstance(result, dict) and result.get("ok"))

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        """Cancel a native animation and return its presentation value, if known."""
        if tag not in self._types:
            return None
        result = codec.loads(self.transport.animate(tag, codec.dumps({"op": "cancel", "id": int(anim_id)})))
        if isinstance(result, dict):
            return result.get("value")
        return None

    def reset(self) -> None:
        """Forget a disconnected surface before the host remounts its tree."""
        self._types.clear()
        self._refs.clear()
        self._python_props.clear()
        self._commit = CommitState(str(uuid.uuid4()), 1)
        self._births: dict[int, int] = {}
        self._event_sequences: dict[tuple[int, str], int] = {}
        self._failed = False


def _bound(value: float) -> float:
    """Clamp ``math.inf`` to the wire's "unconstrained" sentinel."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return _MEASURE_UNBOUNDED
    if not math.isfinite(f) or f > _MEASURE_UNBOUNDED:
        return _MEASURE_UNBOUNDED
    return max(0.0, f)
