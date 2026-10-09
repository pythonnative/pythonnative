"""Development server and browser preview.

The browser is a protocol-4 renderer with Yoga WebAssembly layout. Python runs
on the standard application asyncio loop; the transport's coordinator and
network threads forward messages to their owners. The dev server watches app
sources, synchronizes mobile clients, and applies compatible Fast Refresh.

PN_PLATFORM=web must be set before importing pythonnative; the CLI launches a
child process with that environment when needed.
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
        config: Any = None,
        debug_port: Optional[int] = None,
    ) -> None:
        from .bridge.web import WebTransport
        from .devserver import DevServer

        self.project_root = os.path.abspath(project_root)
        self.entry_module = entry_module
        self.log: Logger = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self.server = DevServer(
            self.project_root,
            entry_module,
            host=host,
            port=port,
            project_name=project_name,
            log=self.log,
            config=config,
            debug_port=debug_port,
            open_devtools=self.open_devtools,
        )
        self.transport = WebTransport(log=self.log)
        self.transport.on_peer_changed = self._on_peer_changed
        self.transport.on_dev_message = self._on_dev_message
        self._stop = threading.Event()
        self._unsubscribe: Optional[Callable[[], None]] = None
        self._stdout: Any = None

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
        from .runtime import start as start_runtime

        start_runtime()
        self.server.set_preview_channel(self.transport)
        self._unsubscribe = self.server.add_change_listener(self._on_sources_changed)
        self.server.start()
        self._install_devtools()

    def _install_devtools(self) -> None:
        """Serve DevTools for the preview from this process."""
        from . import devtools
        from .devtools.debugger import install_breakpoint_hook, mark_dev_thread

        agent = devtools.install(lambda topic, data: self.server.publish_local("preview", topic, data), kind="preview")
        self.server.preview_target(agent)
        install_breakpoint_hook()
        # The server's threads carry the debugger's traffic; never pause them.
        for thread in threading.enumerate():
            if thread.name in ("pn-dev-server", "pn-file-watcher"):
                mark_dev_thread(thread)
        # The app's print() output goes to stdout (the server logs to
        # stderr); mirror it to DevTools' console.
        from .devclient import _Tee

        self._stdout = sys.stdout
        sys.stdout = _Tee(
            self._stdout, lambda line: self.server.publish_local("preview", "log", {"level": "info", "text": line})
        )

    def open_devtools(self) -> None:
        """Open DevTools in the developer's browser (from any thread)."""
        try:
            webbrowser.open(self.server.info.devtools_url("localhost"))
        except Exception:
            pass

    def run(self) -> None:
        """Run the main loop until ``stop`` (or Ctrl+C)."""
        try:
            self.transport.run_main_loop(until=self._stop.is_set)
        except KeyboardInterrupt:
            pass

    def stop_soon(self) -> None:
        """Ask [`run`][pythonnative.preview.PreviewSession.run] to return (from any thread)."""
        self._stop.set()

    def stop(self) -> None:
        """Tear everything down."""
        self._stop.set()
        if self._stdout is not None:
            sys.stdout = self._stdout
            self._stdout = None
        from . import devtools

        devtools.uninstall()
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
        from .assets import bump_generation, manifest_for_sync
        from .devserver.watcher import modules_for_paths

        paths = list(change.changed) + list(change.removed)
        modules = modules_for_paths(paths)
        assets_changed = bool(manifest_for_sync(paths))
        if not modules and not assets_changed:
            return

        def _apply() -> None:
            from .hosts import live_hosts
            from .hot_reload import apply_reload

            if assets_changed:
                # The page re-reads the manifest and font CSS, then reloads
                # every ``asset://`` image it shows.
                bump_generation()
                self.transport.send_dev({"type": "assets"})
            if not modules:
                return
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
            self.server.publish_local("preview", "reload", {"mode": result.mode, "modules": result.reloaded})
            label = "Fast Refresh" if result.mode == "fast_refresh" else "Remounted"
            self.log(f"[pn] {label}: {', '.join(result.reloaded)} ({elapsed_ms:.0f} ms)")
            self.transport.send_dev(
                {"type": "reload", "ok": True, "mode": result.mode, "modules": result.reloaded, "ms": elapsed_ms}
            )

        self.transport.post_to_application(_apply)

    # -- peers -------------------------------------------------------------

    def _on_peer_changed(self, connected: bool) -> None:
        if connected:
            self.log("[pn] browser preview connected")
            self.transport.post_to_application(self._remount_for_new_page)
            return
        self.log("[pn] browser preview disconnected")
        self._destroy_hosts()

    def _remount_for_new_page(self) -> None:
        """Start a page's session on a fresh surface (application thread).

        A page that went away can leave a commit in flight, which the
        transport rejects after the disconnect was handled; the surface
        must be reset once that commit settles, or the next page's mount
        fails on a surface marked as failed.
        """
        import asyncio
        from contextlib import suppress

        from .native_views import get_backend

        async def run() -> None:
            backend = get_backend()
            waiting = [getattr(backend, "_pending", None), *getattr(backend, "_queued_commits", ())]
            for future in waiting:
                if future is not None and not future.done():
                    with suppress(BaseException):
                        await future
            self._destroy_hosts()
            self._send_hello()

        asyncio.get_running_loop().create_task(run())

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
        from .native_views import get_backend

        for host in list(live_hosts()):
            try:
                host.on_destroy()
            except Exception:
                traceback.print_exc()
        backend = get_backend()
        reset = getattr(backend, "reset", None)
        if callable(reset):
            try:
                reset()
            except Exception as exc:
                # A commit is still in flight; the next page resets once it settles.
                self.log(f"[pn] surface reset deferred: {exc}")

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
        """Every URL the server can be reached at (local first), each carrying the dev token."""
        from .devserver import lan_addresses

        info = self.server.info
        urls = [info.preview_url("localhost")]
        for address in lan_addresses():
            url = info.preview_url(address)
            if url not in urls:
                urls.append(url)
        return urls


