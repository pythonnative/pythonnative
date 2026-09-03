"""Native module registry: name -> callable module, on device or off.

A *native module* is a named bag of methods implemented in Swift and
Kotlin (``Camera``, ``Storage``, ``Haptics``, ...). Python facades in
this package never touch platform APIs; they obtain a
[`NativeModule`][pythonnative.native_modules.registry.NativeModule]
through [`native_module`][pythonnative.native_modules.registry.native_module]
and call methods on it:

```python
_clipboard = native_module("Clipboard")
_clipboard.call("set_string", text="hello")
text = _clipboard.call("get_string")
result = await _camera.call_async("take_photo")
```

On device the module is a
[`BridgeModule`][pythonnative.native_modules.registry.BridgeModule]
that speaks the ``call(module, method, args_json)`` protocol described
in ``docs/concepts/bridge.md``. Off device (tests, ``pn preview``) the
same name resolves to a
[`PythonModule`][pythonnative.native_modules.registry.PythonModule]
wrapping a plain Python object with the same method names; the
built-in fallbacks live in ``pythonnative.native_modules.desktop`` and
third-party packages register theirs through the
``pythonnative.modules`` entry point group or
[`register_python_module`][pythonnative.native_modules.registry.register_python_module].

Modules can also push events (``AppState`` changes, deep links,
battery updates). Facades subscribe with
[`NativeModule.add_listener`][pythonnative.native_modules.registry.NativeModule.add_listener];
native delivers through
[`dispatch_module_message`][pythonnative.native_modules.registry.dispatch_module_message]
and Python implementations through
[`emit`][pythonnative.native_modules.registry.emit].
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import threading
from typing import Any, Callable, Dict, List, Optional

from ..bridge import codec

__all__ = [
    "ENTRY_POINT_GROUP",
    "BridgeModule",
    "NativeModule",
    "NativeModuleError",
    "PythonModule",
    "dispatch_module_message",
    "emit",
    "native_module",
    "on_event",
    "register_python_module",
    "unregister_python_module",
]

ENTRY_POINT_GROUP = "pythonnative.modules"
"""Entry-point group for Python (desktop / test) implementations of native modules."""

Listener = Callable[[Any], None]


class NativeModuleError(RuntimeError):
    """A native module method failed.

    Attributes:
        module: Module name.
        method: Method name.
        code: Optional machine-readable code supplied by native.
    """

    def __init__(self, module: str, method: str, message: str, code: Optional[str] = None) -> None:
        super().__init__(f"{module}.{method}: {message}")
        self.module = module
        self.method = method
        self.message = message
        self.code = code


class NativeModule:
    """Common surface of bridge-backed and Python-backed modules."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self._listeners: Dict[str, List[Listener]] = {}
        self._lock = threading.Lock()

    def call(self, method: str, **args: Any) -> Any:
        """Invoke ``method`` synchronously and return its value.

        Raises:
            NativeModuleError: When the native side reports a failure.
            RuntimeError: When the method only completes asynchronously
                (use [`call_async`][pythonnative.native_modules.registry.NativeModule.call_async]).
        """
        raise NotImplementedError

    async def call_async(self, method: str, **args: Any) -> Any:
        """Invoke ``method`` and await its result."""
        raise NotImplementedError

    def add_listener(self, event: str, callback: Listener) -> Callable[[], None]:
        """Subscribe to ``event``; returns an unsubscribe callable."""
        with self._lock:
            self._listeners.setdefault(event, []).append(callback)

        def _remove() -> None:
            with self._lock:
                bucket = self._listeners.get(event)
                if bucket is None:
                    return
                try:
                    bucket.remove(callback)
                except ValueError:
                    pass
                if not bucket:
                    self._listeners.pop(event, None)

        return _remove

    def listener_count(self, event: Optional[str] = None) -> int:
        """Number of listeners for ``event`` (or for every event when ``None``)."""
        with self._lock:
            if event is None:
                return sum(len(b) for b in self._listeners.values())
            return len(self._listeners.get(event, ()))

    def _deliver(self, event: str, payload: Any) -> None:
        with self._lock:
            callbacks = list(self._listeners.get(event, ()))
        for callback in callbacks:
            try:
                callback(payload)
            except Exception:
                from .. import diagnostics

                diagnostics.swallowed(f"native_modules.{self.name}.{event}")


# ======================================================================
# Bridge-backed modules (device)
# ======================================================================

_call_ids = itertools.count(1)
_pending: Dict[int, "asyncio.Future[Any]"] = {}
_pending_meta: Dict[int, tuple] = {}
_pending_lock = threading.Lock()


