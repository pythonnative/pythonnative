"""Python's side of the motion runtime: installs, requests, and messages (RFC 0009).

Programs, shared values, and bindings live in the renderer core's motion
runtime on the UI thread. This module tracks what each transport's core
already has, batches requests, and sends them behind pending mounts with
``pn_core_motion``. Requests made during a render wait for that render's
commit; others go out on the next turn of the application loop. It also
handles the core's ``motion`` messages: finished animations, calls a
worklet queued with ``run_on_python``, and worklet errors.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .. import diagnostics
from .compiler import WorkletError
from .shared import SharedValue
from .worklets import Encoder, closure_wire, encode_value, encoding, end_encoding, is_worklet

__all__ = ["MotionRuntime", "motion_message", "runtime"]


@dataclass(eq=False)
class Target:
    """One transport's core: what it already has and what's queued for it."""

    transport: Any
    surface: int
    generation: int
    programs: Set[int] = field(default_factory=set)
    shared: Set[int] = field(default_factory=set)
    bindings: Dict[int, str] = field(default_factory=dict)  # binding -> request last sent
    handlers: Dict[str, int] = field(default_factory=dict)  # closure -> handler binding
    handler_keys: Dict[int, str] = field(default_factory=dict)
    handler_refs: Counter[int] = field(default_factory=Counter)
    view_handlers: Dict[int, Dict[str, Tuple[int, ...]]] = field(default_factory=dict)
    pending: List[Dict[str, Any]] = field(default_factory=list)


_RETIRE_SECONDS = 30.0
"""How long a released ``run_on_python`` callback still answers calls already in flight."""


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False)


class MotionRuntime:
    """Install worklets and shared values on each transport's core."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Forget every target and pending request (the core was reset)."""
        self._targets: Dict[int, Target] = {}
        self._binding_ids = itertools.count(1)
        self._tokens = itertools.count(1)
        self._futures: Dict[int, asyncio.Future[bool]] = {}
        self._callbacks: Dict[int, Callable[..., Any]] = {}
        self._callback_refs: Counter[int] = Counter()
        # Callback ids by (target, binding), in the order a binding registers them.
        self._callback_slots: Dict[Tuple[int, int], List[int]] = {}
        self._callback_by_function: Dict[int, int] = {}
        self._callback_ids = itertools.count(1)
        self._binding_callbacks: Dict[Tuple[int, int], List[int]] = {}
        self._retired: Dict[int, float] = {}
        self._scheduled = False

    # -- targets ---------------------------------------------------------------

    def target(self, backend: Any) -> Optional[Target]:
        """The target for a bridge backend, or ``None`` when it has no motion-capable transport."""
        transport = getattr(backend, "transport", None)
        surface = getattr(backend, "surface", None)
        if transport is None or surface is None or not hasattr(transport, "motion"):
            return None
        return self._target_for(transport, int(surface))

    def _target_for(self, transport: Any, surface: int) -> Target:
        generation = int(getattr(transport, "motion_generation", 0))
        found = self._targets.get(id(transport))
        if found is None or found.transport is not transport or found.generation != generation:
            found = Target(transport, surface, generation)
            self._targets[id(transport)] = found
        return found

    def _live(self, target: Optional[Target]) -> Optional[Target]:
        if target is None:
            return None
        return self._target_for(target.transport, target.surface)

    def new_binding(self) -> int:
        """A fresh binding id."""
        return next(self._binding_ids)

    # -- requests --------------------------------------------------------------

    def queue(self, target: Target, request: Dict[str, Any]) -> None:
        """Queue a request for the target's next flush."""
        target.pending.append(request)
        self._schedule()

    def _schedule(self) -> None:
        if self._scheduled:
            return
        self._scheduled = True
        from ..runtime import get_loop

        try:
            get_loop().call_soon_threadsafe(self.flush_all)
        except RuntimeError:  # pragma: no cover - a closed loop at shutdown
            self._scheduled = False

    def flush_all(self) -> None:
        """Send every target's queued requests."""
        self._scheduled = False
        for target in list(self._targets.values()):
            self.flush(target)

    def flush_transport(self, transport: Any) -> None:
        """Send the requests queued for one transport (before its next commit)."""
        target = self._targets.get(id(transport))
        if target is not None and target.transport is transport:
            self.flush(target)

    def flush(self, target: Target) -> None:
        """Send the target's queued requests as one batch."""
        if not target.pending:
            return
        requests, target.pending = target.pending, []
        payload = requests[0] if len(requests) == 1 else {"op": "batch", "requests": requests}
        try:
            reply = target.transport.motion(target.surface, _dumps(payload))
        except Exception as exc:  # the transport died; the next generation reinstalls
            _report(WorkletError(f"couldn't send motion requests: {exc}"))
            return
        try:
            parsed = json.loads(reply) if reply else {"ok": True}
        except ValueError:
            parsed = {"ok": True}
        if isinstance(parsed, dict) and parsed.get("ok") is False:
            _report(WorkletError(str(parsed.get("error", "the renderer core rejected a motion request"))))

    def _install(self, target: Target, encoder: Encoder) -> None:
        for ident, program in encoder.programs.items():
            if ident not in target.programs:
                target.programs.add(ident)
                self.queue(target, {"op": "program", "id": ident, "program": program.document()})
        for shared in encoder.shared:
            self.ensure_shared(target, shared)

    def _encoder(self, slot: Optional[Tuple[int, int]] = None) -> Encoder:
        counter = itertools.count()

        def register(fn: Callable[..., Any]) -> int:
            if slot is not None:
                # Stable per binding and position, so a callback recreated on
                # every render doesn't reinstall the worklet.
                idents = self._callback_slots.setdefault(slot, [])
                position = next(counter)
                if position < len(idents):
                    ident = idents[position]
                else:
                    ident = next(self._callback_ids)
                    idents.append(ident)
            else:
                ident = self._callback_by_function.get(id(fn), 0)
                if self._callbacks.get(ident) is not fn:
                    ident = next(self._callback_ids)
                self._callback_by_function[id(fn)] = ident
            self._retired.pop(ident, None)
            self._callbacks[ident] = fn
            return ident

        return Encoder(register)

    def _settle_callbacks(self, key: Tuple[int, int], new: List[int]) -> None:
        old = self._binding_callbacks.pop(key, [])
        self._callback_refs.update(new)
        self._callback_refs.subtract(old)
        now = time.monotonic()
        for ident in old:
            if self._callback_refs[ident] <= 0:
                del self._callback_refs[ident]
                # A `call` the UI thread sent before it applied the release may
                # still be on its way, so the callback outlives its binding briefly.
                self._retired[ident] = now
        for ident, retired in list(self._retired.items()):
            if now - retired > _RETIRE_SECONDS and self._callback_refs[ident] <= 0:
                del self._retired[ident]
                fn = self._callbacks.pop(ident, None)
                if fn is not None and self._callback_by_function.get(id(fn)) == ident:
                    del self._callback_by_function[id(fn)]
        if new:
            self._binding_callbacks[key] = list(new)

    # -- shared values ---------------------------------------------------------

    def adopt(self, shared: SharedValue[Any], backend: Any) -> None:
        """Make ``backend``'s core the home of a shared value created in its render."""
        if shared._target is None:
            shared._target = self.target(backend)

    def ensure_shared(self, target: Target, shared: SharedValue[Any]) -> None:
        """Define a shared value on the target's core, once."""
        if shared._target is None:
            shared._target = target
        if shared.id in target.shared:
            return
        target.shared.add(shared.id)
        self.queue(target, {"op": "shared", "id": shared.id, "value": encode_value(shared._value)})

    def _home(self, shared: SharedValue[Any]) -> Optional[Target]:
        target = self._live(shared._target)
        if target is not None:
            shared._target = target
            self.ensure_shared(target, shared)
        return target

    def read(self, shared: SharedValue[Any]) -> Optional[str]:
        """The published value as JSON, or ``None`` when no core holds it."""
        target = self._home(shared)
        if target is None:
            return None
        self.flush(target)
        reader = getattr(target.transport, "shared_read", None)
        if reader is None:
            return None
        text = reader(shared.id)
        # "null" also means the UI thread hasn't applied the definition yet.
        return None if text in (None, "", "null") else str(text)

    def set(self, shared: SharedValue[Any], value: Any) -> None:
        """Queue a plain write (it cancels a running animation)."""
        target = self._home(shared)
        if target is not None:
            self.queue(target, {"op": "set", "id": shared.id, "value": encode_value(value)})

    def animate(self, shared: SharedValue[Any], animation: Any, token: Optional[int]) -> None:
        """Queue an animation; ``token`` asks the core to report when it settles."""
        target = self._home(shared)
        if target is None:
            final = getattr(animation, "to", None)
            if final is not None:
                shared._value = final
            if token is not None:
                self._finish(token, True)
            return
        encoder = self._encoder()
        scope = encoding(encoder)
        try:
            wire = animation.__pn_wire__()
        finally:
            end_encoding(scope)
        # An animation's `on_finish` callbacks live until the next animation of the same value.
        self._settle_callbacks((id(target), -shared.id), encoder.callbacks)
        self._install(target, encoder)
        request: Dict[str, Any] = {"op": "animate", "id": shared.id, "animation": wire}
        if token is not None:
            request["token"] = token
        self.queue(target, request)

    async def animate_awaitable(self, shared: SharedValue[Any], animation: Any) -> bool:
        """Run an animation and return whether it finished."""
        from ..runtime import get_loop

        token = next(self._tokens)
        future: asyncio.Future[bool] = get_loop().create_future()
        self._futures[token] = future
        self.animate(shared, animation, token)
        try:
            return await future
        except asyncio.CancelledError:
            self._futures.pop(token, None)
            self.cancel(shared)
            raise

    def cancel(self, shared: SharedValue[Any]) -> None:
        """Queue a cancel of a running animation."""
        target = self._home(shared)
        if target is not None:
            self.queue(target, {"op": "cancel", "id": shared.id})

    def release_shared(self, shared: SharedValue[Any]) -> None:
        """Forget a shared value in the core (its component unmounted)."""
        target = self._live(shared._target)
        if target is not None and shared.id in target.shared:
            target.shared.discard(shared.id)
            self.queue(target, {"op": "release", "shared": [shared.id]})

    # -- bindings --------------------------------------------------------------

    def bind(
        self,
        backend: Any,
        binding: int,
        kind: str,
        fn: Callable[..., Any],
        *,
        output: Optional[SharedValue[Any]] = None,
        react: Optional[Callable[..., Any]] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Install or update a derived value, reaction, frame callback, or animated style.

        Raises:
            WorkletError: When a worklet doesn't compile or captures something it can't use.
        """
        target = self.target(backend)
        if target is None:
            return
        encoder = self._encoder((id(target), binding))
        request: Dict[str, Any] = {
            "op": "bind",
            "id": binding,
            "kind": kind,
            "closure": closure_wire(fn, encoder=encoder),
        }
        if react is not None:
            request["react"] = closure_wire(react, encoder=encoder)
        if output is not None:
            encoder.shared.append(output)
            request["output"] = output.id
        if active is not None:
            request["active"] = bool(active)
        text = _dumps(request)
        self._settle_callbacks((id(target), binding), encoder.callbacks)
        if target.bindings.get(binding) == text:
            return
        self._install(target, encoder)
        target.bindings[binding] = text
        self.queue(target, request)

    def release_binding(self, backend: Any, binding: int) -> None:
        """Forget a binding in the core (its component unmounted)."""
        target = self.target(backend)
        if target is None or binding not in target.bindings:
            return
        del target.bindings[binding]
        self._callback_slots.pop((id(target), binding), None)
        self._settle_callbacks((id(target), binding), [])
        self.queue(target, {"op": "release", "bindings": [binding]})

    # -- event handlers and layout animation props ------------------------------

    def handler(self, backend: Any, fn: Callable[..., Any]) -> Optional[int]:
        """A handler binding for an event or gesture worklet, shared by every view using the same closure."""
        target = self.target(backend)
        if target is None:
            return None
        encoder = self._encoder()
        wire = closure_wire(fn, encoder=encoder)
        key = _dumps(wire)
        binding = target.handlers.get(key)
        if binding is None:
            binding = self.new_binding()
            target.handlers[key] = binding
            target.handler_keys[binding] = key
            self._install(target, encoder)
            self.queue(target, {"op": "bind", "id": binding, "kind": "handler", "closure": wire})
            self._settle_callbacks((id(target), binding), encoder.callbacks)
        return binding

    def retain_view(self, backend: Any, tag: int, source: str, bindings: Iterable[int]) -> None:
        """Record which handler bindings a view's ``source`` prop references (``_pn_motion`` or ``gestures``)."""
        target = self.target(backend)
        if target is None:
            return
        held = target.view_handlers.setdefault(tag, {})
        new = tuple(bindings)
        old = held.get(source, ())
        target.handler_refs.update(new)
        held[source] = new
        self._drop_handlers(target, old)

    def release_view(self, backend: Any, tag: int) -> None:
        """Drop a destroyed view's references to handler bindings."""
        target = self.target(backend)
        if target is None:
            return
        held = target.view_handlers.pop(tag, None)
        if held:
            for bindings in held.values():
                self._drop_handlers(target, bindings)

    def _drop_handlers(self, target: Target, bindings: Iterable[int]) -> None:
        released = []
        target.handler_refs.subtract(bindings)
        for binding in set(bindings):
            if target.handler_refs[binding] > 0:
                continue
            del target.handler_refs[binding]
            key = target.handler_keys.pop(binding, None)
            if key is not None:
                target.handlers.pop(key, None)
            self._settle_callbacks((id(target), binding), [])
            released.append(binding)
        if released:
            self.queue(target, {"op": "release", "bindings": sorted(released)})

    def prop_wire(self, backend: Any, value: Any) -> Any:
        """Encode an ``entering``, ``exiting``, ``layout``, or ``shared_transition`` value for the core."""
        if value is None:
            return None
        encoder = self._encoder()
        scope = encoding(encoder)
        try:
            if is_worklet(value) or (callable(value) and getattr(value, "__code__", None) is not None):
                from .worklets import require_worklet

                wire: Any = {"type": "custom", "worklet": closure_wire(require_worklet(value, "a layout animation"))}
            elif hasattr(value, "__pn_wire__"):
                wire = value.__pn_wire__()
            else:
                wire = value
        finally:
            end_encoding(scope)
        target = self.target(backend)
        if target is not None:
            self._install(target, encoder)
        return wire

    # -- messages ---------------------------------------------------------------

    def _finish(self, token: int, finished: bool) -> None:
        future = self._futures.pop(token, None)
        if future is not None and not future.done():
            from ..runtime import resolve_future

            resolve_future(future, finished)

    def message(self, payload: Dict[str, Any]) -> None:
        """Handle one ``motion`` message from the core."""
        kind = payload.get("type")
        if kind == "finished":
            self._finish(int(payload.get("token", 0)), bool(payload.get("finished")))
        elif kind == "call":
            callback = self._callbacks.get(int(payload.get("callback", 0)))
            if callback is None:
                return
            from ..runtime import invoke

            try:
                invoke(callback, *list(payload.get("args") or []))
            except Exception as exc:
                if not diagnostics.report_error(exc, phase="event"):
                    raise
        elif kind == "error":
            _report(
                WorkletError(
                    str(payload.get("message", "")),
                    str(payload.get("file", "")),
                    int(payload.get("line", 0) or 0),
                    error_type=str(payload.get("error_type", "")),
                )
            )


def _report(error: WorkletError) -> None:
    if not diagnostics.report_error(error, phase="worklet"):
        diagnostics.warn_once(str(error), key=f"worklet:{error}")


runtime = MotionRuntime()
"""The process's motion runtime."""


def motion_message(payload: Dict[str, Any]) -> None:
    """Handle one ``motion`` message from the core (the bridge's dispatch calls this)."""
    runtime.message(payload)
