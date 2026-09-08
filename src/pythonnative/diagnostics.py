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

This module has no dependencies on the rest of PythonNative, so any
module (hooks, reconciler, events) may import it freely.
"""

import os
import sys
import threading
import traceback
from collections import deque
from typing import Any, Callable, Deque, List, Optional, Set, Tuple

__all__ = [
    "HookOrderError",
    "set_dev_mode",
    "is_dev",
    "warn",
    "warn_once",
    "swallowed",
    "get_warnings",
    "clear_warnings",
    "set_error_reporter",
    "report_error",
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

# Tri-state: ``None`` means "not explicitly set, consult the environment".
_dev_mode: Optional[bool] = None


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


def is_dev() -> bool:
    """Return whether dev diagnostics are active.

    Resolution order: an explicit
    [`set_dev_mode`][pythonnative.diagnostics.set_dev_mode] call, then
    the ``PN_DEV`` environment variable, then ``False``.
    """
    if _dev_mode is not None:
        return _dev_mode
    return os.environ.get("PN_DEV", "").lower() in {"1", "true", "yes", "on"}


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


def report_error(exc: BaseException, phase: str = "runtime") -> bool:
    """Route ``exc`` to the active RedBox reporter (dev mode only).

    Args:
        exc: The exception to display.
        phase: Where it came from: ``"render"``, ``"effect"``,
            ``"event"``, or ``"async"``.

    Returns:
        ``True`` when a reporter accepted the error, ``False`` when no
        reporter is registered (or dev mode is off), in which case the
        caller should fall back to its default behavior.
    """
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
