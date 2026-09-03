"""Platform-level metrics shared between screen hosts and view handlers.

The screen host (`pythonnative.hosts`) is the only place that knows
about native window/safe-area state because it is the only piece of
code that holds a reference to the native ``UIViewController``
(iOS) or ``Activity`` (Android). Native view handlers, however, need
that state to size themselves correctly:

- A bottom tab bar must claim both its visible 49 pt / 56 dp content
  height **and** the bottom safe-area inset so its background reaches
  the edge of the screen and the home indicator / gesture bar does
  not draw on top of the labels.
- A future safe-area-aware container can read the same values instead
  of asking each native view for window metrics.

Rather than threading those values through every
[`measure_intrinsic`][pythonnative.native_views.base.ViewHandler.measure_intrinsic]
call signature, the screen host writes them here and handlers read
them on demand. Values are in **dp on Android** and **pt on iOS**,
i.e., the same "layout units" the layout engine uses on each
platform, so handlers can add them to other layout-unit values
without further conversion. On iOS the screen host consumes the top
safe-area inset by positioning the root view below it, then publishes
``top=0`` here; Android publishes the raw system-bar insets because
the host view normally remains full-screen.

Example:
    >>> from pythonnative.platform_metrics import (
    ...     get_safe_area_insets, set_safe_area_insets,
    ... )
    >>> set_safe_area_insets(top=44.0, left=0.0, bottom=34.0, right=0.0)
    >>> get_safe_area_insets().bottom
    34.0
"""

from __future__ import annotations

import threading
from typing import Callable, List, NamedTuple


class SafeAreaInsets(NamedTuple):
    """Safe-area insets in layout units (pt on iOS, dp on Android)."""

    top: float
    left: float
    bottom: float
    right: float


class WindowDimensions(NamedTuple):
    """Viewport size in layout units (pt on iOS, dp on Android)."""

    width: float
    height: float


_safe_area_insets: SafeAreaInsets = SafeAreaInsets(0.0, 0.0, 0.0, 0.0)
_window_dimensions: WindowDimensions = WindowDimensions(0.0, 0.0)
_keyboard_height: float = 0.0

_subscribers: List[Callable[[], None]] = []
_subscribers_lock = threading.Lock()


def _notify_subscribers() -> None:
    """Invoke every registered subscriber, swallowing exceptions.

    Called from every metric setter so subscriber callbacks (the React
    hooks ``use_window_dimensions``/``use_safe_area_insets``/
    ``use_keyboard_height`` for example) can re-render in response to
    any metric change. Subscribers are called serially in registration
    order; any callback that raises is logged-and-skipped so a single
    misbehaving subscriber can't take down the whole notification
    cycle.
    """
    with _subscribers_lock:
        callbacks = list(_subscribers)
    for cb in callbacks:
        try:
            cb()
        except Exception:
            pass


def subscribe(callback: Callable[[], None]) -> Callable[[], None]:
    """Register *callback* to fire whenever any metric changes.

    Returns an unsubscribe function. Hooks pass a state setter so a
    component re-renders whenever the platform reports a new value.
    Threadsafe: multiple subscribers may register/unregister
    concurrently.
    """
    with _subscribers_lock:
        _subscribers.append(callback)

    def _unsub() -> None:
        with _subscribers_lock:
            try:
                _subscribers.remove(callback)
            except ValueError:
                pass

    return _unsub


def set_safe_area_insets(top: float, left: float, bottom: float, right: float) -> None:
    """Publish the current safe-area insets.

    Called by the platform-specific screen host whenever it learns a
    new value (e.g., on first layout, on rotation, on multitasking
    split-view changes). Negative inputs are clamped to ``0.0`` so
    handlers don't have to defend against bad data from native
    callers.

    Args:
        top: Distance in layout units from the top of the host
            container to the safe area (status bar / dynamic island /
            navigation bar).
        left: Inset from the left edge.
        bottom: Inset from the bottom edge (home indicator / gesture
            bar).
        right: Inset from the right edge.
    """
    global _safe_area_insets
    new_insets = SafeAreaInsets(
        max(0.0, float(top)),
        max(0.0, float(left)),
        max(0.0, float(bottom)),
        max(0.0, float(right)),
    )
    if new_insets == _safe_area_insets:
        return
    _safe_area_insets = new_insets
    _notify_subscribers()


