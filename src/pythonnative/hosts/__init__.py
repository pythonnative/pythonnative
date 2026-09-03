"""Screen hosts: the bridge between a native screen and the reconciler.

On device the native runtime creates screens through the bridge
(``callback("host", screen_id, "create", {...})``), which lands in
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost]. Off device,
``pn preview`` creates a
[`DesktopScreenHost`][pythonnative.hosts.desktop.DesktopScreenHost]
through [`create_screen`][pythonnative.hosts.create_screen], and unit
tests use the headless base [`ScreenHost`][pythonnative.hosts.ScreenHost]
with a fake backend.
"""

from __future__ import annotations

from typing import Any, Optional, Type

from ..utils import IS_ANDROID, IS_DESKTOP, IS_IOS
from .base import ScreenHost, import_component

__all__ = ["ScreenHost", "create_screen", "host_class", "import_component"]


def host_class() -> Type[ScreenHost]:
    """The host class for the current runtime."""
    if IS_ANDROID or IS_IOS:
        from .native import NativeScreenHost

        return NativeScreenHost
    if IS_DESKTOP:
        from .desktop import DesktopScreenHost

        return DesktopScreenHost
    return ScreenHost


def create_screen(component_path: str, native_instance: Any = None, args_json: Optional[str] = None) -> ScreenHost:
    """Create the screen host for a root component.

    Args:
        component_path: ``"app.main"`` (the module's ``App`` is used) or a
            dotted path like ``"app.main.RootScreen"``. Imported lazily
            so the dev server can reload it.
        native_instance: The platform object owning the screen (the
            integer screen id on device, ``DesktopApp`` in the preview).
        args_json: Optional JSON launch arguments (pushed screens
            receive their navigation history here).

    Returns:
        A host ready for ``on_create`` and the other lifecycle calls.
    """
    component = import_component(component_path)
    host = host_class()(native_instance, component_path, component)
    if args_json:
        host.set_args(args_json)
    return host


def drain_desktop_scheduled_renders() -> None:
    """Drain deferred desktop renders (called by the preview's Tk loop)."""
    from .desktop import drain_desktop_scheduled_renders as drain

    drain()
