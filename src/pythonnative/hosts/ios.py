"""iOS screen host: one ``UIViewController`` per screen, driven by ``ViewController.swift``."""

from __future__ import annotations

import json
import sys
import threading
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from ..utils import IS_IOS
from .base import ScreenHost, flush_hosts, log_pn

__all__ = ["IOSScreenHost", "drain_ios_scheduled_renders", "forward_lifecycle"]

try:
    from rubicon.objc import SEL, ObjCClass, ObjCInstance, objc_method

    _rubicon_available = True
    import gc as _gc

    _gc.disable()
except ImportError:  # pragma: no cover - only on hosts without the [ios] extra
    _rubicon_available = False

# Redirect Python's stdout/stderr through fd 2 so ``print()`` output is
# visible via ``xcrun simctl launch --console-pty``. Runs before any user
# module is imported so their top-level prints are captured too.
if IS_IOS:
    try:
        from .. import _ios_log

        _ios_log.install()
    except Exception:
        pass

_REGISTRY: Dict[int, ScreenHost] = {}
_SCHEDULED: Dict[int, ScreenHost] = {}
_timer_target: Any = None
_native_scheduler: Any = None


def _objc_addr(obj: Any) -> Optional[int]:
    """Pointer of an ``ObjCInstance`` as an int (``ptr`` varies by rubicon release)."""
    ptr = getattr(obj, "ptr", None)
    if ptr is None:
        return None
    if isinstance(ptr, (bytes, bytearray)):
        try:
            return int.from_bytes(ptr, byteorder=sys.byteorder, signed=False)
        except Exception:
            return None
    if isinstance(ptr, int):
        return ptr
    value = getattr(ptr, "value", None)
    if isinstance(value, int):
        return value
    try:
        return int(ptr)
    except Exception:
        return None


def _publish_color_scheme() -> None:
    try:
        from .. import appearance

        UITraitCollection = ObjCClass("UITraitCollection")
        style_value = int(UITraitCollection.currentTraitCollection.userInterfaceStyle)
        appearance.set_system_color_scheme("dark" if style_value == 2 else "light")
    except Exception:
        pass


def _flush_scheduled() -> None:
    hosts = list(_SCHEDULED.values())
    _SCHEDULED.clear()
    if hosts:
        log_pn(f"render_scheduler: flushing {len(hosts)} host(s)")
    flush_hosts(hosts)


def drain_ios_scheduled_renders() -> None:
    """Entry point used by the iOS template to drain pending renders on the main thread."""
    _flush_scheduled()


def _wake_native_drain() -> bool:
    """Ask the template's ``pn_schedule_render_drain`` to drain on the main thread."""
    global _native_scheduler
    try:
        if _native_scheduler is None:
            import ctypes

            scheduler = ctypes.CDLL(None).pn_schedule_render_drain
            scheduler.restype = None
            scheduler.argtypes = []
            _native_scheduler = scheduler
        _native_scheduler()
        return True
    except Exception as exc:
        log_pn(f"render_scheduler: native iOS wake failed: {exc!r}")
        return False


def forward_lifecycle(native_addr: int, event: str) -> None:
    """Forward a Swift ``UIViewController`` lifecycle event to its host.

    Args:
        native_addr: Pointer of the view controller, as registered by
            ``create_screen``.
        event: Host method name (``"on_resume"``, ``"on_layout"``, ...).
    """
    try:
        key = int(native_addr)
    except Exception as exc:
        log_pn(f"forward_lifecycle: bad native_addr={native_addr!r}: {exc!r}")
        return
    host = _REGISTRY.get(key)
    if host is None:
        log_pn(f"forward_lifecycle: no host for event={event!r} addr={key}")
        return
    handler = getattr(host, event, None)
    if handler is None:
        log_pn(f"forward_lifecycle: host has no {event!r}")
        return
    try:
        handler()
    except Exception as exc:
        log_pn(f"forward_lifecycle: {event!r} raised: {exc!r}")


if _rubicon_available and IS_IOS:
    NSObject = ObjCClass("NSObject")

    class _RenderTimerTarget(NSObject):  # type: ignore[misc, valid-type]
        @objc_method
        def onRenderTimer_(self, timer: object) -> None:
            _flush_scheduled()

    def _timer_target_instance() -> Any:
        global _timer_target
        if _timer_target is None:
            target = _RenderTimerTarget.new()
            try:
                target.retain()
            except Exception:
                pass
            _timer_target = target
        return _timer_target