class BridgeModule(NativeModule):
    """A module implemented natively; every call crosses the bridge once."""

    def __init__(self, name: str, transport: Any = None) -> None:
        super().__init__(name)
        self._transport = transport

    @property
    def transport(self) -> Any:
        """The transport in use (resolved lazily on first access)."""
        if self._transport is None:
            from ..bridge import get_transport

            self._transport = get_transport()
        return self._transport

    def _invoke(self, method: str, args: Dict[str, Any], call_id: int) -> Any:
        envelope = codec.dumps({"call_id": call_id, "args": codec.to_jsonable(args)})
        raw = self.transport.call(self.name, method, envelope)
        result = codec.loads(raw)
        if result is None:
            return {"ok": True, "value": None}
        if not isinstance(result, dict):
            return {"ok": True, "value": result}
        return result

    def call(self, method: str, **args: Any) -> Any:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        result = self._invoke(method, args, 0)
        if result.get("pending"):
            raise RuntimeError(f"{self.name}.{method} completes asynchronously; use call_async()")
        if result.get("ok", True):
            return result.get("value")
        raise NativeModuleError(self.name, method, str(result.get("error", "unknown error")), result.get("code"))

    async def call_async(self, method: str, **args: Any) -> Any:
        """Invoke ``method`` and await its result."""
        loop = asyncio.get_running_loop()
        call_id = next(_call_ids)
        future: asyncio.Future[Any] = loop.create_future()
        with _pending_lock:
            _pending[call_id] = future
            _pending_meta[call_id] = (self.name, method)
        try:
            result = self._invoke(method, args, call_id)
        except Exception:
            with _pending_lock:
                _pending.pop(call_id, None)
                _pending_meta.pop(call_id, None)
            raise
        if not result.get("pending"):
            with _pending_lock:
                _pending.pop(call_id, None)
                _pending_meta.pop(call_id, None)
            if result.get("ok", True):
                return result.get("value")
            raise NativeModuleError(self.name, method, str(result.get("error", "unknown error")), result.get("code"))
        return await future


def _settle(call_id: int, message: Dict[str, Any]) -> None:
    with _pending_lock:
        future = _pending.pop(call_id, None)
        meta = _pending_meta.pop(call_id, ("?", "?"))
    if future is None:
        return
    from ..runtime import reject_future, resolve_future

    if message.get("ok", True):
        resolve_future(future, message.get("value"))
    else:
        module, method = meta
        reject_future(
            future, NativeModuleError(module, method, str(message.get("error", "unknown error")), message.get("code"))
        )


# ======================================================================
# Python-backed modules (desktop / tests)
# ======================================================================


class PythonModule(NativeModule):
    """A module implemented by a plain Python object.

    Methods are looked up by name on ``impl``; keyword arguments are
    forwarded. A method may be a coroutine function (or return an
    awaitable), in which case ``call`` raises and ``call_async`` awaits
    it. The implementation can push events with
    [`emit`][pythonnative.native_modules.registry.emit].
    """

    def __init__(self, name: str, impl: Any = None) -> None:
        super().__init__(name)
        self._impl = impl

    @property
    def impl(self) -> Any:
        """The implementation object, resolved on first use.

        Facades call ``native_module()`` at import time, so resolution is
        deferred until the first method call; by then the package's
        desktop implementation (or entry point) has had a chance to
        register.

        Raises:
            KeyError: If no implementation is registered for the module.
        """
        if self._impl is None:
            self._impl = _resolve_python_impl(self.name)
        return self._impl

    def _method(self, method: str) -> Callable[..., Any]:
        fn = getattr(self.impl, method, None)
        if fn is None or not callable(fn):
            raise NativeModuleError(self.name, method, "unknown method", code="unknown_method")
        return fn

    def call(self, method: str, **args: Any) -> Any:
        """Call a native module method with a ``{"call_id", "args"}`` envelope."""
        fn = self._method(method)
        if inspect.iscoroutinefunction(fn):
            raise RuntimeError(f"{self.name}.{method} is asynchronous; use call_async()")
        try:
            value = fn(**args)
        except NativeModuleError:
            raise
        except Exception as exc:
            raise NativeModuleError(self.name, method, str(exc)) from exc
        if inspect.isawaitable(value):
            raise RuntimeError(f"{self.name}.{method} returned an awaitable; use call_async()")
        return value

    async def call_async(self, method: str, **args: Any) -> Any:
        """Invoke ``method`` and await its result."""
        fn = self._method(method)
        try:
            value = fn(**args)
            if inspect.isawaitable(value):
                value = await value
        except NativeModuleError:
            raise
        except Exception as exc:
            raise NativeModuleError(self.name, method, str(exc)) from exc
        return value


# ======================================================================
# Registry
# ======================================================================

_modules: Dict[str, NativeModule] = {}
_python_impls: Dict[str, Any] = {}
_registry_lock = threading.Lock()
_discovered = False


def register_python_module(name: str, impl: Any) -> None:
    """Register ``impl`` as the off-device implementation of module ``name``.

    ``impl`` is an object (or a zero-arg factory returning one) whose
    methods match the module's method names. Registering replaces any
    earlier implementation and invalidates the cached module so the
    next [`native_module`][pythonnative.native_modules.registry.native_module]
    call picks it up.
    """
    with _registry_lock:
        _python_impls[name] = impl
        _modules.pop(name, None)


