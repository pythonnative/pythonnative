"""An in-process stand-in for the native side of the bridge.

[`FakeTransport`][pythonnative.bridge.fake.FakeTransport] decodes the
same JSON the Swift and Kotlin runtimes receive and keeps a tiny view
tree so tests can assert on what *would* have reached native: created
types and props, insert order, frames, commands, animation requests,
and module calls. It also lets tests play the native side, firing
events and module results back through
[`native_callback`][pythonnative.bridge.native_callback].
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import codec

__all__ = ["FakeNativeView", "FakeTransport"]


class FakeNativeView:
    """One decoded native view: type, merged props, children, and frame."""

    def __init__(self, tag: int, type_name: str, props: Dict[str, Any]) -> None:
        self.tag = tag
        self.type_name = type_name
        self.props: Dict[str, Any] = dict(props)
        self.children: List["FakeNativeView"] = []
        self.parent: Optional["FakeNativeView"] = None
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def __repr__(self) -> str:
        return f"<native {self.type_name} tag={self.tag}>"


ModuleHandler = Callable[[str, Dict[str, Any]], Any]
"""``handler(method, args) -> value`` for a fake native module."""

DEFAULT_MEASURE: Dict[str, Tuple[float, float]] = {
    "Text": (60.0, 16.0),
    "Button": (80.0, 32.0),
    "Image": (40.0, 40.0),
    "TextInput": (120.0, 32.0),
    "TabBar": (320.0, 49.0),
}


class FakeTransport:
    """Decode bridge traffic into inspectable Python structures.

    Attributes:
        views: Live views by tag.
        transactions: Every decoded transaction (list of op lists).
        commands: ``(tag, name, args)`` tuples in call order.
        animations: ``(tag, request)`` tuples in call order.
        calls: ``(module, method, args)`` tuples in call order.
    """

    name = "fake"

    def __init__(self, *, version: int = 1, measure: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        self._version = version
        self.measure_table = dict(DEFAULT_MEASURE if measure is None else measure)
        self.views: Dict[int, FakeNativeView] = {}
        self.transactions: List[List[Any]] = []
        self.commands: List[Tuple[int, str, Dict[str, Any]]] = []
        self.animations: List[Tuple[int, Dict[str, Any]]] = []
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []
        self.command_results: Dict[str, Any] = {}
        self.animate_results: Dict[str, Any] = {"start": {"ok": True}}
        self.module_handlers: Dict[str, ModuleHandler] = {}
        self.pending_calls: List[Tuple[str, int, str, Dict[str, Any]]] = []
        self.callback: Optional[Callable[[str, int, str, str], Optional[str]]] = None
        self.posted = 0

    # -- Transport protocol ----------------------------------------------

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the native library."""
        return self._version

    def set_callback(self, callback: Callable[[str, int, str, str], Optional[str]]) -> None:
        """Install ``callback`` as the native -> Python entry point."""
        self.callback = callback

    def apply(self, transaction_json: str) -> None:
        """Apply one serialized transaction (a JSON array of ops)."""
        ops = json.loads(transaction_json)
        self.transactions.append(ops)
        for op in ops:
            self._apply_one(op)

    def _apply_one(self, op: List[Any]) -> None:
        code = op[0]
        if code == "c":
            _, tag, type_name, props = op
            if tag in self.views:
                raise AssertionError(f"create: tag {tag} already exists")
            self.views[tag] = FakeNativeView(tag, type_name, props)
        elif code == "u":
            _, tag, changed = op
            view = self._require(tag, "update")
            for key, value in changed.items():
                if value is None:
                    view.props.pop(key, None)
                else:
                    view.props[key] = value
        elif code == "i":
            _, parent_tag, child_tag, index = op
            parent = self._require(parent_tag, "insert")
            child = self._require(child_tag, "insert")
            if child.parent is not None:
                child.parent.children.remove(child)
            index = max(0, min(int(index), len(parent.children)))
            parent.children.insert(index, child)
            child.parent = parent
        elif code == "d":
            _, tag = op
            view = self.views.pop(tag, None)
            if view is None:
                raise AssertionError(f"destroy: unknown tag {tag}")
            if view.parent is not None:
                view.parent.children.remove(view)
                view.parent = None
        elif code == "f":
            _, tag, x, y, w, h = op
            self._require(tag, "set_frame").frame = (float(x), float(y), float(w), float(h))
        else:
            raise AssertionError(f"unknown opcode {code!r}")

    def _require(self, tag: int, what: str) -> FakeNativeView:
        view = self.views.get(tag)
        if view is None:
            raise AssertionError(f"{what}: unknown tag {tag}")
        return view

    def measure(self, tag: int, max_width: float, max_height: float) -> Tuple[float, float]:
        """Return the intrinsic ``(width, height)`` of the view ``tag`` under the constraints."""
        view = self.views.get(tag)
        if view is None:
            return (0.0, 0.0)
        return self.measure_table.get(view.type_name, (0.0, 0.0))

    def command(self, tag: int, name: str, args_json: str) -> Optional[str]:
        """Run an imperative command on one view; returns its JSON result or ``None``."""
        args = codec.loads(args_json) or {}
        self.commands.append((tag, name, args))
        result = self.command_results.get(name)
        return None if result is None else codec.dumps(result)

    def animate(self, tag: int, request_json: str) -> Optional[str]:
        """Handle an animation request (``set`` / ``start`` / ``cancel``) for one view."""
        request = codec.loads(request_json) or {}
        self.animations.append((tag, request))
        result = self.animate_results.get(str(request.get("op")))
        return None if result is None else codec.dumps(result)

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        envelope = codec.loads(args_json) or {}
        args = envelope.get("args") or {}
        call_id = int(envelope.get("call_id", 0) or 0)
        self.calls.append((module, method, args))
        if module == "Host" and method == "post":
            self.posted += 1
            return codec.dumps({"ok": True, "value": None})
        handler = self.module_handlers.get(module)
        if handler is None:
            return codec.dumps({"ok": True, "value": None})
        try:
            value = handler(method, args)
        except Exception as exc:
            return codec.dumps({"ok": False, "error": str(exc)})
        if value is _PENDING:
            self.pending_calls.append((module, call_id, method, args))
            return codec.dumps({"pending": True})
        return codec.dumps({"ok": True, "value": codec.to_jsonable(value)})

    # -- Playing the native side ------------------------------------------

    def fire(self, tag: int, name: str, *args: Any) -> Any:
        """Emit a view event as native would; returns the decoded handler result."""
        return self._callback("event", tag, name, codec.dumps([codec.to_jsonable(a) for a in args]))

    def emit_module_event(self, module: str, event: str, payload: Any = None) -> None:
        """Push an unsolicited module event (``AppState`` ``change``, ...) into Python."""
        self._callback("module", 0, module, codec.dumps({"event": event, "payload": codec.to_jsonable(payload)}))

    def resolve_pending(self, call_id: int, value: Any = None, *, error: Optional[str] = None) -> None:
        """Settle a call that returned ``pending``."""
        module = next((m for m, cid, _, _ in self.pending_calls if cid == call_id), None)
        if module is None:
            raise AssertionError(f"no pending call with id {call_id}")
        self.pending_calls = [p for p in self.pending_calls if p[1] != call_id]
        body: Dict[str, Any] = {"call_id": call_id, "ok": error is None}
        if error is None:
            body["value"] = codec.to_jsonable(value)
        else:
            body["error"] = error
        self._callback("module", 0, module, codec.dumps(body))

    def host_event(self, screen: int, event: str, payload: Any = None) -> Any:
        """Deliver a screen lifecycle event as the native host would; returns the decoded result."""
        return self._callback("host", screen, event, codec.dumps(codec.to_jsonable(payload)))

    def pump(self) -> None:
        """Deliver the ``pump`` callback (what ``Host.post`` would trigger)."""
        self._callback("pump", 0, "", "")

    def complete_animation(self, anim_id: int, finished: bool = True) -> None:
        """Report a native animation as finished (or interrupted) to Python."""
        self._callback("animation", 0, "", codec.dumps({"id": anim_id, "finished": finished}))

    def _callback(self, kind: str, tag: int, name: str, payload: str) -> Any:
        if self.callback is None:
            raise AssertionError("FakeTransport has no callback; install it with pythonnative.bridge.set_transport")
        return codec.loads(self.callback(kind, tag, name, payload))

    # -- Introspection -----------------------------------------------------

    def find(self, type_name: str) -> List[FakeNativeView]:
        """Every live view whose type is ``type_name``, in creation order."""
        return [v for v in self.views.values() if v.type_name == type_name]

    def roots(self) -> List[FakeNativeView]:
        """Views with no parent (the attached screen roots and detached subtrees)."""
        return [v for v in self.views.values() if v.parent is None]

    @staticmethod
    def pending() -> object:
        """Sentinel a module handler returns to answer ``pending``."""
        return _PENDING


_PENDING = object()
