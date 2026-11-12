"""Developer diagnostics: dev mode, warnings, and error reporting.

PythonNative distinguishes **dev mode** (the `pn preview` window, `pn
run` with hot reload, or any process with ``PN_DEV=1``) from production.
Dev mode turns on:

- **Validation warnings** ([`warn`][pythonnative.diagnostics.warn] /
  [`warn_once`][pythonnative.diagnostics.warn_once]): unknown style
  keys, duplicate list keys, and similar mistakes are printed once with
  a suggestion instead of failing silently.
- **Hook-order checking**: calling hooks conditionally corrupts slot
  state; in dev mode the mismatch raises a
  [`HookOrderError`][pythonnative.diagnostics.HookOrderError]
  immediately instead of cross-wiring state.
- **The RedBox**: uncaught errors from render, effects, and event
  handlers are routed to the screen host, which presents a full-screen
  error overlay (see `pythonnative.hosts`) instead of crashing or
  swallowing the traceback.

In production none of this runs: validation is skipped, hook-order
checks are skipped, and errors propagate exactly as raised.

The **startup timeline** runs in every build: each launch logs one
``[PN] startup:`` line, and
[`startup_timeline`][pythonnative.diagnostics.startup_timeline] returns
the same phases.

This module has no dependencies on the rest of PythonNative, so any
module (hooks, reconciler, events) may import it freely.
"""

import os
import sys
import threading
import time
import traceback
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

__all__ = [
    "HookOrderError",
    "reset_dev_mode",
    "set_dev_mode",
    "is_dev",
    "log",
    "warn",
    "warn_once",
    "swallowed",
    "get_warnings",
    "clear_warnings",
    "set_error_reporter",
    "handle_error",
    "report_error",
    "set_error_handler",
    "add_listener",
    "STARTUP_PHASES",
    "begin_startup",
    "mark_startup",
    "startup_summary",
    "startup_timeline",
]


class HookOrderError(RuntimeError):
    """Raised in dev mode when hooks are called in a different order than the previous render.

    Hooks map to state slots by call order, so calling them inside
    conditionals or loops (or returning early between hook calls)
    silently cross-wires state in production. Dev mode detects the
    mismatch and raises this error with the offending component and
    slot so the bug is caught at the source.
    """


# ======================================================================
# Dev mode
# ======================================================================


def _environment_dev_mode() -> bool:
    return os.environ.get("PN_DEV", "").lower() in {"1", "true", "yes", "on"}


# Read on every render path, so it's a plain module global: the ``PN_DEV``
# environment variable seeds it at import and ``set_dev_mode`` overrides it.
_dev_mode: bool = _environment_dev_mode()


def set_dev_mode(enabled: bool) -> None:
    """Explicitly enable or disable dev mode for this process.

    Called automatically by ``pn preview`` and by the screen host's
    ``enable_hot_reload`` (which the device templates invoke on debug
    builds). An explicit call wins over the ``PN_DEV`` environment
    variable.

    Args:
        enabled: ``True`` to turn on dev diagnostics.
    """
    global _dev_mode
    _dev_mode = bool(enabled)


def reset_dev_mode() -> None:
    """Return to the mode the ``PN_DEV`` environment variable selects."""
    global _dev_mode
    _dev_mode = _environment_dev_mode()


def is_dev() -> bool:
    """Return whether dev diagnostics are active.

    An explicit [`set_dev_mode`][pythonnative.diagnostics.set_dev_mode]
    call wins; otherwise the ``PN_DEV`` environment variable, read when
    this module is imported, decides (default ``False``).
    """
    return _dev_mode


# ======================================================================
# Trace logging
# ======================================================================


def log(message: str) -> None:
    """Print a framework trace line (``[PN] message``) in dev mode.

    The reconciler and screen hosts call this at phase boundaries
    (mount, re-render, RedBox) so a dev console shows what the runtime
    is doing. No-op in production.

    Args:
        message: The trace text.
    """
    if not is_dev():
        return
    try:
        print(f"[PN] {message}", flush=True)
    except Exception:
        pass


# ======================================================================
# Startup timeline
# ======================================================================

STARTUP_PHASES = ("framework", "contracts", "bridge", "app", "render", "commit")
"""The startup phases, in launch order (see [`startup_timeline`][pythonnative.diagnostics.startup_timeline])."""

_startup_origin: Optional[float] = None
_startup_last: Optional[float] = None
_startup: Dict[str, float] = {}


def begin_startup(origin: float) -> None:
    """Set the ``time.perf_counter()`` value the ``framework`` phase starts from.

    ``pythonnative/__init__.py`` calls this with the time it started
    executing, before it records the ``framework`` mark.
    """
    global _startup_origin, _startup_last
    if _startup_origin is None:
        _startup_origin = _startup_last = origin