class IOSScreenHost(ScreenHost):
    """Host owned by a ``ViewController``; pushes onto its ``UINavigationController``."""

    def __init__(self, native_instance: Any, component_path: str, component: Any) -> None:
        if isinstance(native_instance, int):
            try:
                native_instance = ObjCInstance(native_instance)
            except Exception:
                native_instance = None
        super().__init__(native_instance, component_path, component)
        if self.native_instance is not None:
            addr = _objc_addr(self.native_instance)
            if addr is not None:
                _REGISTRY[addr] = self

    # -- lifecycle ------------------------------------------------------

    def on_create(self) -> None:
        """Publish the system color scheme, then mount the root component."""
        _publish_color_scheme()
        super().on_create()

    def on_layout(self) -> None:
        """Sync the root view's frame and viewport size after ``viewDidLayoutSubviews``."""
        # ``viewDidLayoutSubviews``: safe-area insets are valid now.
        _publish_color_scheme()
        if self.root_native_view is not None:
            self._sync_root_frame(self.root_native_view)
            self._push_viewport_from_root(self.root_native_view)

    def on_resume(self) -> None:
        """Mark the screen focused and refresh the color scheme, root frame, and viewport size."""
        _publish_color_scheme()
        super().on_resume()
        if self.root_native_view is not None:
            self._sync_root_frame(self.root_native_view)
            self._push_viewport_from_root(self.root_native_view)

    def on_destroy(self) -> None:
        """Drop this host from the view-controller registry, then tear down the tree."""
        if self.native_instance is not None:
            addr = _objc_addr(self.native_instance)
            if addr is not None:
                _REGISTRY.pop(addr, None)
        super().on_destroy()

    # -- platform primitives -------------------------------------------

    def _initial_viewport_size(self) -> Optional[Tuple[float, float]]:
        try:
            if self.native_instance is not None:
                bounds = self.native_instance.view.bounds
                if bounds.size.width > 0 and bounds.size.height > 0:
                    return (float(bounds.size.width), float(bounds.size.height))
        except Exception:
            pass
        try:
            bounds = ObjCClass("UIScreen").mainScreen.bounds
            return (float(bounds.size.width), float(bounds.size.height))
        except Exception:
            return None

    def _schedule_render_async(self) -> bool:
        if self._render_scheduled:
            return True
        self._render_scheduled = True
        _SCHEDULED[id(self)] = self
        if threading.current_thread() is not threading.main_thread():
            if not _wake_native_drain():
                log_pn("request_render: native iOS scheduler unavailable; render remains queued")
            return True
        # Main-queue GCD blocks run in the common run-loop modes, so
        # renders land during scrolls and synthesized test touches; a
        # default-mode NSTimer is starved for the whole gesture.
        from ..runtime import _ensure_libdispatch_loaded, _ios_dispatch_async

        if _ensure_libdispatch_loaded():
            _ios_dispatch_async(_flush_scheduled)
            return True
        try:
            NSTimer = ObjCClass("NSTimer")
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.0, _timer_target_instance(), SEL("onRenderTimer:"), None, False
            )
            return True
        except Exception as exc:
            self._render_scheduled = False
            _SCHEDULED.pop(id(self), None)
            log_pn(f"request_render: iOS defer failed ({exc!r}); rendering synchronously")
            return False

    def _view_controller_class(self) -> Any:
        try:
            return ObjCClass("ViewController")
        except Exception:
            pass
        try:
            bundle = ObjCClass("NSBundle").mainBundle
            module_name = bundle.objectForInfoDictionaryKey_("CFBundleName") or bundle.objectForInfoDictionaryKey_(
                "CFBundleExecutable"
            )
            if module_name:
                return ObjCClass(f"{module_name}.ViewController")
        except Exception:
            pass
        raise NameError("ViewController class not found; ensure the Swift class is ObjC-visible")

    def _make_view_controller(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> Any:
        vc = self._view_controller_class().alloc().init()
        try:
            vc.setValue_forKey_(component_path, "requestedScreenPath")
            if args:
                vc.setValue_forKey_(json.dumps(args), "requestedScreenArgsJSON")
        except Exception:
            pass
        title = options.get("title")
        if title is not None:
            try:
                vc.setTitle_(str(title))
            except Exception:
                pass
        return vc

    def _run_nav_op(self, op: Callable[[Any], None]) -> None:
        """Run ``op(nav)`` unless a transition is mid-flight.

        UIKit doesn't queue navigation calls: one issued during an
        animation is ignored or misapplied. Dropping it keeps the stack
        consistent; a retry lands on a settled stack.
        """
        nav = getattr(self.native_instance, "navigationController", None)
        if nav is None:
            raise RuntimeError("No UINavigationController; the template must embed the root in one")
        try:
            coord = nav.transitionCoordinator
            if callable(coord):
                coord = coord()
            if coord is not None:
                log_pn("_run_nav_op: transition in flight; dropping nav op")
                return
        except Exception:
            pass
        op(nav)

    def _native_push(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        vc = self._make_view_controller(component_path, args, options)
        self._run_nav_op(lambda nav: nav.pushViewController_animated_(vc, True))

    def _native_pop(self, count: int) -> None:
        def op(nav: Any) -> None:
            if count <= 1:
                nav.popViewControllerAnimated_(True)
                return
            controllers = nav.viewControllers
            n = int(controllers.count)
            target_index = max(0, n - 1 - count)
            nav.popToViewController_animated_(controllers.objectAtIndex_(target_index), True)

        self._run_nav_op(op)

    def _native_pop_to_root(self) -> None:
        self._run_nav_op(lambda nav: nav.popToRootViewControllerAnimated_(True))

    def _native_replace(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        vc = self._make_view_controller(component_path, args, options)

        def op(nav: Any) -> None:
            controllers = list(nav.viewControllers)
            controllers[-1] = vc
            nav.setViewControllers_animated_(controllers, True)

        self._run_nav_op(op)

    def _native_reset(self, component_path: str, screens: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]) -> None:
        vcs = [self._make_view_controller(component_path, args, options) for args, options in screens]

        def op(nav: Any) -> None:
            root = nav.viewControllers.objectAtIndex_(0)
            nav.setViewControllers_animated_([root, *vcs], True)

        self._run_nav_op(op)

    def _native_set_options(self, options: Dict[str, Any]) -> None:
        title = options.get("title")
        if title is None or self.native_instance is None:
            return
        try:
            self.native_instance.setTitle_(str(title))
        except Exception as exc:
            log_pn(f"set_screen_options: setTitle failed: {exc!r}")

    def _attach_root(self, native_view: Any) -> None:
        self.native_instance.view.addSubview_(native_view)
        # Frame-based layout for the root so the layout engine's frames
        # aren't fought by Auto Layout.
        try:
            native_view.setTranslatesAutoresizingMaskIntoConstraints_(True)
            native_view.setAutoresizingMask_(2 | 16)  # FlexibleWidth | FlexibleHeight
        except Exception:
            pass
        self._sync_root_frame(native_view)
        self._push_viewport_from_root(native_view)

    def _detach_root(self, native_view: Any) -> None:
        try:
            native_view.removeFromSuperview()
        except Exception:
            pass

    # -- viewport plumbing ---------------------------------------------

    def _sync_root_frame(self, native_view: Any) -> None:
        """Position the root below the top safe area, full-bleed at the bottom.

        The bottom inset is published to ``platform_metrics`` instead of
        being subtracted, so a tab bar can reach the home indicator;
        content that needs it opts in via ``SafeAreaView``.
        """
        root_view = self.native_instance.view
        if root_view is None:
            return
        try:
            bounds, insets = root_view.bounds, root_view.safeAreaInsets
            top, left, right, bottom = float(insets.top), float(insets.left), float(insets.right), float(insets.bottom)
            w = max(0.0, float(bounds.size.width) - left - right)
            h = max(0.0, float(bounds.size.height) - top)
            try:
                from .. import platform_metrics

                platform_metrics.set_safe_area_insets(0.0, left, bottom, right)
            except Exception:
                pass
            if w > 0 and h > 0:
                native_view.setFrame_(((left, top), (w, h)))
                return
        except Exception as exc:
            log_pn(f"sync_root_frame: insets path failed: {exc!r}")
        try:
            bounds = root_view.bounds
            native_view.setFrame_(((0, 0), (float(bounds.size.width), float(bounds.size.height))))
        except Exception as exc:
            log_pn(f"sync_root_frame: bounds fallback failed: {exc!r}")

    def _push_viewport_from_root(self, native_view: Any) -> None:
        try:
            bounds = native_view.bounds
            w, h = float(bounds.size.width), float(bounds.size.height)
            if w <= 0 or h <= 0:
                screen = ObjCClass("UIScreen").mainScreen.bounds
                w, h = float(screen.size.width), float(screen.size.height)
            self.set_viewport_size(w, h)
        except Exception as exc:
            log_pn(f"push_viewport: failed: {exc!r}")
