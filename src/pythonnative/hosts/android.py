"""Android screen host: a fragment inside the template's ``NavHostFragment``."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional, Tuple

from java import dynamic_proxy, jclass

from ..utils import get_android_fragment_container, set_android_context
from .base import ScreenHost, flush_hosts

__all__ = ["AndroidScreenHost"]

_SCHEDULED: Dict[int, ScreenHost] = {}
_handler: Any = None
_runnable: Any = None
_main_looper: Any = None


def _is_main_thread() -> bool:
    global _main_looper
    try:
        Looper = jclass("android.os.Looper")
        if _main_looper is None:
            _main_looper = Looper.getMainLooper()
        return Looper.myLooper() == _main_looper
    except Exception:
        return threading.current_thread() is threading.main_thread()


def _flush_scheduled() -> None:
    hosts = list(_SCHEDULED.values())
    _SCHEDULED.clear()
    flush_hosts(hosts)


def _publish_window_insets(view: Any) -> None:
    """Publish system-bar and IME insets from ``view`` to ``platform_metrics`` (best-effort)."""
    try:
        from .. import platform_metrics
    except Exception:
        return
    try:
        insets_obj = view.getRootWindowInsets()
        if insets_obj is None:
            return
        density = float(view.getResources().getDisplayMetrics().density) or 1.0
        Type: Any = None
        try:
            WindowInsets = jclass("android.view.WindowInsets")
            Type = WindowInsets.Type
            typed = insets_obj.getInsets(Type.systemBars())
            top_px, left_px, bottom_px, right_px = int(typed.top), int(typed.left), int(typed.bottom), int(typed.right)
        except Exception:
            top_px = int(insets_obj.getSystemWindowInsetTop() or 0)
            left_px = int(insets_obj.getSystemWindowInsetLeft() or 0)
            bottom_px = int(insets_obj.getSystemWindowInsetBottom() or 0)
            right_px = int(insets_obj.getSystemWindowInsetRight() or 0)
        platform_metrics.set_safe_area_insets(
            top_px / density, left_px / density, bottom_px / density, right_px / density
        )
        # The keyboard overlaps the navigation bar, so the visible
        # keyboard height is the IME inset minus the bar inset.
        try:
            ime = insets_obj.getInsets(Type.ime())
            platform_metrics.set_keyboard_height(max(0, int(ime.bottom) - bottom_px) / density)
        except Exception:
            pass
    except Exception:
        pass


def _publish_color_scheme(activity: Any) -> None:
    try:
        from .. import appearance

        Configuration = jclass("android.content.res.Configuration")
        ui_mode = int(activity.getResources().getConfiguration().uiMode)
        night = ui_mode & int(Configuration.UI_MODE_NIGHT_MASK)
        appearance.set_system_color_scheme("dark" if night == int(Configuration.UI_MODE_NIGHT_YES) else "light")
    except Exception:
        pass


class AndroidScreenHost(ScreenHost):
    """Host owned by ``ScreenFragment.kt``; ``native_instance`` is the activity."""

    def __init__(self, native_instance: Any, component_path: str, component: Any) -> None:
        set_android_context(native_instance)
        super().__init__(native_instance, component_path, component)
        self._layout_listener: Any = None  # retained to prevent GC
        self._insets_listener: Any = None

    # -- lifecycle ------------------------------------------------------

    def on_create(self) -> None:
        """Publish the system color scheme from the activity, then mount the root component."""
        _publish_color_scheme(self.native_instance)
        super().on_create()

    def on_resume(self) -> None:
        """Refresh the system color scheme, then mark the screen focused."""
        _publish_color_scheme(self.native_instance)
        super().on_resume()

    def on_activity_result(self, request_code: int, result_code: int, data: Any) -> None:
        """Forward ``Activity.onActivityResult`` to the native-module dispatcher."""
        from ..native_modules import dispatch_activity_result

        dispatch_activity_result(int(request_code), int(result_code), data)

    def on_request_permissions_result(self, request_code: int, permissions: Any, grant_results: Any) -> None:
        """Forward ``Activity.onRequestPermissionsResult`` to the native-module dispatcher."""
        from ..native_modules import dispatch_permissions_result

        dispatch_permissions_result(int(request_code), list(permissions or []), list(grant_results or []))

    # -- platform primitives -------------------------------------------

    def _initial_viewport_size(self) -> Optional[Tuple[float, float]]:
        try:
            metrics = self.native_instance.getResources().getDisplayMetrics()
            density = float(metrics.density) or 1.0
            return (metrics.widthPixels / density, metrics.heightPixels / density)
        except Exception:
            return None

    def _schedule_render_async(self) -> bool:
        global _handler, _runnable
        if self._render_scheduled:
            return True
        if _is_main_thread():
            return False
        self._render_scheduled = True
        _SCHEDULED[id(self)] = self
        try:
            if _handler is None:
                Handler = jclass("android.os.Handler")
                Looper = jclass("android.os.Looper")
                Runnable = jclass("java.lang.Runnable")
                _handler = Handler(Looper.getMainLooper())

                class _RenderRunnable(dynamic_proxy(Runnable)):  # type: ignore[misc]
                    def run(self) -> None:
                        _flush_scheduled()

                _runnable = _RenderRunnable()
            _handler.post(_runnable)
            return True
        except Exception:
            self._render_scheduled = False
            _SCHEDULED.pop(id(self), None)
            return False

    def _navigator(self) -> Any:
        return jclass(f"{self.native_instance.getPackageName()}.Navigator")

    def _native_push(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        self._navigator().push(self.native_instance, component_path, json.dumps(args) if args else None)

    def _native_pop(self, count: int) -> None:
        try:
            navigator = self._navigator()
            for _ in range(count):
                navigator.pop(self.native_instance)
        except Exception:
            self.native_instance.finish()

    def _native_pop_to_root(self) -> None:
        try:
            self._navigator().popToRoot(self.native_instance)
        except Exception:
            pass

    def _native_set_options(self, options: Dict[str, Any]) -> None:
        title = options.get("title")
        try:
            if title is not None and hasattr(self.native_instance, "setTitle"):
                self.native_instance.setTitle(str(title))
        except Exception:
            pass

    def _attach_root(self, native_view: Any) -> None:
        container = None
        try:
            container = get_android_fragment_container()
            try:
                container.removeAllViews()
            except Exception:
                pass
            # A root from a prior mount may still be parented under the
            # old (destroyed) FrameLayout; addView throws otherwise.
            try:
                old_parent = native_view.getParent()
                if old_parent is not None:
                    old_parent.removeView(native_view)
            except Exception:
                pass
            LayoutParams = jclass("android.view.ViewGroup$LayoutParams")
            container.addView(native_view, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        except Exception:
            self.native_instance.setContentView(native_view)
            container = native_view
        if container is not None:
            self._register_layout_listener(container)
            self._register_insets_listener(container)
            self._push_initial_viewport(container)

    def _detach_root(self, native_view: Any) -> None:
        # Never clear the shared fragment container: a popped fragment's
        # detach runs after the screen below has re-attached its root.
        if native_view is None:
            return
        try:
            parent = native_view.getParent()
            if parent is not None:
                parent.removeView(native_view)
        except Exception:
            pass

    # -- viewport plumbing ---------------------------------------------

    def _register_layout_listener(self, view: Any) -> None:
        host = self
        try:
            View = jclass("android.view.View")

            class _LayoutListener(dynamic_proxy(View.OnLayoutChangeListener)):  # type: ignore[misc]
                def onLayoutChange(self, v: Any, left: int, top: int, right: int, bottom: int, *_: Any) -> None:
                    try:
                        _publish_window_insets(v)
                        density = float(v.getResources().getDisplayMetrics().density) or 1.0
                        host.set_viewport_size((right - left) / density, (bottom - top) / density)
                    except Exception:
                        pass

            self._layout_listener = _LayoutListener()
            view.addOnLayoutChangeListener(self._layout_listener)
        except Exception:
            pass

    def _register_insets_listener(self, view: Any) -> None:
        try:
            View = jclass("android.view.View")

            class _InsetsListener(dynamic_proxy(View.OnApplyWindowInsetsListener)):  # type: ignore[misc]
                def onApplyWindowInsets(self, v: Any, insets: Any) -> Any:
                    _publish_window_insets(v)
                    return insets

            self._insets_listener = _InsetsListener()
            view.setOnApplyWindowInsetsListener(self._insets_listener)
        except Exception:
            pass

    def _push_initial_viewport(self, view: Any) -> None:
        try:
            _publish_window_insets(view)
            metrics = view.getResources().getDisplayMetrics()
            density = float(metrics.density) or 1.0
            w, h = int(view.getWidth() or 0), int(view.getHeight() or 0)
            if w > 0 and h > 0:
                self.set_viewport_size(w / density, h / density)
            else:
                self.set_viewport_size(metrics.widthPixels / density, metrics.heightPixels / density)
        except Exception:
            pass
