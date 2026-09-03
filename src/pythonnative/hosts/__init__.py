"""Screen hosts: the bridge between a native screen and the reconciler.

Native templates create one host per screen:

```python
host = pythonnative.hosts.create_screen("app.main", native_instance, args_json)
host.on_create()
```

and forward lifecycle events to it. The concrete class depends on the
runtime ([`AndroidScreenHost`][pythonnative.hosts.android.AndroidScreenHost],
[`IOSScreenHost`][pythonnative.hosts.ios.IOSScreenHost],
[`DesktopScreenHost`][pythonnative.hosts.desktop.DesktopScreenHost]);
the headless base [`ScreenHost`][pythonnative.hosts.ScreenHost] is used
in unit tests with a fake backend.
"""

from __future__ import annotations

from typing import Any, Optional, Type

from ..utils import IS_ANDROID, IS_DESKTOP, IS_IOS
from .base import ScreenHost, import_component

__all__ = ["ScreenHost", "create_screen", "host_class", "import_component"]


def host_class() -> Type[ScreenHost]:
    """The host class for the current runtime."""
    if IS_ANDROID:
        from .android import AndroidScreenHost

        return AndroidScreenHost
    if IS_DESKTOP:
        from .desktop import DesktopScreenHost

        return DesktopScreenHost
    if IS_IOS:
        from .ios import IOSScreenHost

        return IOSScreenHost
    return ScreenHost


def create_screen(component_path: str, native_instance: Any = None, args_json: Optional[str] = None) -> ScreenHost:
    """Create the screen host for a root component.

    Args:
        component_path: ``"app.main"`` (the module's ``App`` is used) or a
            dotted path like ``"app.main.RootScreen"``. Imported lazily
            so the dev server can reload it.
        native_instance: The platform object owning the screen
            (``Activity``, ``UIViewController`` pointer, ``DesktopApp``).
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


def drain_ios_scheduled_renders() -> None:
    """Drain deferred iOS renders (called by the Swift template on the main thread)."""
    from .ios import drain_ios_scheduled_renders as drain

    drain()


def forward_lifecycle(native_addr: int, event: str) -> None:
    """Forward a Swift view-controller lifecycle event to its host."""
    from .ios import forward_lifecycle as forward

    forward(native_addr, event)


def drain_desktop_scheduled_renders() -> None:
    """Drain deferred desktop renders (called by the preview's Tk loop)."""
    from .desktop import drain_desktop_scheduled_renders as drain

    drain()