def mark_startup(phase: str, since: Optional[float] = None) -> None:
    """Record that startup ``phase`` finished now; only the first mark of each phase counts.

    Args:
        phase: One of [`STARTUP_PHASES`][pythonnative.diagnostics.STARTUP_PHASES].
        since: The ``time.perf_counter()`` value the phase started at.
            Defaults to the previous mark, so the phases a launch records
            in order cover it without gaps. ``render`` passes the time the
            first mount started, so the wait for the native screen isn't
            counted.

    ``commit`` counts only once ``render`` is recorded. When it is, the
    timeline is complete: it's reported through the profiling gauges
    (``startup.<phase>_ms``) and, after a launch through
    ``pythonnative.bootstrap``, logged as one ``[PN] startup:`` line, in
    release builds too.
    """
    global _startup_last
    if phase in _startup or (phase == "commit" and "render" not in _startup):
        return
    now = time.perf_counter()
    start = since if since is not None else _startup_last if _startup_last is not None else now
    _startup[phase] = (now - start) * 1000.0
    _startup_last = now
    # No profiler can be running before the profiling module is imported.
    profiling = sys.modules.get(f"{__package__}.profiling")
    if profiling is not None:
        profiling.gauge(f"startup.{phase}_ms", round(_startup[phase]))
    if phase == "commit":
        if _startup_origin is not None:
            _startup["total"] = (now - _startup_origin) * 1000.0
        if "app" in _startup:
            try:
                print(f"[PN] {startup_summary()}", flush=True)
            except Exception:
                pass


def startup_timeline() -> Dict[str, float]:
    """Return how long each startup phase of this process took, in milliseconds.

    Keys appear in launch order, and only for the phases recorded so far:

    - ``framework``: ``import pythonnative``, from the first line of the
      package's ``__init__`` to its last. Interpreter startup before it
      isn't included.
    - ``contracts``: starting the runtime and loading the native contracts
      compiled into the app (``bootstrap.start``).
    - ``bridge``: the protocol handshake and the view backend.
    - ``app``: the dev client (debug builds) and importing the app's
      entry module.
    - ``render``: the first screen's first render, from the start of its
      mount.
    - ``commit``: from the end of that render until the native side
      acknowledged the first commit.
    - ``total``: from the start of ``import pythonnative`` until that
      acknowledgment, including time between the phases (the native
      screen being created, for example). Present once ``commit`` is.

    A process that didn't launch through ``pythonnative.bootstrap`` (a
    test, the browser preview) records only the phases it ran.

    Returns:
        A new ``{phase: milliseconds}`` dict.
    """
    return dict(_startup)


def startup_summary() -> str:
    """The timeline as the one-line form logged at launch (``startup: framework 182 ms, ...``)."""
    return "startup: " + ", ".join(f"{phase} {ms:.0f} ms" for phase, ms in _startup.items())


# ======================================================================
# Warnings (LogBox-lite)
# ======================================================================

_MAX_WARNINGS = 200

_warn_lock = threading.Lock()
_warned_keys: Set[str] = set()
_warnings: Deque[str] = deque(maxlen=_MAX_WARNINGS)


def warn(message: str) -> None:
    """Print a dev warning and record it in the warning log.

    No-op in production. Warnings are prefixed with ``[PN] WARN`` on
    stderr and retained (most recent 200) for inspection via
    [`get_warnings`][pythonnative.diagnostics.get_warnings].

    Args:
        message: Human-readable description of the problem, ideally
            with a suggestion for the fix.
    """
    if not is_dev():
        return
    with _warn_lock:
        _warnings.append(message)
    try:
        print(f"[PN] WARN: {message}", file=sys.stderr, flush=True)
    except Exception:
        pass
    if _listeners:
        _notify_warning(message)


def warn_once(message: str, key: Optional[str] = None) -> None:
    """Like [`warn`][pythonnative.diagnostics.warn], but at most once per ``key``.

    Use for per-render validation (style keys, list keys) so a warning
    fires once instead of sixty times a second.

    Args:
        message: The warning message.
        key: Dedupe key, e.g. ``"style:Text:font_siez"``. Defaults to
            the message itself.
    """
    if not is_dev():
        return
    dedupe = key if key is not None else message
    with _warn_lock:
        if dedupe in _warned_keys:
            return
        _warned_keys.add(dedupe)
    warn(message)


def swallowed(context: str) -> None:
    """Surface a suppressed native-backend exception (dev mode only).

    The native view/module backends intentionally degrade gracefully in
    production: a failed style application or a missing OS API must not
    crash the app. Call this from the ``except`` block instead of
    ``pass`` so that, in dev mode, each suppression is reported once per
    call site instead of disappearing.

    Args:
        context: Where the suppression happened, e.g.
            ``"ios.TextHandler._apply"``.
    """
    if not is_dev():
        return
    exc = sys.exc_info()[1]
    if exc is None:
        return
    frame = sys._getframe(1)
    location = f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno}"
    warn_once(
        f"{context} suppressed {type(exc).__name__}: {exc} ({location})",
        key=f"swallowed:{context}:{location}",
    )


