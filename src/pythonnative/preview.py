"""``pn start`` / ``pn preview``: the dev server plus the browser preview.

[`serve`][pythonnative.preview.serve] runs one process that does three
jobs:

1. **Dev server** (``pythonnative.devserver``): watches ``app/``, syncs
   sources to every connected dev client (simulators, emulators,
   physical devices), and relays their logs to this terminal.
2. **Browser preview**: renders the app in a browser tab. The tab is a
   bridge peer like any device; the reconciler runs in *this* process
   on the main thread and commits through
   [`WebTransport`][pythonnative.bridge.web.WebTransport].
3. **Fast Refresh** for the preview: every save reloads the changed
   modules here and refreshes the mounted screens, exactly as the dev
   client does on device.

The main thread runs the transport's main loop; that is the browser's
stand-in for the UIKit / Android main queue. Everything else (sockets,
the file watcher) lives on daemon threads and marshals work onto it.

``PN_PLATFORM=web`` must be set before ``pythonnative`` is imported so
platform detection binds to the browser backend; the CLI re-execs
itself to guarantee that.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
import webbrowser
from typing import Any, Callable, Dict, List, Optional

__all__ = ["PreviewSession", "serve"]

Logger = Callable[[str], None]


class PreviewSession:
    """Everything one ``pn start`` invocation owns; see [`serve`][pythonnative.preview.serve]."""

    def __init__(
        self,
        project_root: str,
        entry_module: str,
        *,
        host: str = "0.0.0.0",
        port: int = 8765,
        project_name: str = "",
        log: Optional[Logger] = None,
    ) -> None:
        from .bridge.web import WebTransport
        from .devserver import DevServer

        self.project_root = os.path.abspath(project_root)
        self.entry_module = entry_module
        self.log: Logger = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self.server = DevServer(
            self.project_root, entry_module, host=host, port=port, project_name=project_name, log=self.log
        )
        self.transport = WebTransport(log=self.log)
        self.transport.on_peer_changed = self._on_peer_changed
        self.transport.on_dev_message = self._on_dev_message
        self._stop = threading.Event()
        self._unsubscribe: Optional[Callable[[], None]] = None

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Install the transport, start the server, and begin watching."""
        from . import bridge, diagnostics
        from .utils import IS_WEB

        if not IS_WEB:
            raise RuntimeError(
                "The browser preview needs PN_PLATFORM=web before pythonnative is imported "
                "(`pn start` and `pn preview` set it for you)."
            )
        if self.project_root not in sys.path:
            sys.path.insert(0, self.project_root)
        os.environ.setdefault("PN_ENTRY_MODULE", self.entry_module)
        os.environ.setdefault("PN_STORAGE_DIR", os.path.join(self.project_root, "build", "preview", "storage"))
        diagnostics.set_dev_mode(True)
        # Bottom of the reporter stack: screens register their own RedBox
        # above this, so it only sees errors raised before a screen exists
        # (a failing import of the entry module, say).
        diagnostics.set_error_reporter(self, self._report_error)
        bridge.set_transport(self.transport)
        # Warm the guest loop on this thread so it is owned by the main thread.
        from .runtime import get_loop

        get_loop()
        self.server.set_preview_channel(self.transport)
        self._unsubscribe = self.server.add_change_listener(self._on_sources_changed)
        self.server.start()

    def run(self) -> None:
        """Run the main loop until ``stop`` (or Ctrl+C)."""
        try:
            self.transport.run_main_loop(until=self._stop.is_set)
        except KeyboardInterrupt:
            pass

    def stop(self) -> None:
        """Tear everything down."""
        self._stop.set()
        self.transport.stop()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        try:
            self._destroy_hosts()
        except Exception:
            pass
        self.server.stop()
        from . import bridge, diagnostics

        diagnostics.set_error_reporter(self, None)
        bridge.set_transport(None)

    # -- source changes ----------------------------------------------------

    def _on_sources_changed(self, change: Any, snapshot: Any) -> None:
        """Watcher thread: schedule a reload of the preview's own app."""
        from .devserver.watcher import modules_for_paths

        modules = modules_for_paths(list(change.changed) + list(change.removed))
        if not modules:
            return

        def _apply() -> None:
            from .hosts import live_hosts
            from .hot_reload import apply_reload

            hosts = list(live_hosts())
            started = time.monotonic()
            result = apply_reload(modules, hosts)
            elapsed_ms = (time.monotonic() - started) * 1000.0
            if result.mode == "error":
                self.log("[pn] reload failed:")
                for line in (result.error or "").rstrip().split("\n"):
                    self.log(f"    {line}")
                self.transport.send_dev({"type": "reload", "ok": False, "error": result.error, "modules": modules})
                return
            if result.mode == "none":
                return
            label = "Fast Refresh" if result.mode == "fast_refresh" else "Remounted"
            self.log(f"[pn] {label}: {', '.join(result.reloaded)} ({elapsed_ms:.0f} ms)")
            self.transport.send_dev(
                {"type": "reload", "ok": True, "mode": result.mode, "modules": result.reloaded, "ms": elapsed_ms}
            )

        self.transport.post_to_main(_apply)

    # -- peers -------------------------------------------------------------

    def _on_peer_changed(self, connected: bool) -> None:
        if connected:
            self.log("[pn] browser preview connected")
            self._send_hello()
            return
        self.log("[pn] browser preview disconnected")
        self._destroy_hosts()

    def _send_hello(self) -> None:
        """Tell the page what to mount; it answers by creating the entry screen."""
        self.transport.send_dev(
            {
                "type": "hello",
                "entry": self.entry_module,
                "project": self.server.project_name or os.path.basename(self.project_root),
            }
        )

    def _report_error(self, exc: BaseException, phase: str) -> None:
        """Print an error to the terminal and mirror it into the preview page."""
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
        self.log(f"[pn] error during {phase}:")
        for line in text.split("\n"):
            self.log(f"    {line}")
        self.transport.send_dev({"type": "error", "phase": phase, "text": text})

    def _destroy_hosts(self) -> None:
        """Unmount every screen the page created (it is gone, so are its views)."""
        from .hosts.native import live_hosts
        from .native_views import get_registry

        for host in list(live_hosts()):
            try:
                host.on_destroy()
            except Exception:
                traceback.print_exc()
        backend = get_registry()
        reset = getattr(backend, "reset", None)
        if callable(reset):
            reset()

    def _on_dev_message(self, payload: Dict[str, Any]) -> None:
        kind = payload.get("type")
        if kind == "log":
            self.log(f"[browser] {payload.get('text', '')}")
        elif kind == "error":
            self.log(f"[browser error] {payload.get('text', '')}")
        elif kind == "hello":
            agent = str(payload.get("user_agent", ""))
            device = payload.get("device", "")
            size = f"{payload.get('width', '?')}x{payload.get('height', '?')}"
            self.log(f"[pn] preview page: {device} {size} ({_browser_family(agent)})")
        elif kind == "remount":
            self.log("[pn] remounting the app")
            self._destroy_hosts()
            self._send_hello()

    # -- info ----------------------------------------------------------------

    def urls(self) -> List[str]:
        """Every URL the server can be reached at (local first)."""
        from .devserver import lan_addresses

        info = self.server.info
        urls = [info.url("localhost")]
        for address in lan_addresses():
            url = info.url(address)
            if url not in urls:
                urls.append(url)
        return urls