def get_safe_area_insets() -> SafeAreaInsets:
    """Return the current safe-area insets.

    The default value is ``(0, 0, 0, 0)``; handlers should still
    function correctly on a desktop / unit-test environment where no
    screen host has published insets.
    """
    return _safe_area_insets


def reset_safe_area_insets() -> None:
    """Reset the insets back to ``(0, 0, 0, 0)``.

    Intended for unit tests that need a clean slate between cases.
    Production code should use
    [`set_safe_area_insets`][pythonnative.platform_metrics.set_safe_area_insets]
    instead.
    """
    global _safe_area_insets
    _safe_area_insets = SafeAreaInsets(0.0, 0.0, 0.0, 0.0)


def set_window_dimensions(width: float, height: float) -> None:
    """Publish the viewport size in layout units.

    Called by the screen host on initial layout, rotation, and split-
    view changes. Notifies subscribers (and therefore re-renders
    components using ``use_window_dimensions``) only when the size
    actually changes.
    """
    global _window_dimensions
    new_dims = WindowDimensions(max(0.0, float(width)), max(0.0, float(height)))
    if new_dims == _window_dimensions:
        return
    _window_dimensions = new_dims
    _notify_subscribers()


def get_window_dimensions() -> WindowDimensions:
    """Return the current viewport size, or ``(0, 0)`` before first layout."""
    return _window_dimensions


def reset_window_dimensions() -> None:
    """Reset window dimensions back to ``(0, 0)``. Intended for tests."""
    global _window_dimensions
    _window_dimensions = WindowDimensions(0.0, 0.0)


def set_keyboard_height(height: float) -> None:
    """Publish the on-screen keyboard height in layout units.

    Negative inputs are clamped to ``0.0``. Notifies subscribers only
    when the value actually changes.
    """
    global _keyboard_height
    new_h = max(0.0, float(height))
    if new_h == _keyboard_height:
        return
    _keyboard_height = new_h
    _notify_subscribers()


def get_keyboard_height() -> float:
    """Return the current on-screen keyboard height, or ``0.0`` if hidden."""
    return _keyboard_height


def reset_keyboard_height() -> None:
    """Reset the keyboard height back to ``0.0``. Intended for tests."""
    global _keyboard_height
    _keyboard_height = 0.0


# ======================================================================
# Per-platform tab-bar defaults
# ======================================================================
#
# Only iOS exposes an explicit constant here. The iOS handler can't
# trust ``UITabBar.sizeThatFits_`` (it has historically returned 0 in
# some configurations) and the screen host deliberately extends the
# root view past the bottom safe area so the bar reaches the home
# indicator; both pieces conspire to require a single source of
# truth for the height formula.
#
# Android intentionally has no equivalent: ``BottomNavigationView``
# reports a reliable natural height via ``measure(…)`` once attached
# to the window, and the active-indicator pill is positioned against
# that natural height. Forcing our own height threw off the pill
# geometry, so the Android handler defers entirely to the system.

IOS_TAB_BAR_BASE_HEIGHT_PT: float = 49.0
"""UIKit HIG tab-bar content height in points.

The total bar reaches ``IOS_TAB_BAR_BASE_HEIGHT_PT +
safe_area_insets.bottom`` so the pill background can extend over the
home indicator. Apple's HIG places the tab bar flush with the screen
edge and lets UIKit render its own internal padding for the home
indicator.
"""


def ios_tab_bar_height() -> float:
    """Return the iOS tab-bar intrinsic height in points.

    Equal to ``IOS_TAB_BAR_BASE_HEIGHT_PT + safe_area_insets.bottom``
    so the bar reaches the home indicator. The iOS screen host
    deliberately extends the root view past the bottom safe area for
    this very reason; the tab bar absorbs the inset and UIKit
    renders the pill with internal padding for the home indicator.
    Used by ``pythonnative.native_views.ios.TabBarHandler``; exposed
    here so the formula is testable without importing the iOS
    handler module (which requires ``rubicon-objc``).
    """
    return IOS_TAB_BAR_BASE_HEIGHT_PT + get_safe_area_insets().bottom