def banner_lines(session: PreviewSession, title: str) -> List[str]:
    """The ``pn start`` banner: a QR code for the connect link, then the URLs."""
    from .devserver import lan_addresses
    from .devserver.auth import token_source
    from .devserver.qr import encode, to_terminal

    server = session.server
    info = server.info
    lan = next(iter(lan_addresses()), None)
    links = server.connect_links(lan)
    lines = ["", f"  PythonNative dev server for {title}", ""]
    try:
        code = to_terminal(encode(str(links["preferred"])), border=2)
        lines.extend("  " + row for row in code.rstrip("\n").split("\n"))
    except ValueError:
        pass
    target = "PythonNative Go" if links.get("go_compatible", True) or "app" not in links else "your development build"
    lines += [
        f"  Scan with your phone's camera to open it in {target}.",
        "",
        f"  Browser preview:  {info.preview_url('localhost')}",
        f"  DevTools:         {info.devtools_url('localhost')}",
    ]
    if lan:
        lines.append(f"  Devices (LAN):    {info.connect_url(lan)}")
    if server.debug_port:
        lines.append(f"  Debugger:         127.0.0.1:{server.debug_port} (VS Code: 'PythonNative: Attach')")
    lines += ["", f"  The URLs carry your dev token ({token_source()}); keep them to your own devices.", ""]
    return lines


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
    config: Any = None,
    debug_port: Optional[int] = None,
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
        ready: Called once the server is listening (the CLI starts its
            key handler here; tests use it to drive the session).
        config: The project's ``AppConfig`` (compatibility checks,
            package sync, connect links).
        debug_port: Port of the debugger proxy, or ``None`` for none.

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
        config=config,
        debug_port=debug_port,
    )
    session.start()
    urls = session.urls()
    if banner:
        for line in banner_lines(session, project_name or entry_module):
            session.log(line)
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