def get_warnings() -> List[str]:
    """Return a snapshot of the recorded warnings (oldest first)."""
    with _warn_lock:
        return list(_warnings)


def clear_warnings() -> None:
    """Drop all recorded warnings and dedupe keys (test helper)."""
    with _warn_lock:
        _warnings.clear()
        _warned_keys.clear()


# ======================================================================
# Error reporting (RedBox routing)
# ======================================================================
#
# Screen hosts register themselves as error reporters. When an error
# escapes user code in a context that would otherwise be swallowed
# (event handlers) or crash the process (async tasks), dev mode routes
# it to the most recently registered reporter, which shows the RedBox.
# Reporters form a stack: the top entry is the most recently created
# (and therefore frontmost) screen.

_reporter_lock = threading.Lock()
_reporters: List[Tuple[int, Callable[[BaseException, str], None]]] = []


def set_error_reporter(owner: Any, reporter: Optional[Callable[[BaseException, str], None]]) -> None:
    """Register or unregister ``owner``'s RedBox reporter.

    Args:
        owner: Any object identifying the registration (a screen
            host); keyed by ``id(owner)``.
        reporter: ``reporter(exc, phase)`` callable, or ``None`` to
            unregister the owner's reporter.
    """
    key = id(owner)
    with _reporter_lock:
        _reporters[:] = [(k, r) for (k, r) in _reporters if k != key]
        if reporter is not None:
            _reporters.append((key, reporter))


# ======================================================================
# Listeners (DevTools)
# ======================================================================

_listeners: List[Callable[[Any], None]] = []


def add_listener(callback: Callable[[Any], None]) -> Callable[[], None]:
    """Receive every warning and reported error as an ``ErrorReport``.

    The devtools agent subscribes so warnings and errors reach the
    DevTools Problems panel with their component stacks. Reports are only
    built while a listener is registered, and only in dev mode.

    Args:
        callback: Called with an
            [`ErrorReport`][pythonnative.errors.ErrorReport], on whichever
            thread raised the warning or error.

    Returns:
        A callable that removes the listener.
    """
    _listeners.append(callback)

    def remove() -> None:
        try:
            _listeners.remove(callback)
        except ValueError:
            pass

    return remove


def _notify(report: Any) -> None:
    for callback in list(_listeners):
        try:
            callback(report)
        except Exception:
            pass


def _notify_warning(message: str) -> None:
    try:
        from .errors import warning_report
        from .hooks import current_hook_state

        state = current_hook_state()
        _notify(warning_report(message, getattr(state, "_component_name", None) or None))
    except Exception:
        pass


def notify_error(exc: BaseException, phase: str) -> None:
    """Tell listeners about an error shown in the error screen or terminal."""
    if not _listeners or not is_dev():
        return
    try:
        from .errors import report

        _notify(report(exc, phase))
    except Exception:
        pass


_error_handler: Optional[Callable[[BaseException, str], None]] = None


def set_error_handler(handler: Optional[Callable[[BaseException, str], None]]) -> None:
    """Receive every uncaught error, in development and release builds alike.

    This is where a crash reporter attaches. ``handler`` gets the exception and
    the phase it came from (``"render"``, ``"effect"``, ``"event"``, ``"async"``,
    ``"mount"``, and similar). It runs on the application thread and should
    return quickly. An error it raises itself is printed and dropped. Errors a
    boundary of your own catches don't arrive here; use its ``on_error``.

    Args:
        handler: The callback, or ``None`` to remove the current one.

    Example:
        ```python
        import pythonnative as pn

        pn.set_error_handler(lambda error, phase: crash_reporter.capture(error, tags={"phase": phase}))
        ```
    """
    global _error_handler
    _error_handler = handler


def handle_error(exc: BaseException, phase: str) -> None:
    """Tell the app's error handler about ``exc``, at most once per exception."""
    handler = _error_handler
    if handler is None or getattr(exc, "_pn_handled", False):
        return
    try:
        exc._pn_handled = True  # type: ignore[attr-defined]
    except AttributeError:
        pass
    try:
        handler(exc, phase)
    except Exception:
        traceback.print_exc()


def report_error(exc: BaseException, phase: str = "runtime") -> bool:
    """Give ``exc`` to the app's error handler, and to the RedBox reporter in dev mode.

    Args:
        exc: The exception to display.
        phase: Where it came from: ``"render"``, ``"effect"``,
            ``"event"``, or ``"async"``.

    Returns:
        ``True`` when a reporter accepted the error, ``False`` when no
        reporter is registered (or dev mode is off), in which case the
        caller should fall back to its default behavior.
    """
    handle_error(exc, phase)
    if not is_dev():
        return False
    with _reporter_lock:
        reporter = _reporters[-1][1] if _reporters else None
    if reporter is None:
        return False
    try:
        reporter(exc, phase)
        return True
    except Exception:
        traceback.print_exc()
        return False
