"""The host renderer core with Python playing the platform's UI thread.

[`FakeTransport`][pythonnative.bridge.fake.FakeTransport] commits to the
host build of the same C++ core the apps link, so tests see the shipping
validation, layout, flattening, list datasets, animation, and gestures. It
mounts each transaction right away into a small tree of
[`FakeNativeView`][pythonnative.bridge.fake.FakeNativeView] objects, so
tests can assert on what the platform would have mounted: created types
and props, insert order, frames, commands, animated writes, and module
calls. It also lets tests play the native side, firing events, pointers,
and module results back into Python.

Every transport owns one core surface, so several can live in one test.
They share the process's core and one Python platform, which routes each
surface's mounts, measurements, and messages to its transport. Display
frames for animations run as timers on the framework loop, so a
[`FakeClock`][pythonnative.testing.FakeClock] drives them.
"""

from __future__ import annotations

import json
import weakref
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import codec
from .core import PROTOCOL_VERSION, MountOp, MountTransaction, Platform, RendererCore, decode_transaction, load_core

__all__ = ["DEFAULT_MEASURE", "FakeNativeView", "FakeTransport", "reset_fakes"]


class FakeNativeView:
    """One mounted view: type, merged props, mounted children, frame, and animated values."""

    def __init__(self, tag: int, type_name: str, props: Dict[str, Any]) -> None:
        self.tag = tag
        self.type_name = type_name
        self.props: Dict[str, Any] = dict(props)
        self.children: List["FakeNativeView"] = []
        self.parent: Optional["FakeNativeView"] = None
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.animated: Dict[str, Any] = {}

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
"""What the fake platform measures for content-sized leaves (and reports for loaded images)."""


# ======================================================================
# The shared fake platform
# ======================================================================

_transports: "weakref.WeakValueDictionary[int, FakeTransport]" = weakref.WeakValueDictionary()
_installed: Optional[RendererCore] = None
_frame_handle: Any = None
_work_handle: Any = None
_mounting = False


def _owner(surface: int) -> Optional["FakeTransport"]:
    return _transports.get(int(surface))


def _measure(
    surface: int,
    tag: int,
    component: str,
    mode: int,
    props: Dict[str, Any],
    width: float,
    width_mode: int,
    height: float,
    height_mode: int,
) -> Tuple[float, float]:
    transport = _owner(surface)
    if transport is None:
        return (0.0, 0.0)
    transport.measured.append((tag, component))
    max_width = width if width_mode else float("inf")
    max_height = height if height_mode else float("inf")
    if transport.measurer is not None:
        return transport.measurer(tag, component, props, max_width, max_height)
    del mode
    return transport.measure_table.get(component, (0.0, 0.0))


def _emit(kind: str, surface: int, tag: int, name: str, payload: str) -> None:
    transport = _owner(surface)
    if transport is not None:
        transport._callback(kind, tag, name, payload)


def _schedule_work() -> None:
    # Deferred work (relayout after an image loads) runs on a later loop
    # turn, after Python has accepted the commit that caused it.
    global _work_handle
    if _work_handle is not None:
        return
    from ..runtime import get_loop

    _work_handle = get_loop().call_soon(_run_work)


def _run_work() -> None:
    global _work_handle
    _work_handle = None
    if _installed is not None:
        _installed.work()
        _mount_all()


def _request_frames() -> None:
    global _frame_handle
    if _frame_handle is not None:
        return
    from ..runtime import get_loop

    _frame_handle = get_loop().call_soon(_frame)


def _frame() -> None:
    """One display frame on the framework loop's clock."""
    global _frame_handle
    from ..runtime import get_loop

    loop = get_loop()
    running = _installed is not None and _installed.animation_frame(loop.time() * 1000.0)
    _take_writes()
    _mount_all()
    _frame_handle = loop.call_later(1.0 / 60.0, _frame) if running else None


def _take_writes() -> None:
    if _installed is None:
        return
    for tag, prop, value in _installed.take_writes():
        for transport in list(_transports.values()):
            view = transport.views.get(tag)
            if view is not None or transport.owns(tag):
                transport.writes.append((tag, prop, value))
                if view is not None:
                    view.animated[prop] = value
                break


