"""The view backend that commits to the renderer core (RFC 0007).

Each commit is built as wire operations once, serialized once, and handed
to the core, which validates it, applies it to its shadow tree, lays it
out, and queues the mount for the platform's UI thread. The acknowledgement
arrives when the core has accepted and laid out the commit, before widgets
exist; commands and animation requests issued afterward queue behind that
mount, so they always reach the widgets it creates. Rejected commits leave
the surface as it was; a failed mount poisons it until it is remounted.

Native events carry application, revision, sequence, and text edit
identities. NativeViewRef holds a live native tag rather than a UI object.
"""

from __future__ import annotations

import asyncio
import itertools
import time
import uuid
import weakref
from typing import Any, Dict, List, Optional, Sequence

from ..bridge import PROTOCOL_VERSION, codec, get_transport
from ..mutations import UNSET, CreateOp, DestroyOp, InsertOp, Mutation, UpdateOp

__all__ = ["BridgeBackend", "CommitError", "NativeViewRef", "SURFACE"]

SURFACE = 1
"""The surface every host mounts into; the core supports more, hosts use one."""


class CommitError(RuntimeError):
    """A malformed, stale, or failed native transaction."""


class NativeViewRef:
    """Opaque handle to a native view living on the other side of the bridge.

    Attributes:
        tag: The reconciler-assigned tag; pass it to
            ``Reconciler.dispatch_command`` or ``get_backend().command``.
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
    """Backend protocol implementation that commits to the renderer core."""

    native_layout = True
    """Layout always runs in the core; there is no Python layout engine."""

    selective_layout = True
    """Ask the core for observed frames only (tests ask for every frame)."""

    def __init__(self, transport: Any = None, *, surface: int = SURFACE) -> None:
        self._transport = transport
        self.surface = surface
        self._application = str(uuid.uuid4())
        self._revision = 0
        self._births: dict[int, int] = {}
        self._event_sequences: dict[int, dict[str, int]] = {}
        self._edit_revisions: dict[int, int] = {}
        self._failed = False
        self._pending: asyncio.Future[None] | None = None
        self._publishing = False
        self._queued_commits: set[asyncio.Task[None]] = set()
        self._layout_listeners: list[Any] = []
        self._queued_events: list[tuple[int, str, dict[str, Any]]] = []
        self.on_layout: Any = None
        self._types: Dict[int, str] = {}
        self._refs: Dict[int, NativeViewRef] = {}
        self._python_props: Dict[int, Dict[str, Any]] = {}
        self._layout_request: Any = None
        self._layout_required = True
        self._pending_layout_request: dict[str, Any] | None = None
        self._call_ids = itertools.count(1)
        self._commands: dict[int, tuple[asyncio.Future[Any], str, str]] = {}
        bind = getattr(transport, "bind", None)
        if bind is not None:
            bind(self)

    @property
    def transport(self) -> Any:
        """The transport in use (resolved lazily on first access)."""
        if self._transport is None:
            self._transport = get_transport()
        return self._transport

    def _ensure_contracts(self) -> None:
        """Compile newly registered contracts into the core before they're used."""
        from ..bridge import ensure_contracts

        ensure_contracts(self.transport)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def prepare_layout(self, roots: list[int], width: float, height: float) -> None:
        """Include the layout request in the next commit when a viewport is known."""
        if roots and width > 0 and height > 0:
            self._pending_layout_request = {
                "roots": roots,
                "width": width,
                "height": height,
                "selective": self.selective_layout,
            }
        else:
            self._pending_layout_request = None

    def compute_layout(self, roots: list[int], width: float, height: float) -> None:
        """Lay out in the core without a commit, publishing changed frames."""
        request = (tuple(roots), width, height)
        if not self._layout_required and self._layout_request == request:
            return
        from ..profiling import count

        count("layout.requests")
        self._ensure_contracts()
        raw = self.transport.layout(
            codec.dumps(
                {
                    "surface": self.surface,
                    "roots": roots,
                    "width": width,
                    "height": height,
                    "selective": self.selective_layout,
                }
            )
        )
        result = codec.loads(raw)
        if not isinstance(result, dict) or not result.get("ok"):
            raise CommitError(f"Native layout failed: {result!r}")
        self._layout_required = False
        self._layout_request = request
        self.accept_layout(result.get("value"))

    def subscribe_layout(self, callback: Any) -> None:
        """Observe geometry without retaining an unmounted reconciler."""
        self._layout_listeners.append(weakref.WeakMethod(callback))

    def accept_layout(self, payload: Any) -> None:
        """Accept geometry only for this surface's current committed revision."""
        if not isinstance(payload, dict):
            raise CommitError("Layout must identify its committed surface")
        identity = tuple(payload.get(key) for key in ("application", "surface", "revision"))
        if identity != (self._application, self.surface, self._revision):
            return
        frames = payload.get("frames")
        if not isinstance(frames, list):
            raise CommitError("Layout frames must be an array")
        from ..profiling import native_sample

        metrics = payload.get("metrics", {})
        if isinstance(metrics, dict):
            duration = metrics.get("layout_ns")
            visited = metrics.get("visited", metrics.get("views", 0))
            if type(duration) is int and duration >= 0 and type(visited) is int and visited >= 0:
                native_sample("layout", duration, views=visited, changed_frames=len(frames))
        if self.on_layout is not None:
            self.on_layout(frames)
        self._layout_listeners = [ref for ref in self._layout_listeners if ref() is not None]
        for reference in self._layout_listeners:
            callback = reference()
            if callback is not None:
                callback(frames)

    async def measure_in_window(self, tag: int) -> Optional[tuple[float, float, float, float]]:
        """The view's frame in its screen's coordinates, read from the core's shadow tree."""
        if tag not in self._types:
            return None
        value = codec.loads(self.transport.measure(self.surface, tag))
        if not isinstance(value, dict):
            return None
        x, y, width, height = value["window"]
        return (float(x), float(y), float(width), float(height))

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
        """Number of views in the core's shadow tree."""
        return len(self._types)

    def python_props(self, tag: int) -> Dict[str, Any]:
        """Props held Python-side for ``tag`` (callables never sent to native)."""
        return self._python_props.get(tag, {})

    # ------------------------------------------------------------------
    # Commit channel
    # ------------------------------------------------------------------

    def apply_mutations(self, ops: Sequence[Mutation]) -> asyncio.Future[None] | None:
        """Build, serialize, and commit ``ops`` to the core in one crossing.

        A ``TextInput`` value update echoes the last edit revision the
        native side reported, so native can discard a stale value that
        raced a newer keystroke.
        """
        if not ops:
            return None
        if self._pending is not None:
            # Hosts share the process surface. Commit against the acknowledged
            # revision only when this transaction reaches the front of the queue.
            from ..journal import detached_context
            from ..runtime import get_loop

            layout = self._pending_layout_request
            queued_ops = tuple(ops)

            async def submit() -> None:
                while self._pending is not None:
                    try:
                        await asyncio.shield(self._pending)
                    except Exception:
                        pass  # apply_mutations checks whether the surface survived.
                self._pending_layout_request = layout
                pending = self.apply_mutations(queued_ops)
                if pending is not None:
                    await asyncio.shield(pending)

            task = get_loop().create_task(submit(), context=detached_context())
            from ..profiling import gauge

            self._queued_commits.add(task)
            gauge("commit.queued", len(self._queued_commits))

            def dequeued(finished: asyncio.Task[None]) -> None:
                self._queued_commits.discard(finished)
                gauge("commit.queued", len(self._queued_commits))

            task.add_done_callback(dequeued, context=detached_context())
            return task
        if self._failed:
            raise CommitError("Native surface failed; remount the application with a new backend")
        self._ensure_contracts()
        wire_ops, sidecar = codec.build_transaction(ops, self._types)
        for op in wire_ops:
            if op[0] == "u" and self._types.get(op[1]) == "TextInput" and "value" in op[2]:
                op[2]["_pn_edit_revision"] = self._edit_revisions.get(op[1], 0)
        revision = self._revision + 1
        envelope: Dict[str, Any] = {
            "version": PROTOCOL_VERSION,
            "application": self._application,
            "surface": self.surface,
            "revision": revision,
            "ops": wire_ops,
        }
        if self._pending_layout_request is not None:
            envelope["layout"] = self._pending_layout_request
        payload = codec.dumps(envelope)
        from ..profiling import count, native_sample, span

        count("bridge.commits")
        count("bridge.operations", len(ops))
        count("bridge.bytes", len(payload.encode("utf-8")))

        def complete(raw: str) -> None:
            self._accept_commit(codec.loads(raw), revision, envelope, ops, sidecar)

        from ..runtime import get_loop

        loop = get_loop()
        if getattr(self.transport, "asynchronous_commits", False) and loop.is_running():
            from ..journal import detached_context

            result: asyncio.Future[None] = loop.create_future()
            self._pending = result
            self._publishing = True
            started = time.perf_counter_ns()
            # The executor runs the core's validation and layout with the GIL
            # released, so the application loop keeps handling input.
            worker = loop.run_in_executor(None, self.transport.commit, payload)

            def acknowledged(future: asyncio.Future[str]) -> None:
                self._pending = None
                try:
                    raw = future.result()
                    with span("acknowledgement"):
                        complete(raw)
                    native_sample("commit_wait", time.perf_counter_ns() - started)
                    if not result.cancelled():
                        result.set_result(None)
                    else:
                        self._failed = True
                except BaseException as error:
                    if not isinstance(error, CommitError):
                        self._failed = True
                    self._publishing = False
                    self._queued_events.clear()
                    if not result.done():
                        result.set_exception(error)

            worker.add_done_callback(acknowledged, context=detached_context())
            return result
        try:
            with span("transport.commit"):
                raw = self.transport.commit(payload)
        except BaseException:
            self._failed = True
            raise
        complete(raw)
        return None

    def _accept_commit(
        self,
        ack: Any,
        revision: int,
        envelope: dict[str, Any],
        ops: Sequence[Mutation],
        sidecar: list[tuple[int, dict[str, Any]]],
    ) -> None:
        from ..profiling import gauge, native_sample

        if not isinstance(ack, dict) or not ack.get("ok") or ack.get("revision") != revision:
            # A rejection leaves the core's tree as it was, so the same
            # revision can be retried. Unknown outcomes invalidate the surface.
            self._failed = not (isinstance(ack, dict) and ack.get("failed") is False)
            message = ack.get("error") if isinstance(ack, dict) else ack
            raise CommitError(f"Native commit {revision} rejected: {message}")
        metrics = ack.get("metrics", {})
        if isinstance(metrics, dict):
            for phase in ("validate", "commit"):
                duration = metrics.get(phase + "_ns")
                if type(duration) is int and duration >= 0:
                    native_sample(phase, duration, operations=len(ops) if phase == "commit" else 0)
        self._revision = revision
        from ..reconciler.layout_pass import affects_layout

        destroyed: List[int] = []
        for op in ops:
            if isinstance(op, (CreateOp, DestroyOp, InsertOp)) or (
                isinstance(op, UpdateOp) and affects_layout(self._types.get(op.tag, ""), op.changed_props)
            ):
                self._layout_required = True
            if isinstance(op, CreateOp):
                self._types[op.tag] = op.type_name
                self._births[op.tag] = revision
                self._refs[op.tag] = NativeViewRef(op.tag, op.type_name)
            elif isinstance(op, DestroyOp):
                destroyed.append(op.tag)
        for tag, props in sidecar:
            self._python_props.setdefault(tag, {}).update(props)
        for op in ops:
            if isinstance(op, UpdateOp):
                # Omission clears the sidecar; an explicit null stays a value.
                bucket = self._python_props.get(op.tag)
                if bucket:
                    for key, value in op.changed_props.items():
                        if value is UNSET:
                            bucket.pop(key, None)
                    if not bucket:
                        self._python_props.pop(op.tag, None)
        for tag in destroyed:
            self._forget(tag)
        if "layout" in envelope:
            layout = envelope["layout"]
            self.accept_layout(ack.get("layout"))
            self._layout_request = (tuple(layout["roots"]), layout["width"], layout["height"])
            self._layout_required = False
        gauge("native.views", self.live_view_count())

    def surface_failed(self, payload: Any) -> None:
        """The UI thread couldn't mount a transaction; the surface needs a remount."""
        self._failed = True
        error = payload.get("error") if isinstance(payload, dict) else payload
        from .. import diagnostics

        diagnostics.report_error(CommitError(f"Native mount failed: {error}"), phase="native mount")

    def defer_event(self, tag: int, name: str, envelope: Any) -> bool:
        """Keep input ordered until its commit and Python effects publish."""
        if self._pending is None and not self._publishing:
            return False
        if isinstance(envelope, dict):
            if len(self._queued_events) >= 4096:
                self._failed = True
                raise CommitError("Native input queue exceeded 4096 events while a commit was pending")
            self._queued_events.append((tag, name, envelope))
        return True

    def release_events(self) -> None:
        """Deliver events after refs and effects have observed a successful commit."""
        if self._pending is not None:
            return
        self._publishing = False
        events, self._queued_events = self._queued_events, []
        if self._failed:
            return
        from ..bridge import _on_event
        from ..journal import detached_context
        from ..runtime import get_loop

        for tag, name, envelope in events:
            get_loop().call_soon(_on_event, tag, name, codec.dumps(envelope), self, context=detached_context())

    def accept_event(self, tag: int, name: str, envelope: Any) -> bool:
        """Reject events from destroyed views, earlier applications, and replayed input."""
        if self._failed or not isinstance(envelope, dict):
            return False
        if envelope.get("application") != self._application or envelope.get("surface") != self.surface:
            return False
        revision, sequence = envelope.get("revision"), envelope.get("sequence")
        if type(revision) is not int or type(sequence) is not int or tag not in self._births:
            return False
        sequences = self._event_sequences.setdefault(tag, {})
        if not self._births[tag] <= revision <= self._revision or sequence <= sequences.get(name, 0):
            return False
        arguments = envelope.get("args")
        if not isinstance(arguments, list):
            return False
        from ..sdk.schema import COMPONENTS

        contract = COMPONENTS.get(self._types[tag])
        if contract is not None:
            try:
                envelope["args"] = contract.decode_event(name, arguments)
            except TypeError as error:
                from ..diagnostics import warn_once

                warn_once(
                    f"Rejected native event for {self._types[tag]} #{tag}: {error}",
                    key=f"native-contract:{self._types[tag]}:{name}",
                )
                return False
        sequences[name] = sequence
        if name == "on_change" and self._types.get(tag) == "TextInput":
            edit = envelope.get("edit_revision")
            if type(edit) is int:
                self._edit_revisions[tag] = max(edit, self._edit_revisions.get(tag, 0))
        return True

    def _forget(self, tag: int) -> None:
        from ..animated import release_view_backend

        release_view_backend(self, (tag,))
        self._types.pop(tag, None)
        self._births.pop(tag, None)
        self._edit_revisions.pop(tag, None)
        self._event_sequences.pop(tag, None)
        self._refs.pop(tag, None)
        self._python_props.pop(tag, None)

    # ------------------------------------------------------------------
    # Imperative escape hatches
    # ------------------------------------------------------------------

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> asyncio.Future[Any]:
        """Queue a view command behind pending mounts; returns a future for its result.

        Fire-and-forget commands (``focus``, ``scroll_to_offset``) can
        ignore the future; ``await`` it for commands that answer
        (``get_value``, ``get_scroll_offset``).

        Raises:
            CommitError: When ``tag`` is stale, isn't mounted, or the core
                rejects the command's arguments.
        """
        if tag not in self._types:
            raise CommitError(f"Command {name!r} addressed stale view {tag}")
        from ..runtime import get_loop
        from ..sdk.schema import COMPONENTS, ModuleSchema

        type_name = self._types[tag]
        schema = COMPONENTS.get(type_name)
        arguments = args or {}
        if schema is not None:
            arguments = ModuleSchema(schema.name, schema.commands).validate_call(name, arguments)
        call_id = next(self._call_ids)
        future: asyncio.Future[Any] = get_loop().create_future()
        self._commands[call_id] = (future, type_name, name)
        reply = codec.loads(
            self.transport.command(self.surface, tag, name, codec.dumps(codec.to_jsonable(arguments)), call_id)
        )
        if not isinstance(reply, dict) or not reply.get("ok"):
            self._commands.pop(call_id, None)
            future.cancel()
            raise CommitError(reply.get("error") if isinstance(reply, dict) else f"Command {name!r} failed")
        return future

    def accept_command_result(self, payload: Any) -> None:
        """Resolve the future of a command the UI thread ran."""
        if not isinstance(payload, dict):
            return
        entry = self._commands.pop(int(payload.get("call_id", 0) or 0), None)
        if entry is None:
            return
        future, type_name, name = entry
        if future.done():
            return
        if not payload.get("ok", True):
            future.set_exception(CommitError(str(payload.get("error") or f"Command {name!r} failed")))
            return
        value = payload.get("value")
        from ..sdk.schema import COMPONENTS, ModuleSchema

        schema = COMPONENTS.get(type_name)
        try:
            if schema is not None:
                value = ModuleSchema(schema.name, schema.commands).validate_result(name, value)
        except TypeError as error:
            future.set_exception(error)
            return
        future.set_result(value)

    def _animate(self, tag: int, request: Dict[str, Any]) -> Dict[str, Any]:
        reply = codec.loads(self.transport.animate(self.surface, tag, codec.dumps(codec.to_jsonable(request))))
        return reply if isinstance(reply, dict) else {"ok": False}

    def _targets_animation(self, tag: int, prop_name: str) -> bool:
        """Whether a request can reach the UI thread: graph nodes and unbound values need no view."""
        return tag in self._types or prop_name.startswith(("_pn_graph:", "_pn_value:"))

    def set_animated_property(self, tag: int, prop_name: str, value: Any) -> None:
        """Write one animated property value without animating."""
        if self._targets_animation(tag, prop_name):
            self._animate(tag, {"op": "set", "prop": prop_name, "value": value})

    def install_animation_graph(self, tag: int, graph: dict[str, Any]) -> None:
        """Install expression nodes and view bindings on the UI thread."""
        if tag in self._types:
            self._animate(tag, {"op": "graph", "graph": graph})

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
        """Start a driver on the UI thread; returns whether the core accepted the request."""
        if not self._targets_animation(tag, prop_name):
            return False
        return bool(self._animate(tag, {"op": "start", "id": int(anim_id), "prop": prop_name, "spec": spec}).get("ok"))

    def cancel_animation(self, tag: int, anim_id: int) -> None:
        """Stop a driver; its value arrives with the ``animation`` message that reports the cancellation."""
        self._animate(tag, {"op": "cancel", "id": int(anim_id)})

    def reset(self) -> None:
        """Forget a disconnected surface before the host remounts its tree."""
        if self._pending is not None:
            raise CommitError("Wait for the in-flight commit before resetting its surface")
        if any(not task.done() for task in self._queued_commits):
            raise CommitError("Wait for queued commits before resetting the surface")
        from ..animated import release_view_backend

        release_view_backend(self, list(self._types))
        self._publishing = False
        self._queued_events.clear()
        self._types.clear()
        self._refs.clear()
        self._python_props.clear()
        self._application = str(uuid.uuid4())
        self._revision = 0
        self._births = {}
        self._event_sequences = {}
        self._failed = False
        self._edit_revisions.clear()
        self._layout_required = True
        self._layout_request = None
        for future, _, _ in self._commands.values():
            future.cancel()
        self._commands.clear()
