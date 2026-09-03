"""Desktop preview host (Tkinter), driven by ``pn preview``.

Placement of the root widget and the screen stack are delegated to the
``DesktopApp`` controller in ``pythonnative.preview`` (passed as
``native_instance``). The controller runs the Tk event loop on the main
thread and polls ``drain_desktop_scheduled_renders`` so renders
requested from the asyncio worker thread are applied on the main thread.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

from .base import ScreenHost, flush_hosts

__all__ = ["DesktopScreenHost", "drain_desktop_scheduled_renders"]

_SCHEDULED: Dict[int, ScreenHost] = {}
_lock = threading.Lock()


def drain_desktop_scheduled_renders() -> None:
    """Apply renders queued from worker threads (called on the Tk main thread)."""
    with _lock:
        hosts = list(_SCHEDULED.values())
        _SCHEDULED.clear()
    flush_hosts(hosts)


class DesktopScreenHost(ScreenHost):
    """Host for one page of the desktop preview's screen stack."""

    def __init__(self, native_instance: Any = None, component_path: str = "", component: Any = None) -> None:
        super().__init__(native_instance, component_path, component)
        self.container: Any = None  # the Tk frame this page renders into (set by DesktopApp)

    def _initial_viewport_size(self) -> Optional[Tuple[float, float]]:
        app = self.native_instance
        if app is None or not hasattr(app, "viewport_size"):
            return None
        try:
            width, height = app.viewport_size()
            return (float(width), float(height))
        except Exception:
            return None

    def _schedule_render_async(self) -> bool:
        if threading.current_thread() is threading.main_thread():
            return False
        if self._render_scheduled:
            return True
        self._render_scheduled = True
        with _lock:
            _SCHEDULED[id(self)] = self
        return True

    def _native_push(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        app = self.native_instance
        if app is None or not hasattr(app, "push_screen"):
            raise RuntimeError("desktop navigation requires a running `pn preview` session")
        app.push_screen(component_path, args, options)

    def _native_pop(self, count: int) -> None:
        app = self.native_instance
        if app is not None and hasattr(app, "pop_screen"):
            for _ in range(count):
                app.pop_screen()

    def _native_pop_to_root(self) -> None:
        app = self.native_instance
        if app is not None and hasattr(app, "reset_to_root"):
            app.reset_to_root()

    def _native_set_options(self, options: Dict[str, Any]) -> None:
        title = options.get("title")
        app = self.native_instance
        if title is not None and app is not None and hasattr(app, "set_title"):
            try:
                app.set_title(str(title))
            except Exception:
                pass

    def _attach_root(self, native_view: Any) -> None:
        from ..native_views import desktop as backend

        stage = backend.get_root_container()
        if stage is not None and native_view is not None:
            try:
                native_view.place(in_=stage, x=0, y=0, relwidth=1.0, relheight=1.0)
                native_view.lift()
            except Exception:
                pass
        app = self.native_instance
        if app is not None and hasattr(app, "viewport_size"):
            try:
                width, height = app.viewport_size()
                self.set_viewport_size(float(width), float(height))
            except Exception:
                pass

    def _detach_root(self, native_view: Any) -> None:
        if native_view is not None:
            try:
                native_view.place_forget()
            except Exception:
                pass