def _mount_all() -> None:
    """Apply every queued transaction to the transport owning its surface."""
    global _mounting
    if _installed is None or _mounting:
        return
    _mounting = True
    try:
        while True:
            taken = _installed.mount_next()
            if taken is None:
                break
            data, ident = taken
            transaction = decode_transaction(data)
            transport = _owner(transaction.surface)
            error: Optional[str] = None
            if transport is not None:
                transport.transactions.append(transaction)
                try:
                    for op in transaction.ops:
                        transport._apply(op)
                except AssertionError as exc:
                    error = str(exc)
            _installed.mount_finished(ident, error)
            _take_writes()
    finally:
        _mounting = False


def _install(core: RendererCore) -> None:
    global _installed
    if _installed is core:
        return
    core.set_platform(
        Platform(
            schedule_mount=lambda: None,
            schedule_work=_schedule_work,
            request_frames=_request_frames,
            measure=_measure,
            emit=_emit,
        )
    )
    _installed = core


def reset_fakes() -> None:
    """Forget every fake surface and the core's state (the pytest plugin calls this between tests)."""
    global _frame_handle, _work_handle
    for handle in (_frame_handle, _work_handle):
        if handle is not None:
            handle.cancel()
    _frame_handle = None
    _work_handle = None
    _transports.clear()
    if _installed is not None:
        _installed.reset()
    from . import _loaded_contracts

    _loaded_contracts.clear()  # the reset dropped every compiled contract


# ======================================================================
# The transport
# ======================================================================


