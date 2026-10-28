"""Breakpoint debugging through ``debugpy``, inside any dev client.

``pn start`` accepts Debug Adapter Protocol connections on
``127.0.0.1:5678`` and asks the selected dev client to start a debug
adapter. [`start`][pythonnative.devtools.debugger.start] runs ``debugpy``
with its adapter in this process (``in_process_debug_adapter=True``):
mobile platforms can't spawn the separate adapter process ``debugpy``
normally uses. The adapter listens on a localhost port, which the dev
server reaches directly (the browser preview runs in its own process) or
through the dev session's tunnel (devices).

On a device ``debugpy`` arrives through the dev session's package sync:
the dev server sends its Python sources, without the compiled speedups,
into the overlay's ``site-packages``. The pure-Python tracer is slower
than the compiled one, which only matters while a debugger is attached.

Path mapping makes breakpoints set in the editor bind on the device: the
dev server sends the host paths of the project, the ``pythonnative``
package, and the installed packages, and the device maps its own copies
to them.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["attached", "install_breakpoint_hook", "mark_dev_thread", "start"]

_port: Optional[int] = None
_lock = threading.Lock()


def mark_dev_thread(thread: Optional[threading.Thread] = None) -> None:
    """Keep the debugger from tracing or suspending a development thread.

    The dev client's network and tunnel threads carry the debugger's own
    traffic; pausing them at a breakpoint would freeze the session that
    reports the breakpoint. ``pydevd`` skips threads marked this way.
    """
    target = thread or threading.current_thread()
    try:
        setattr(target, "is_pydev_daemon_thread", True)
        setattr(target, "pydev_do_not_trace", True)
    except AttributeError:
        pass


def attached() -> bool:
    """Whether a debugger client is connected to this process."""
    if _port is None:
        return False
    try:
        import debugpy

        return bool(debugpy.is_client_connected())
    except Exception:
        return False


def _mappings(host_paths: Dict[str, Any]) -> List[Tuple[str, str]]:
    """``(host path, local path)`` pairs for ``pydevd``'s path translation."""
    from ..utils import overlay_root

    mappings: List[Tuple[str, str]] = []
    project = str(host_paths.get("project") or "")
    if project:
        host_app = os.path.join(project, "app")
        local_apps: List[str] = []
        overlay = overlay_root()
        if overlay:
            local_apps.append(os.path.join(overlay, "app"))
        app_module = sys.modules.get("app")
        for location in list(getattr(app_module, "__path__", []) or []):
            local_apps.append(str(location))
        for local in local_apps:
            if os.path.abspath(local) != os.path.abspath(host_app):
                mappings.append((host_app, os.path.abspath(local)))
    framework = str(host_paths.get("pythonnative") or "")
    if framework:
        local_framework = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.abspath(framework) != local_framework:
            mappings.append((framework, local_framework))
    overlay = overlay_root()
    for site in host_paths.get("site_packages") or []:
        if overlay:
            mappings.append((str(site), os.path.join(overlay, "site-packages")))
    return mappings


def start(host_paths: Optional[Dict[str, Any]] = None) -> int:
    """Start the in-process debug adapter (once) and return its port.

    Args:
        host_paths: ``{"project", "pythonnative", "site_packages"}`` on the
            developer's machine, for path mapping. ``None`` (the browser
            preview) needs no mapping.

    Raises:
        RuntimeError: When ``debugpy`` isn't importable here.
    """
    global _port
    with _lock:
        if _port is not None:
            return _port
        # The synced copy has no compiled speedups; tell pydevd not to look.
        os.environ.setdefault("PYDEVD_USE_CYTHON", "NO")
        os.environ.setdefault("PYDEVD_USE_FRAME_EVAL", "NO")
        # Embedded interpreters use frozen standard-library modules; the
        # warning about them is noise for application debugging.
        os.environ.setdefault("PYDEVD_DISABLE_FILE_VALIDATION", "1")
        try:
            import debugpy
        except ImportError as exc:
            raise RuntimeError(
                "debugpy isn't available in this app. `pn start` syncs it to dev clients from its own "
                "environment; install it there with `pip install debugpy`."
            ) from exc
        for thread in threading.enumerate():
            if thread.name.startswith(("pn-dev-", "pn-tunnel-", "pn-file-watcher")):
                mark_dev_thread(thread)
        debugpy.configure(subProcess=False)
        if host_paths:
            mappings = _mappings(host_paths)
            if mappings:
                try:
                    import pydevd_file_utils

                    pydevd_file_utils.setup_client_server_paths(mappings)
                except Exception:
                    pass
        _host, port = debugpy.listen(("127.0.0.1", 0), in_process_debug_adapter=True)
        _port = int(port)
        return _port


def install_breakpoint_hook(log: Any = None) -> None:
    """Make ``breakpoint()`` useful in a dev client.

    With a debugger attached it pauses there. Without one it reports the
    location and how to attach, instead of starting ``pdb`` with no
    terminal to read from.
    """

    def hook(*_args: Any, **_kwargs: Any) -> None:
        if attached():
            import debugpy

            debugpy.breakpoint()
            return
        frame = sys._getframe(1)
        from ..errors import project_path

        where = f"{project_path(frame.f_code.co_filename)}:{frame.f_lineno}"
        message = (
            f"[pn dev] breakpoint() at {where} was skipped: no debugger is attached. "
            "Attach with VS Code's 'PythonNative: Attach' (localhost:5678 on your computer)."
        )
        print(message, file=sys.stderr)

    setattr(hook, "__pn_dev_hook__", True)
    sys.breakpointhook = hook
