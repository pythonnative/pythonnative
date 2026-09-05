"""The view backend the reconciler commits to.

The reconciler talks to exactly one object, obtained from
[`get_registry`][pythonnative.native_views.get_registry], through a
small protocol: ``apply_mutations`` (one ordered batch of
create/update/insert/destroy/frame ops per commit, see
`pythonnative.mutations`), ``resolve_view``, ``measure_intrinsic``,
``command``, and the animation hooks. Two implementations exist:

- [`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
  (iOS, Android, and the browser preview): serializes each commit and
  hands it to the native runtime through the bridge; the Swift and
  Kotlin component managers, or the preview page's DOM applier, own
  every platform view. Python holds no native objects.
- [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
  (tests and SDK handler introspection): maps element type names to
  Python [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
  implementations and owns the tag table itself.

Platform selection happens lazily on first use, so this package
imports on any platform. Tests install a mock with
[`set_registry`][pythonnative.native_views.set_registry].
"""

import math
import sys
import threading
import time
from typing import Any, Dict, Optional, Sequence, Tuple

from ..mutations import CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp
from .base import ViewHandler

# ======================================================================
# Tripwire log rate limiter
# ======================================================================
#
# Defensive NaN/Inf guards in ``set_frame`` and ``_apply_transform`` log
# a single line per occurrence. That's fine for one-off events, but
# ``Animated.View`` drives transforms at ~60 Hz; once an
# ``Animated.Value`` enters a stuck NaN state (e.g., a spring tick
# corrupted across a Fast Refresh), the tripwire would otherwise emit
# thousands of identical lines per second and drown the dev console.
#
# We instead log the first occurrence immediately, then suppress
# further messages with the same ``label`` for
# ``_TRIPWIRE_RATE_LIMIT_S`` seconds, and append a
# ``(+N similar in last Xs)`` suffix to the next message that escapes
# the window. The first sample plus a count is enough to diagnose; the
# bounded log keeps the dev console usable.

_TRIPWIRE_RATE_LIMIT_S: float = 1.0
_TRIPWIRE_LOG_LOCK = threading.Lock()
_TRIPWIRE_LAST_LOG_TIME: Dict[str, float] = {}
_TRIPWIRE_SUPPRESSED_COUNT: Dict[str, int] = {}


def _tripwire_log(label: str, message: str) -> None:
    """Emit ``message`` to stderr, rate-limited per ``label``.

    The first call for a given ``label`` always emits. Calls within
    ``_TRIPWIRE_RATE_LIMIT_S`` seconds are silently counted. The next
    call after the window appends ``(+N similar in last Xs)`` and
    resets the counter.
    """
    now = time.monotonic()
    write = False
    suppressed = 0
    with _TRIPWIRE_LOG_LOCK:
        last = _TRIPWIRE_LAST_LOG_TIME.get(label)
        if last is None or now - last >= _TRIPWIRE_RATE_LIMIT_S:
            write = True
            suppressed = _TRIPWIRE_SUPPRESSED_COUNT.get(label, 0)
            _TRIPWIRE_SUPPRESSED_COUNT[label] = 0
            _TRIPWIRE_LAST_LOG_TIME[label] = now
        else:
            _TRIPWIRE_SUPPRESSED_COUNT[label] = _TRIPWIRE_SUPPRESSED_COUNT.get(label, 0) + 1
    if not write:
        return
    if suppressed > 0:
        message = f"{message} (+{suppressed} similar in last {_TRIPWIRE_RATE_LIMIT_S:g}s)"
    try:
        print(message, file=sys.stderr, flush=True)
    except Exception:
        pass


class ViewRecord:
    """One live native view tracked by the tag table."""

    __slots__ = ("tag", "type_name", "view", "handler")

    def __init__(self, tag: int, type_name: str, view: Any, handler: ViewHandler) -> None:
        self.tag = tag
        self.type_name = type_name
        self.view = view
        self.handler = handler