def _browser_family(user_agent: str) -> str:
    agent = user_agent.lower()
    for needle, name in (("firefox", "Firefox"), ("edg/", "Edge"), ("chrome", "Chrome"), ("safari", "Safari")):
        if needle in agent:
            return name
    return "browser"


def serve(
    entry_module: str,
    *,
    project_root: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8765,
    project_name: str = "",
    open_browser: bool = False,
    log: Optional[Logger] = None,
    banner: bool = True,
    ready: Optional[Callable[[PreviewSession], None]] = None,
) -> None:
    """Run the dev server (and browser preview) until interrupted.

    Args:
        entry_module: The app's entry module (``"app.main"``).
        project_root: Directory containing ``app/``; defaults to the
            current directory. Added to ``sys.path``.
        host: Bind address (``0.0.0.0`` so devices can connect).
        port: TCP port (``0`` picks a free one).
        project_name: Shown in the preview page.
        open_browser: Open the preview page in the default browser.
        log: Where status lines go (stderr by default).
        banner: Print the connection banner.
        ready: Called once the server is listening (tests).

    Raises:
        RuntimeError: If ``PN_PLATFORM=web`` was not set before
            PythonNative was imported (the CLI sets it for you).
        OSError: If the port is taken.
    """
    session = PreviewSession(
        project_root or os.getcwd(),
        entry_module,
        host=host,
        port=port,
        project_name=project_name,
        log=log,
    )
    session.start()
    urls = session.urls()
    if banner:
        emit = session.log
        emit("")
        emit(f"  PythonNative dev server for {project_name or entry_module}")
        emit("")
        emit(f"  Browser preview:  {urls[0]}")
        for url in urls[1:]:
            emit(f"  Devices (LAN):    {url}")
        emit("")
        emit("  Debug builds made with `pn run` connect here automatically.")
        emit("  Press Ctrl+C to stop.")
        emit("")
    if open_browser:
        try:
            webbrowser.open(urls[0])
        except Exception:
            pass
    if ready is not None:
        ready(session)
    try:
        session.run()
    finally:
        session.stop()
