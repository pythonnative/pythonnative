"""Platform-specific native-view creation and update logic.

This package provides the
[`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
that maps element type names (e.g., `"Text"`, `"Button"`) to
platform-specific
[`ViewHandler`][pythonnative.native_views.base.ViewHandler]
implementations. The reconciler calls the registry to create, update,
and re-parent native views.

Platform handlers live in dedicated submodules:

- `pythonnative.native_views.base`: shared `ViewHandler` protocol and
  utilities.
- `pythonnative.native_views.android`: Android handlers
  (Chaquopy / Java bridge).
- `pythonnative.native_views.ios`: iOS handlers (rubicon-objc).

All platform-branching is handled at registration time via lazy
imports, so this package can be imported on any platform for testing.
A mock registry can be installed via
[`set_registry`][pythonnative.native_views.set_registry] to drive the
reconciler with no real native views.
"""

import math
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

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


class NativeViewRegistry:
    """Map element type names to platform-specific view handlers.

    The reconciler depends only on this protocol:
    `create_view`, `update_view`, `add_child`, `remove_child`,
    `insert_child`, `set_frame`, `measure_intrinsic`. Implementations
    may be real (Android/iOS) or mocked for tests.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, ViewHandler] = {}

    def register(self, type_name: str, handler: ViewHandler) -> None:
        """Register `handler` to service elements of type `type_name`.

        Args:
            type_name: The element type name (e.g., `"Text"`).
            handler: A `ViewHandler` instance for the active platform.
        """
        self._handlers[type_name] = handler

    def create_view(self, type_name: str, props: Dict[str, Any]) -> Any:
        """Create a native view for `type_name` and apply initial props.

        Args:
            type_name: The element type name.
            props: Initial props dict.

        Returns:
            The platform-native view object.

        Raises:
            ValueError: If no handler is registered for `type_name`.
        """
        handler = self._handlers.get(type_name)
        if handler is None:
            raise ValueError(f"Unknown element type: {type_name!r}")
        return handler.create(props)

    def update_view(self, native_view: Any, type_name: str, changed_props: Dict[str, Any]) -> None:
        """Apply `changed_props` to an existing native view.

        Silently ignored if no handler is registered for `type_name`.

        Args:
            native_view: The platform-native view.
            type_name: The element type name.
            changed_props: A dict containing only props whose values
                changed since the previous render. Removed props are
                signaled with a value of `None`.
        """
        handler = self._handlers.get(type_name)
        if handler is not None:
            handler.update(native_view, changed_props)

    def add_child(self, parent: Any, child: Any, parent_type: str) -> None:
        """Append `child` to `parent`.

        Args:
            parent: Parent native view.
            child: Native view to append.
            parent_type: Element type of the parent (for handler lookup).
        """
        handler = self._handlers.get(parent_type)
        if handler is not None:
            handler.add_child(parent, child)

    def remove_child(self, parent: Any, child: Any, parent_type: str) -> None:
        """Remove `child` from `parent`.

        Args:
            parent: Parent native view.
            child: Child native view to remove.
            parent_type: Element type of the parent.
        """
        handler = self._handlers.get(parent_type)
        if handler is not None:
            handler.remove_child(parent, child)

    def insert_child(self, parent: Any, child: Any, parent_type: str, index: int) -> None:
        """Insert `child` into `parent` at `index`.

        Args:
            parent: Parent native view.
            child: Child native view to insert.
            parent_type: Element type of the parent.
            index: Zero-based insertion position among `parent`'s
                existing children.
        """
        handler = self._handlers.get(parent_type)
        if handler is not None:
            handler.insert_child(parent, child, index)

    def set_frame(
        self,
        native_view: Any,
        type_name: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """Position and size a native view via the appropriate handler.

        Called by the reconciler's layout pass after every commit, with
        coordinates computed by ``pythonnative.layout`` in points
        relative to the parent's content origin.
        """
        # Tripwire: log non-finite layout values so we can diagnose
        # crashes like iOS `CALayerInvalidGeometry` without losing the
        # repro. Handlers are responsible for clamping before applying.
        # Rate-limited via ``_tripwire_log`` to avoid 60 Hz floods when
        # an animated value is stuck at NaN.
        try:
            finite = math.isfinite(x) and math.isfinite(y) and math.isfinite(width) and math.isfinite(height)
        except (TypeError, ValueError):
            finite = False
        if not finite:
            _tripwire_log(
                "set_frame:nan",
                f"[set_frame:nan] type={type_name!r} " f"x={x!r} y={y!r} w={width!r} h={height!r}",
            )

        handler = self._handlers.get(type_name)
        if handler is not None:
            handler.set_frame(native_view, x, y, width, height)

    def measure_intrinsic(
        self,
        native_view: Any,
        type_name: str,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        """Return the natural ``(width, height)`` of a content-sized view.

        Used by the layout engine for leaves whose intrinsic size
        depends on their content (text, buttons, images).
        """
        handler = self._handlers.get(type_name)
        if handler is None:
            return (0.0, 0.0)
        return handler.measure_intrinsic(native_view, max_width, max_height)


# ======================================================================
# Singleton registry
# ======================================================================

_registry: Optional[NativeViewRegistry] = None


def _active_platform_name() -> str:
    """Return ``"android"``, ``"desktop"``, or ``"ios"`` for the active runtime."""
    from ..utils import IS_ANDROID, IS_DESKTOP

    if IS_ANDROID:
        return "android"
    if IS_DESKTOP:
        return "desktop"
    return "ios"


def _register_builtin_handlers(registry: NativeViewRegistry) -> None:
    """Register every built-in handler for the active platform.

    The desktop (Tkinter) backend is selected when ``pn preview`` sets
    ``PN_PLATFORM=desktop``; otherwise this picks Android (on device) or
    iOS (the default off-device path, exercised by the iOS templates and
    by tests that install the ``[ios]`` extra). Off-device unit tests
    typically inject a mock registry via ``set_registry`` instead.
    """
    from ..utils import IS_ANDROID, IS_DESKTOP

    if IS_ANDROID:
        from .android import register_handlers
    elif IS_DESKTOP:
        from .desktop import register_handlers
    else:
        from .ios import register_handlers
    register_handlers(registry)


def _install_sdk_handlers(registry: NativeViewRegistry) -> None:
    """Copy decorator-registered SDK handlers + entry-point plugins.

    Imported lazily so unit tests that never touch the SDK don't pay the
    entry-point discovery cost.
    """
    try:
        from ..sdk._components import install_into_registry as _sdk_install
    except Exception:
        return
    try:
        _sdk_install(registry, _active_platform_name())
    except Exception:
        # A misbehaving plugin must not break PythonNative's startup.
        pass


def get_registry() -> NativeViewRegistry:
    """Return the process-wide registry, lazily registering handlers.

    The first call instantiates the registry, registers either the
    Android or iOS handlers based on `IS_ANDROID`, then layers on every
    decorator-registered SDK handler (and any handlers exposed by
    third-party packages via the
    [`pythonnative.handlers`][pythonnative.sdk.ENTRY_POINT_GROUP] entry
    point group). Subsequent calls return the same instance.

    Returns:
        The active `NativeViewRegistry`.
    """
    global _registry
    if _registry is not None:
        return _registry
    _registry = NativeViewRegistry()
    _register_builtin_handlers(_registry)
    _install_sdk_handlers(_registry)
    return _registry


def refresh_registry() -> NativeViewRegistry:
    """Re-run SDK handler installation against the existing registry.

    Call this after registering a new component at runtime if the
    registry has already been instantiated. This is mostly useful in
    REPL sessions and tests; the normal flow is "register, then call
    [`get_registry`][pythonnative.native_views.get_registry]" and the
    handlers come along automatically.

    Returns:
        The active `NativeViewRegistry`.
    """
    registry = get_registry()
    _install_sdk_handlers(registry)
    return registry


def set_registry(registry: Optional[NativeViewRegistry]) -> None:
    """Install a custom registry (primarily for testing).

    Replaces the lazy singleton so subsequent
    [`get_registry`][pythonnative.native_views.get_registry] calls
    return `registry`. Pass a mock to drive the reconciler from
    unit tests without touching real native APIs. Pass ``None`` to
    reset the singleton; the next ``get_registry`` call will then
    rebuild it from scratch.

    Args:
        registry: The replacement registry, or ``None`` to clear.
    """
    global _registry
    _registry = registry
