"""On-device screen host, shared by iOS and Android.

One [`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost]
exists per native screen (``UIViewController`` / ``Fragment``). The
native side never holds Python objects: screens are addressed by an
integer id it assigns, lifecycle arrives through
``callback("host", screen_id, event, payload)`` (routed here by
[`dispatch_host_event`][pythonnative.hosts.native.dispatch_host_event]),
and everything the host needs from the platform goes out through the
``Host`` native module (``attach_root``, ``push``, ``pop``, ...). See
``docs/concepts/bridge.md`` for the payloads.

Because native reports viewport size, safe-area insets, keyboard
height, and color scheme *with* each lifecycle event, this module
never queries the platform; it only publishes what it is told.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional, Sequence, Tuple

from .. import appearance, diagnostics, platform_metrics
from ..bridge import codec
from ..native_modules.registry import native_module
from .base import ScreenHost, flush_hosts, log_pn

__all__ = ["NativeScreenHost", "dispatch_host_event", "host_for_screen", "live_hosts"]

_HOSTS: Dict[int, "NativeScreenHost"] = {}
_SCHEDULED: Dict[int, ScreenHost] = {}
_flush_pending = False


def host_for_screen(screen_id: int) -> Optional["NativeScreenHost"]:
    """Return the host registered for ``screen_id`` (``None`` if unknown)."""
    return _HOSTS.get(int(screen_id))


def live_hosts() -> Sequence["NativeScreenHost"]:
    """Every host currently registered, in creation order."""
    return list(_HOSTS.values())


def _host_module() -> Any:
    return native_module("Host")


# ======================================================================
# Deferred renders
# ======================================================================


def _flush_scheduled() -> None:
    global _flush_pending
    _flush_pending = False
    hosts = list(_SCHEDULED.values())
    _SCHEDULED.clear()
    if hosts:
        log_pn(f"render_scheduler: flushing {len(hosts)} host(s)")
    flush_hosts(hosts)


def _request_flush() -> None:
    """Queue one main-thread flush of every scheduled host."""
    global _flush_pending
    if _flush_pending:
        return
    _flush_pending = True
    from ..bridge import post_to_main

    post_to_main(_flush_scheduled)


# ======================================================================
# Payload helpers
# ======================================================================


def _publish_metrics(payload: Any) -> Tuple[float, float]:
    """Publish viewport, insets, keyboard, and color scheme from a host payload.

    Returns the ``(width, height)`` it found (``0, 0`` when absent).
    """
    if not isinstance(payload, dict):
        return (0.0, 0.0)
    width = float(payload.get("width") or 0.0)
    height = float(payload.get("height") or 0.0)
    insets = payload.get("insets")
    if isinstance(insets, dict):
        platform_metrics.set_safe_area_insets(
            float(insets.get("top") or 0.0),
            float(insets.get("left") or 0.0),
            float(insets.get("bottom") or 0.0),
            float(insets.get("right") or 0.0),
        )
    if "keyboard_height" in payload:
        platform_metrics.set_keyboard_height(float(payload.get("keyboard_height") or 0.0))
    scheme = payload.get("color_scheme")
    if scheme in ("light", "dark"):
        appearance.set_system_color_scheme(str(scheme))
    if width > 0 and height > 0:
        platform_metrics.set_window_dimensions(width, height)
    return (width, height)


# ======================================================================
# Host
# ======================================================================


class NativeScreenHost(ScreenHost):
    """Screen host addressed by an integer ``screen_id`` on the bridge."""

    def __init__(self, screen_id: int, component_path: str, component: Any) -> None:
        super().__init__(int(screen_id), component_path, component)
        self.screen_id = int(screen_id)
        self._pending_viewport: Optional[Tuple[float, float]] = None
        _HOSTS[self.screen_id] = self

    # -- lifecycle ------------------------------------------------------

    def on_destroy(self) -> None:
        """Forget the screen id, then tear down the tree."""
        _HOSTS.pop(self.screen_id, None)
        _SCHEDULED.pop(id(self), None)
        super().on_destroy()

    def apply_metrics(self, payload: Any) -> None:
        """Publish the metrics carried by a host event and resize the viewport."""
        width, height = _publish_metrics(payload)
        if width > 0 and height > 0:
            self._pending_viewport = (width, height)
            self.set_viewport_size(width, height)

    # -- platform primitives -------------------------------------------

    def _initial_viewport_size(self) -> Optional[Tuple[float, float]]:
        if self._pending_viewport is not None:
            return self._pending_viewport
        dims = platform_metrics.get_window_dimensions()
        if dims.width > 0 and dims.height > 0:
            return (dims.width, dims.height)
        return None

    def _schedule_render_async(self) -> bool:
        if self._render_scheduled:
            return True
        self._render_scheduled = True
        _SCHEDULED[id(self)] = self
        try:
            _request_flush()
        except Exception as exc:
            self._render_scheduled = False
            _SCHEDULED.pop(id(self), None)
            log_pn(f"request_render: bridge defer failed ({exc!r}); rendering synchronously")
            return False
        return True

    def _attach_root(self, native_view: Any) -> None:
        tag = getattr(native_view, "tag", None)
        if tag is None:
            return
        # Native answers with the viewport the root now occupies, which
        # is the earliest exact size available on iOS.
        result = _host_module().call("attach_root", screen=self.screen_id, tag=int(tag))
        if isinstance(result, dict):
            self.apply_metrics(result)

    def _detach_root(self, native_view: Any) -> None:
        tag = getattr(native_view, "tag", None)
        if tag is None:
            return
        try:
            _host_module().call("detach_root", screen=self.screen_id, tag=int(tag))
        except Exception:
            diagnostics.swallowed("hosts.native.detach_root")

    def _native_push(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        _host_module().call(
            "push",
            screen=self.screen_id,
            path=component_path,
            args=json.dumps(args) if args else None,
            options=codec.to_jsonable(options or {}),
        )

    def _native_pop(self, count: int) -> None:
        _host_module().call("pop", screen=self.screen_id, count=int(count))

    def _native_pop_to_root(self) -> None:
        _host_module().call("pop_to_root", screen=self.screen_id)

    def _native_replace(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        _host_module().call(
            "replace",
            screen=self.screen_id,
            path=component_path,
            args=json.dumps(args) if args else None,
            options=codec.to_jsonable(options or {}),
        )

    def _native_reset(self, component_path: str, screens: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]) -> None:
        _host_module().call(
            "reset",
            screen=self.screen_id,
            path=component_path,
            screens=[
                {
                    "path": component_path,
                    "args": json.dumps(args) if args else None,
                    "options": codec.to_jsonable(options or {}),
                }
                for args, options in screens
            ],
        )

    def _native_set_options(self, options: Dict[str, Any]) -> None:
        _host_module().call("set_options", screen=self.screen_id, options=codec.to_jsonable(options or {}))


# ======================================================================
# Inbound host events
# ======================================================================

_create_lock = threading.Lock()


def dispatch_host_event(screen_id: int, event: str, payload: Any) -> Optional[str]:
    """Route ``callback("host", screen_id, event, payload)`` to a host.

    Events (payloads are what ``PNViewController`` and
    ``PNScreenFragment`` send):

    - ``create`` ``{"path", "args", "dev_root", "restored_state",
      ...metrics}``: import the component, create the host, and mount.
      ``path`` is the dotted component path (``None`` means the app
      entry module), ``args`` a JSON string, ``dev_root`` the hot-reload
      overlay directory for debug builds. Returns ``{"root": tag}``.
    - ``start`` / ``resume`` / ``pause`` / ``stop`` / ``destroy``:
      lifecycle. ``resume`` and ``layout`` carry metrics.
    - ``layout`` ``{width, height, insets, keyboard_height, color_scheme}``.
    - ``appearance`` ``{"color_scheme"}``.
    - ``back_pressed``: returns ``"true"`` when a handler consumed it.
    - ``hot_reload_tick``: poll the reload manifest; returns ``"true"``
      when a reload ran.
    - ``save_state`` / ``restore_state``: instance-state hooks.
    - ``flush``: run deferred renders now.

    Returns a JSON string for request-style events, else ``None``.
    """
    screen_id = int(screen_id)
    if event == "create":
        return _create(screen_id, payload if isinstance(payload, dict) else {})
    if event == "flush":
        _flush_scheduled()
        return None
    if event == "appearance":
        _publish_metrics(payload)
        return None
    host = _HOSTS.get(screen_id)
    if host is None:
        log_pn(f"dispatch_host_event: no host for screen={screen_id} event={event!r}")
        return None
    if event == "layout":
        host.apply_metrics(payload)
        host.on_layout()
        return None
    if event == "resume":
        host.apply_metrics(payload)
        host.on_resume()
        return None
    if event == "back_pressed":
        return "true" if host.on_back_pressed() else "false"
    if event in ("hot_reload_tick", "tick"):
        return "true" if host.hot_reload_tick() else "false"
    if event == "save_state":
        host.on_save_instance_state()
        return None
    if event == "restore_state":
        host.on_restore_instance_state()
        return None
    if event == "destroy":
        host.on_destroy()
        return None
    handler = getattr(host, f"on_{event}", None)
    if handler is None:
        log_pn(f"dispatch_host_event: unknown event {event!r}")
        return None
    handler()
    return None


def _create(screen_id: int, payload: Dict[str, Any]) -> Optional[str]:
    from . import import_component

    component_path = str(payload.get("path") or payload.get("component") or _entry_module())
    with _create_lock:
        existing = _HOSTS.get(screen_id)
        if existing is not None:
            existing.apply_metrics(payload)
            existing.on_create()
            return _root_json(existing)
        component = import_component(component_path)
        host = NativeScreenHost(screen_id, component_path, component)
    args = payload.get("args")
    if args:
        host.set_args(args)
    dev_root = payload.get("dev_root")
    if dev_root:
        from .. import hot_reload

        host.enable_hot_reload(hot_reload.manifest_path_for(str(dev_root)), str(dev_root))
    if not (payload.get("width") and payload.get("height")):
        # ``create`` is sent before the first layout pass; ask native for
        # its best guess so the first commit lays out at the right size.
        try:
            viewport = _host_module().call("viewport", screen=screen_id)
        except Exception:
            viewport = None
        if isinstance(viewport, dict):
            payload = {**viewport, **payload}
    _publish_metrics(payload)
    width = float(payload.get("width") or 0.0)
    height = float(payload.get("height") or 0.0)
    if width > 0 and height > 0:
        host._pending_viewport = (width, height)
    host.on_create()
    return _root_json(host)


def _entry_module() -> str:
    import os

    return os.environ.get("PN_ENTRY_MODULE") or "app.main"


def _root_json(host: ScreenHost) -> str:
    tag = getattr(host.root_native_view, "tag", None)
    return codec.dumps({"root": None if tag is None else int(tag)})


def _reset_for_tests() -> None:
    global _flush_pending
    _HOSTS.clear()
    _SCHEDULED.clear()
    _flush_pending = False