def unregister_python_module(name: str) -> None:
    """Remove a Python implementation registered for ``name`` (tests)."""
    with _registry_lock:
        _python_impls.pop(name, None)
        _modules.pop(name, None)


def native_module(name: str) -> NativeModule:
    """Return the module registered under ``name`` for the current platform.

    On iOS and Android this is always a
    [`BridgeModule`][pythonnative.native_modules.registry.BridgeModule];
    the native runtime decides whether the module exists when a method
    is first called. Elsewhere it is the registered
    [`PythonModule`][pythonnative.native_modules.registry.PythonModule].

    Off device the implementation is resolved lazily, on the first
    method call, so facades can call this at import time; a missing
    implementation surfaces then as ``KeyError``.
    """
    module = _modules.get(name)
    if module is not None:
        return module
    with _registry_lock:
        module = _modules.get(name)
        if module is not None:
            return module
        module = _create(name)
        _modules[name] = module
        return module


def _create(name: str) -> NativeModule:
    from ..bridge import has_transport

    if has_transport():
        return BridgeModule(name)
    return PythonModule(name)


def _resolve_python_impl(name: str) -> Any:
    _discover_entry_points()
    with _registry_lock:
        impl = _python_impls.get(name)
    if impl is None:
        from . import desktop

        impl = desktop.default_implementation(name)
    if impl is None:
        raise KeyError(
            f"No native module named {name!r} is available off device; register one with register_python_module()"
        )
    if inspect.isclass(impl) or inspect.isfunction(impl):
        impl = impl()
    return impl


def _discover_entry_points() -> None:
    global _discovered
    if _discovered:
        return
    _discovered = True
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return
    try:
        eps = entry_points()
    except Exception:  # pragma: no cover
        return
    selected: List[Any] = []
    if hasattr(eps, "select"):
        try:
            selected = list(eps.select(group=ENTRY_POINT_GROUP))
        except Exception:
            selected = []
    if not selected:
        getter = getattr(eps, "get", None)
        if getter is not None:
            try:
                selected = list(getter(ENTRY_POINT_GROUP, []))
            except Exception:
                selected = []
    for ep in selected:
        try:
            loaded = ep.load()
        except Exception as exc:  # pragma: no cover - defensive
            import sys

            print(
                f"[pythonnative.native_modules] Failed to load module entry point {ep.name!r}: {exc!r}", file=sys.stderr
            )
            continue
        module_name = getattr(loaded, "name", None) or ep.name
        if inspect.isfunction(loaded):
            try:
                loaded()
            except Exception as exc:  # pragma: no cover - defensive
                import sys

                print(f"[pythonnative.native_modules] entry point {ep.name!r} raised: {exc!r}", file=sys.stderr)
            continue
        _python_impls.setdefault(str(module_name), loaded)


# ======================================================================
# Inbound messages and events
# ======================================================================


def dispatch_module_message(module: str, message: Dict[str, Any]) -> None:
    """Route a native ``callback("module", ...)`` payload.

    ``{"call_id": n, "ok": ..., "value"|"error": ...}`` settles a
    pending ``call_async``; ``{"event": name, "payload": ...}`` fans
    out to listeners.
    """
    if not isinstance(message, dict):
        return
    if "call_id" in message:
        try:
            _settle(int(message["call_id"]), message)
        except (TypeError, ValueError):
            pass
        return
    event = message.get("event")
    if event:
        emit(module, str(event), message.get("payload"))


_hooks: Dict[tuple, List[Listener]] = {}


def on_event(module: str, event: str, callback: Listener) -> Callable[[], None]:
    """Subscribe to ``module``/``event`` without resolving the module.

    Facades use this at import time to route native pushes (``AppState``
    ``change``, ``Linking`` ``url``, ...) into their own listener lists.
    Unlike [`NativeModule.add_listener`][pythonnative.native_modules.registry.NativeModule.add_listener]
    the subscription survives module re-creation and never touches the
    platform. Returns an unsubscribe callable.
    """
    key = (module, event)
    with _registry_lock:
        _hooks.setdefault(key, []).append(callback)

    def _remove() -> None:
        with _registry_lock:
            bucket = _hooks.get(key)
            if bucket and callback in bucket:
                bucket.remove(callback)

    return _remove


def emit(module: str, event: str, payload: Any = None) -> None:
    """Deliver ``event`` to every listener of ``module`` (any platform).

    Python implementations use this to behave like their native
    counterparts (a test can emit ``AppState`` ``change`` events, for
    example).
    """
    with _registry_lock:
        hooks = list(_hooks.get((module, event), ()))
    for hook in hooks:
        try:
            hook(payload)
        except Exception:
            from .. import diagnostics

            diagnostics.swallowed(f"native_modules.{module}.{event}")
    target = _modules.get(module)
    if target is not None:
        target._deliver(event, payload)


def _reset_for_tests() -> None:
    """Forget cached modules and pending calls (test isolation)."""
    global _discovered
    with _registry_lock:
        _modules.clear()
        _python_impls.clear()
        _discovered = False
    with _pending_lock:
        _pending.clear()
        _pending_meta.clear()