class NativeViewRegistry:
    """Map element type names to handlers and tags to live native views.

    The reconciler depends only on this protocol: ``apply_mutations``,
    ``resolve_view``, ``measure_intrinsic``, and ``command``.
    Implementations may host real platform handlers (Android/iOS/
    browser) or mocks for tests.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, ViewHandler] = {}
        self._records: Dict[int, ViewRecord] = {}

    def register(self, type_name: str, handler: ViewHandler) -> None:
        """Register `handler` to service elements of type `type_name`.

        Args:
            type_name: The element type name (e.g., `"Text"`).
            handler: A `ViewHandler` instance for the active platform.
        """
        self._handlers[type_name] = handler

    def handler_for(self, type_name: str) -> Optional[ViewHandler]:
        """Return the handler registered for ``type_name``, if any."""
        return self._handlers.get(type_name)

    # ------------------------------------------------------------------
    # Tag table
    # ------------------------------------------------------------------

    def resolve_view(self, tag: int) -> Any:
        """Return the native view registered under ``tag``, or ``None``."""
        record = self._records.get(tag)
        return record.view if record is not None else None

    def record_for(self, tag: int) -> Optional[ViewRecord]:
        """Return the full [`ViewRecord`][pythonnative.native_views.ViewRecord] for ``tag``."""
        return self._records.get(tag)

    def live_view_count(self) -> int:
        """Number of views currently tracked (test/diagnostic helper)."""
        return len(self._records)

    # ------------------------------------------------------------------
    # The commit channel
    # ------------------------------------------------------------------

    def apply_mutations(self, ops: Sequence[Mutation]) -> None:
        """Apply one commit transaction.

        Ops are applied strictly in order. Failures are isolated per
        op: a handler exception is logged (rate-limited) and the
        remaining ops still apply, so one bad prop can't desync the
        whole native tree.

        Args:
            ops: Ordered mutations emitted by the reconciler.
        """
        for op in ops:
            try:
                self._apply_one(op)
            except Exception as exc:
                _tripwire_log(
                    f"apply:{type(op).__name__}",
                    f"[PN] apply_mutations: {type(op).__name__} failed: {type(exc).__name__}: {exc!r}",
                )

    def _apply_one(self, op: Mutation) -> None:
        if isinstance(op, CreateOp):
            handler = self._handlers.get(op.type_name)
            if handler is None:
                raise ValueError(f"Unknown element type: {op.type_name!r}")
            view = handler.create(op.tag, op.props)
            self._records[op.tag] = ViewRecord(op.tag, op.type_name, view, handler)
            return
        if isinstance(op, UpdateOp):
            record = self._records.get(op.tag)
            if record is not None:
                record.handler.update(record.view, op.changed_props)
            return
        if isinstance(op, InsertOp):
            parent = self._records.get(op.parent_tag)
            child = self._records.get(op.child_tag)
            if parent is not None and child is not None:
                parent.handler.insert_child(parent.view, child.view, op.index)
            return
        if isinstance(op, DestroyOp):
            record = self._records.pop(op.tag, None)
            if record is not None:
                record.handler.destroy(record.view)
            return
        if isinstance(op, SetFrameOp):
            self._apply_frame(op)
            return
        raise TypeError(f"Unknown mutation op: {op!r}")

    def _apply_frame(self, op: SetFrameOp) -> None:
        record = self._records.get(op.tag)
        if record is None:
            return
        # Tripwire: log non-finite layout values so we can diagnose
        # crashes like iOS `CALayerInvalidGeometry` without losing the
        # repro. Handlers are responsible for clamping before applying.
        # Rate-limited via ``_tripwire_log`` to avoid floods when an
        # animated value is stuck at NaN.
        try:
            finite = (
                math.isfinite(op.x) and math.isfinite(op.y) and math.isfinite(op.width) and math.isfinite(op.height)
            )
        except (TypeError, ValueError):
            finite = False
        if not finite:
            _tripwire_log(
                "set_frame:nan",
                f"[set_frame:nan] type={record.type_name!r} x={op.x!r} y={op.y!r} w={op.width!r} h={op.height!r}",
            )
        record.handler.set_frame(record.view, op.x, op.y, op.width, op.height)

    # ------------------------------------------------------------------
    # Imperative escape hatches (resolved through the tag table)
    # ------------------------------------------------------------------

    def measure_intrinsic(
        self,
        tag: int,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        """Return the natural ``(width, height)`` of a content-sized view.

        Used by the layout engine for leaves whose intrinsic size
        depends on their content (text, buttons, images).
        """
        record = self._records.get(tag)
        if record is None:
            return (0.0, 0.0)
        return record.handler.measure_intrinsic(record.view, max_width, max_height)

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Execute an imperative command against the view for ``tag``.

        Args:
            tag: Target view tag.
            name: Command name (handler-specific, e.g.
                ``"scroll_to_offset"``).
            args: Optional command arguments.

        Returns:
            The handler's command result, or ``None`` when the tag is
            unknown.
        """
        record = self._records.get(tag)
        if record is None:
            return None
        return record.handler.command(record.view, name, args or {})

    def set_animated_property(self, tag: int, prop_name: str, value: Any) -> None:
        """Apply one Python-driven animation frame to the view for ``tag``."""
        record = self._records.get(tag)
        if record is not None:
            record.handler.set_animated_property(record.view, prop_name, value)

    def start_animation(self, tag: int, anim_id: int, prop_name: str, spec: Dict[str, Any]) -> bool:
        """Start a natively-driven animation on the view for ``tag``.

        Returns:
            Whether the platform accepted the animation (``False``
            means the caller should drive it from the Python ticker).
        """
        record = self._records.get(tag)
        if record is None:
            return False
        return bool(record.handler.start_animation(record.view, anim_id, prop_name, spec))

    def cancel_animation(self, tag: int, anim_id: int) -> Any:
        """Cancel a natively-driven animation; returns the presentation value if known."""
        record = self._records.get(tag)
        if record is None:
            return None
        return record.handler.cancel_animation(record.view, anim_id)


