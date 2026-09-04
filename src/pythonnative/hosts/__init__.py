"""Screen hosts: the bridge between a native screen and the reconciler.

On every bridge platform (iOS, Android, and the browser preview) the
native runtime creates screens through the bridge
(``callback("host", screen_id, "create", {...})``), which lands in
[`NativeScreenHost`][pythonnative.hosts.native.NativeScreenHost]. Unit
tests use the headless base [`ScreenHost`][pythonnative.hosts.ScreenHost]
with a fake backend, created through
[`create_screen`][pythonnative.hosts.create_screen].
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Type

from ..utils import IS_NATIVE
from .base import ScreenHost, import_component

__all__ = ["ScreenHost", "create_screen", "host_class", "import_component", "live_hosts"]


def host_class() -> Type[ScreenHost]:
    """The host class for the current runtime."""
    if IS_NATIVE:
        from .native import NativeScreenHost

        return NativeScreenHost
    return ScreenHost


def create_screen(component_path: str, native_instance: Any = None, args_json: Optional[str] = None) -> ScreenHost:
    """Create the screen host for a root component.

    Args:
        component_path: ``"app.main"`` (the module's ``App`` is used) or a
            dotted path like ``"app.main.RootScreen"``. Imported lazily
            so the dev server can reload it.
        native_instance: The platform object owning the screen (the
            integer screen id on the bridge platforms).
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


def live_hosts() -> Sequence[ScreenHost]:
    """Every screen host currently mounted by the native runtime.

    Returns an empty sequence off the bridge platforms; tests hold their
    own host references.
    """
    if not IS_NATIVE:
        return []
    from .native import live_hosts as native_live_hosts

    return list(native_live_hosts())
