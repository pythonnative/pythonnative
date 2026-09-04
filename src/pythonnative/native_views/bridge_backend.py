"""The on-device view backend: every mutation crosses the bridge as one transaction.

[`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
implements the same protocol the reconciler expects from
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
(``apply_mutations``, ``resolve_view``, ``measure_intrinsic``,
``command``, and the animation hooks) but owns no native objects. It
serializes each commit with
[`encode_transaction`][pythonnative.bridge.codec.encode_transaction]
and hands the JSON to the platform transport; Swift and Kotlin
component managers do the rest.

Python keeps two small pieces of per-tag state:

- A **prop sidecar** for values that can't cross the bridge (the
  ``render_row`` callable of a ``VirtualList``).
- **Row pools** for virtualized lists, so the synchronous
  ``on_bind_row`` protocol can mount a row subtree and answer with its
  root tag.

Views are addressed by tag everywhere. ``resolve_view`` returns a
[`NativeViewRef`][pythonnative.native_views.bridge_backend.NativeViewRef],
the opaque handle refs receive.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..bridge import codec, get_transport
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
        self._types: Dict[int, str] = {}
        self._refs: Dict[int, NativeViewRef] = {}
        self._python_props: Dict[int, Dict[str, Any]] = {}
        self._row_pools: Dict[int, Any] = {}
        self._handlers: Dict[str, Any] = {}

    @property
    def transport(self) -> Any:
        """The transport in use (resolved lazily on first access)."""
        if self._transport is None:
            self._transport = get_transport()
        return self._transport

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
        # Bookkeeping first so a native failure never leaves Python
        # believing a destroyed tag is still live.
        destroyed: List[int] = []
        for op in ops:
            if isinstance(op, CreateOp):
                self._types[op.tag] = op.type_name
                self._refs[op.tag] = NativeViewRef(op.tag, op.type_name)
            elif isinstance(op, DestroyOp):
                destroyed.append(op.tag)
        payload, sidecar = codec.encode_transaction(ops)
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
        self.transport.apply(payload)
        for tag in destroyed:
            self._forget(tag)

    def _forget(self, tag: int) -> None:
        self._types.pop(tag, None)
        self._refs.pop(tag, None)
        self._python_props.pop(tag, None)
        pool = self._row_pools.pop(tag, None)
        if pool is not None:
            pool.release_all()

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
            return None
        result = self.transport.command(tag, name, codec.dumps(codec.to_jsonable(args or {})))
        return codec.loads(result)

    def set_animated_property(self, tag: int, prop_name: str, value: Any) -> None:
        """Write one animated property value without animating (a Python-driven frame)."""
        if tag not in self._types:
            return
        self.transport.animate(tag, codec.dumps({"op": "set", "prop": prop_name, "value": codec.to_jsonable(value)}))

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

    # ------------------------------------------------------------------
    # Internal (native-originated) events
    # ------------------------------------------------------------------

    def handle_internal_event(self, tag: int, name: str, args: List[Any]) -> Any:
        """Serve request-style events that no user callback owns.

        Currently the virtualized-list row protocol:

        - ``on_bind_row`` ``[{"container", "index", "width", "height"}]``
          mounts or rebinds the row subtree and returns ``{"root": tag}``.
        - ``on_unbind_row`` ``[{"container"}]`` releases it.
        """
        if name == "on_bind_row":
            return self._bind_row(tag, args[0] if args else {})
        if name == "on_unbind_row":
            info = args[0] if args else {}
            pool = self._row_pools.get(tag)
            if pool is not None and isinstance(info, dict):
                pool.release(int(info.get("container", 0)))
            return None
        return None

    def _bind_row(self, tag: int, info: Any) -> Dict[str, Any]:
        if not isinstance(info, dict):
            return {"root": None}
        render_row = self._python_props.get(tag, {}).get("render_row")
        if not callable(render_row):
            return {"root": None}
        from ..virtual_rows import RowHostPool

        pool = self._row_pools.get(tag)
        if pool is None:
            pool = RowHostPool()
            self._row_pools[tag] = pool
        index = int(info.get("index", 0))
        width = float(info.get("width", 0.0) or 0.0)
        height = float(info.get("height", 0.0) or 0.0)
        root = pool.bind(int(info.get("container", 0)), lambda: render_row(index), width, height)
        root_tag = getattr(root, "tag", None)
        return {"root": int(root_tag) if root_tag is not None else None}

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Forget every view: the native side is gone (browser tab closed, tests)."""
        for pool in list(self._row_pools.values()):
            pool.release_all()
        self._row_pools.clear()
        self._types.clear()
        self._refs.clear()
        self._python_props.clear()


def _bound(value: float) -> float:
    """Clamp ``math.inf`` to the wire's "unconstrained" sentinel."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return _MEASURE_UNBOUNDED
    if not math.isfinite(f) or f > _MEASURE_UNBOUNDED:
        return _MEASURE_UNBOUNDED
    return max(0.0, f)