class FakeTransport:
    """Commit to the host core and record what the UI thread would mount.

    Args:
        surface: The core surface this transport's backend commits to
            (``1``, the device surface, by default).
        measure: Sizes the fake platform measures, by component name.

    Attributes:
        core: The bound host core.
        views: Mounted views by tag (flattened views never appear).
        transactions: Every decoded mount transaction.
        commands: ``(tag, name, args)`` tuples in the order the UI thread ran them.
        writes: ``(tag, prop, value)`` animated writes, in order.
        calls: ``(module, method, args)`` tuples in call order.
        measured: ``(tag, component)`` pairs the core asked the platform to measure.
    """

    name = "fake"
    asynchronous_commits = False

    def __init__(
        self,
        *,
        surface: int = 1,
        version: int = PROTOCOL_VERSION,
        measure: Optional[Dict[str, Tuple[float, float]]] = None,
        core: Optional[RendererCore] = None,
    ) -> None:
        self.surface = surface
        self._version = version
        self.core = core if core is not None else load_core()
        _install(self.core)
        _transports[surface] = self
        self.measure_table = dict(DEFAULT_MEASURE if measure is None else measure)
        self.measurer: Optional[Callable[[int, str, Dict[str, Any], float, float], Tuple[float, float]]] = None
        """Optional ``(tag, component, props, max_width, max_height) -> size`` override."""
        self.views: Dict[int, FakeNativeView] = {}
        self.transactions: List[MountTransaction] = []
        self.commands: List[Tuple[int, str, Dict[str, Any]]] = []
        self.writes: List[Tuple[int, str, Any]] = []
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []
        self.measured: List[Tuple[int, str]] = []
        self.command_results: Dict[str, Any] = {}
        self.command_handler: Optional[Callable[[FakeNativeView, str, Dict[str, Any]], Any]] = None
        self.module_handlers: Dict[str, ModuleHandler] = {}
        self.pending_calls: List[Tuple[str, int, str, Dict[str, Any]]] = []
        self.callback: Optional[Callable[[str, int, str, str], Optional[str]]] = None
        self.list_revisions: Dict[int, int] = {}
        self.reports_images = True
        """Report each mounted ``Image``'s measured size as if it loaded, as a platform loader would."""
        self._tags: set[int] = set()

    def bind(self, backend: Any) -> None:
        """Route this surface's messages to ``backend`` unless a callback was installed."""
        if self.callback is None:
            from . import dispatch

            self.callback = lambda kind, tag, name, payload: dispatch(kind, tag, name, payload, backend)

    def owns(self, tag: int) -> bool:
        """Whether ``tag`` was ever mounted on this transport's surface."""
        return tag in self._tags

    # -- Transport protocol ------------------------------------------------

    def protocol_version(self) -> int:
        """Return the protocol version compiled into the renderer core."""
        return self._version

    def set_callback(self, callback: Callable[[str, int, str, str], None]) -> None:
        """Install ``callback`` as the native -> Python entry point."""
        self.callback = callback

    def load_contracts(self, document: str) -> None:
        """Compile the merged component contracts into the host core."""
        self.core.load_contracts(document, "host")

    def commit(self, envelope_json: str) -> str:
        """Commit, then mount the resulting transaction as the UI thread would."""
        ack = self.core.commit(envelope_json)
        _mount_all()
        return ack

    def layout(self, request_json: str) -> str:
        """Lay out without a commit and mount the frames."""
        result = self.core.layout(request_json)
        _mount_all()
        return result

    def command(self, surface: int, tag: int, name: str, args_json: str, call_id: int) -> str:
        """Queue a view command and run it on the fake UI thread."""
        result = self.core.command(surface, tag, name, args_json, call_id)
        _mount_all()
        return result

    def animate(self, surface: int, tag: int, request_json: str) -> str:
        """Queue an animation request and run it on the fake UI thread."""
        result = self.core.animate(surface, tag, request_json)
        _mount_all()
        return result

    def measure(self, surface: int, tag: int) -> str:
        """The shadow and window frames of a view."""
        return self.core.measure(surface, tag)

    def call(self, module: str, method: str, args_json: str) -> Optional[str]:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        envelope = codec.loads(args_json) or {}
        args = envelope.get("args") or {}
        call_id = int(envelope.get("call_id", 0) or 0)
        self.calls.append((module, method, args))
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

    # -- the fake UI thread ------------------------------------------------

    def drain(self) -> None:
        """Mount queued transactions and run the core's deferred work until both are idle."""
        _mount_all()
        global _work_handle
        if _work_handle is not None:
            _work_handle.cancel()
            _work_handle = None
            self.core.work()
            _mount_all()

    @property
    def animating(self) -> bool:
        """Whether display frames are scheduled for running animations."""
        return _frame_handle is not None

    def _apply(self, op: MountOp) -> None:
        if op.kind == "reset":
            self.views.clear()
        elif op.kind == "create":
            if op.tag in self.views:
                raise AssertionError(f"create: tag {op.tag} already exists")
            self.views[op.tag] = FakeNativeView(op.tag, op.component, op.props)
            self._tags.add(op.tag)
            if op.component == "VirtualList" and "dataset" in op.props:
                self._publish_list(op.tag)
            if op.component in ("Image", "ImageBackground") and self.reports_images and op.props.get("source"):
                width, height = self.measure_table.get("Image", (0.0, 0.0))
                if width > 0 and height > 0:
                    self.core.report_intrinsic(self.surface, op.tag, width, height)
        elif op.kind == "update":
            view = self._require(op.tag, "update")
            view.props.update(op.props)
            for key in op.removed:
                view.props.pop(key, None)
            if view.type_name == "VirtualList" and "dataset" in op.props:
                self._publish_list(op.tag)
        elif op.kind == "insert":
            parent = self._require(op.parent, "insert")
            child = self._require(op.tag, "insert")
            if child.parent is not None:
                child.parent.children.remove(child)
            index = max(0, min(int(op.index), len(parent.children)))
            parent.children.insert(index, child)
            child.parent = parent
        elif op.kind == "delete":
            deleted = self.views.pop(op.tag, None)
            if deleted is None:
                raise AssertionError(f"delete: unknown tag {op.tag}")
            if deleted.parent is not None:
                deleted.parent.children.remove(deleted)
                deleted.parent = None
        elif op.kind == "frame":
            self._require(op.tag, "frame").frame = op.frame
        elif op.kind == "command":
            view = self._require(op.tag, "command")
            arguments = dict(op.arguments or {})
            self.commands.append((op.tag, op.name, arguments))
            if self.command_handler is not None:
                result = self.command_handler(view, op.name, arguments)
            else:
                result = self.command_results.get(op.name)
            self._callback(
                "command",
                0,
                "",
                codec.dumps({"call_id": op.call_id, "ok": True, "value": codec.to_jsonable(result)}),
            )

    def _publish_list(self, tag: int) -> None:
        edits = self.core.list_apply(self.surface, tag)
        if edits is not None:
            self.list_revisions[tag] = int(json.loads(edits)["revision"])
        else:
            # A recreated list view starts from the dataset the core already holds.
            self.list_revisions[tag] = self.core.list_revision(self.surface, tag)

    def _require(self, tag: int, what: str) -> FakeNativeView:
        view = self.views.get(tag)
        if view is None:
            raise AssertionError(f"{what}: unknown tag {tag}")
        return view

    # -- Playing the native side ------------------------------------------

    def fire(self, tag: int, name: str, *args: Any, edit_revision: int = 0) -> None:
        """Emit a view event as the platform would, through the core's stamping."""
        payload = json.dumps([codec.to_jsonable(a) for a in args], separators=(",", ":"))
        self.core.event(self.surface, tag, name, payload, edit_revision)
        _take_writes()

    def pointer(self, tag: int, events: Sequence[Tuple[int, int, float, float, float, float, float]]) -> bool:
        """Feed ``(phase, pointer, x, y, window_x, window_y, time)`` events to a view's gestures."""
        active = self.core.pointer(self.surface, tag, list(events))
        _take_writes()
        return active

    def gesture_deadline(self, tag: int) -> Optional[float]:
        """When a view's gestures next need polling, or ``None``."""
        return self.core.gesture_deadline(self.surface, tag)

    def poll_gestures(self, tag: int, time: float) -> None:
        """Advance time-based gestures for one view (long press, multi-tap windows)."""
        self.core.gesture_poll(self.surface, tag, time)
        _take_writes()

    def report_container(self, tag: int, width: float, height: float, x: float = 0.0, y: float = 0.0) -> None:
        """Report a detached root's container size and relayout."""
        self.core.report_container(self.surface, tag, x, y, width, height)
        self.drain()

    def report_intrinsic(self, tag: int, width: float, height: float) -> None:
        """Report a loaded image's size and relayout."""
        self.core.report_intrinsic(self.surface, tag, width, height)
        self.drain()

    def invalidate(self, tag: int) -> None:
        """Re-measure one leaf and relayout."""
        self.core.invalidate(self.surface, tag)
        self.drain()

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

    def host_event(self, screen: int, event: str, payload: Any = None) -> None:
        """Deliver a screen lifecycle event as the native host would."""
        self._callback("host", screen, event, codec.dumps(codec.to_jsonable(payload)))

    def _callback(self, kind: str, tag: int, name: str, payload: str) -> None:
        if self.callback is None:
            raise AssertionError("FakeTransport has no callback; install it with pythonnative.bridge.set_transport")
        self.callback(kind, tag, name, payload)

    # -- Introspection -----------------------------------------------------

    def find(self, type_name: str) -> List[FakeNativeView]:
        """Every mounted view whose type is ``type_name``, in creation order."""
        return [v for v in self.views.values() if v.type_name == type_name]

    def roots(self) -> List[FakeNativeView]:
        """Mounted views with no parent (the attached screen roots and detached subtrees)."""
        return [v for v in self.views.values() if v.parent is None]

    def list_keys(self, tag: int) -> List[str]:
        """The keys the UI thread's data source holds for a list."""
        return self.core.list_keys(self.surface, tag)

    def list_rows(self, tag: int) -> List[Tuple[str, int, float, bool]]:
        """The ``(key, revision, extent, sticky)`` rows the UI thread holds for a list."""
        return self.core.list_rows(self.surface, tag)

    @staticmethod
    def pending() -> object:
        """Sentinel a module handler returns to answer ``pending``."""
        return _PENDING


_PENDING = object()