# ======================================================================
# Singleton registry
# ======================================================================

_registry: Any = None


def _install_sdk_handlers(registry: Any) -> None:
    """Copy decorator-registered SDK handlers + entry-point plugins.

    Imported lazily so unit tests that never touch the SDK don't pay the
    entry-point discovery cost. Only meaningful for the Python-handler
    registry (tests); on the bridge platforms the native runtime owns
    component managers and Python handlers are recorded but never run.
    """
    try:
        from ..sdk._components import install_into_registry as _sdk_install
    except Exception:
        return
    try:
        _sdk_install(registry)
    except Exception:
        # A misbehaving plugin must not break PythonNative's startup.
        pass


def _create_backend() -> Any:
    """Build the backend for the active platform.

    iOS, Android, and the browser preview (``PN_PLATFORM=web``) get the
    bridge backend. Anywhere else (plain unit tests) there is no
    renderer at all, so the registry is empty: tests inject a
    ``pythonnative.testing.FakeBackend`` with ``set_registry`` and a
    stray commit raises a clear "unknown element type" rather than
    silently importing a platform module.
    """
    from ..utils import IS_NATIVE

    if IS_NATIVE:
        from .bridge_backend import BridgeBackend

        return BridgeBackend()
    registry = NativeViewRegistry()
    _install_sdk_handlers(registry)
    return registry


def get_registry() -> Any:
    """Return the process-wide view backend, creating it on first use.

    Returns:
        A [`BridgeBackend`][pythonnative.native_views.bridge_backend.BridgeBackend]
        on every bridge platform, otherwise a `NativeViewRegistry`
        holding every decorator-registered SDK handler and any handlers
        exposed by third-party packages via the
        [`pythonnative.handlers`][pythonnative.sdk.ENTRY_POINT_GROUP]
        entry point group.
    """
    global _registry
    if _registry is not None:
        return _registry
    _registry = _create_backend()
    return _registry


def refresh_registry() -> Any:
    """Re-run SDK handler installation against the existing backend.

    Call this after registering a new component at runtime if the
    registry has already been instantiated. This is mostly useful in
    REPL sessions and tests; the normal flow is "register, then call
    [`get_registry`][pythonnative.native_views.get_registry]" and the
    handlers come along automatically.
    """
    registry = get_registry()
    _install_sdk_handlers(registry)
    return registry


def set_registry(registry: Any) -> None:
    """Install a custom backend (primarily for testing).

    Replaces the lazy singleton so subsequent
    [`get_registry`][pythonnative.native_views.get_registry] calls
    return `registry`. Pass a mock to drive the reconciler from
    unit tests without touching real native APIs. Pass ``None`` to
    reset the singleton; the next ``get_registry`` call will then
    rebuild it from scratch.

    Args:
        registry: The replacement backend, or ``None`` to clear.
    """
    global _registry
    _registry = registry
