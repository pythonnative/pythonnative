"""Desktop preview runtime, the engine behind ``pn preview``.

``pn preview`` renders a PythonNative app in a real OS window using the
Tkinter backend ([`pythonnative.native_views.desktop`][pythonnative.native_views.desktop]),
with **instant Fast Refresh** on every file save. It exists to make the
inner development loop fast: see your UI and iterate in seconds without
booting a simulator or deploying to a device.

Architecture
------------
- A single Tk window holds one *stage* frame. Every screen on the
  navigation stack gets its own child container inside the stage; the
  desktop view handlers create widgets under the active container.
- [`DesktopApp`][pythonnative.preview.DesktopApp] owns the navigation
  stack of [`hosts`][pythonnative.hosts] and the push/pop/reset
  primitives a root ``Stack.Navigator`` reaches through the host's
  [`HostNavigator`][pythonnative.navigation.HostNavigator] methods.
- The Tk event loop runs on the main thread. A lightweight poll
  (`~60 Hz`) drains (a) UI work marshaled from the asyncio runtime
  thread via [`runtime.call_on_main_thread`][pythonnative.runtime.call_on_main_thread],
  (b) re-renders requested off-thread, and (c) file-change reloads.
- A background [`FileWatcher`][pythonnative.hot_reload.FileWatcher]
  detects ``.py`` edits and enqueues a reload onto the main thread.

This module imports ``tkinter`` and is only imported by the
``pn preview`` command, which sets ``PN_PLATFORM=desktop`` first.
"""

from __future__ import annotations

import os
import queue
import sys
import tkinter as tk
import traceback
from typing import Any, Callable, List, Optional, Tuple

# iPhone-ish logical-point window so layouts that assume a phone-sized
# viewport look right out of the box; resizable at runtime.
DEFAULT_WIDTH = 390
DEFAULT_HEIGHT = 844
_POLL_INTERVAL_MS = 16
_WATCH_INTERVAL_S = 0.4


def _publish_desktop_color_scheme() -> None:
    """Publish the host OS appearance so `use_color_scheme` works in preview.

    ``PN_COLOR_SCHEME=light|dark`` forces a value (handy for testing
    both appearances); otherwise macOS is asked via ``defaults read``
    (the key only exists when dark mode is on). Other platforms default
    to light.
    """
    from . import appearance

    forced = os.environ.get("PN_COLOR_SCHEME")
    if forced in ("light", "dark"):
        appearance.set_system_color_scheme(forced)
        return
    if sys.platform == "darwin":
        import subprocess

        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            is_dark = result.returncode == 0 and result.stdout.strip() == "Dark"
            appearance.set_system_color_scheme("dark" if is_dark else "light")
        except Exception:
            pass


class DesktopApp:
    """Navigation-stack controller for the desktop preview window.

    One instance backs a preview session. It is handed to each
    [`DesktopScreenHost`][pythonnative.hosts.desktop.DesktopScreenHost] as the ``native_instance`` so
    hosts can drive navigation (``push_screen`` / ``pop_screen`` /
    ``reset_to_root``), report the viewport size, and set the window
    title, mirroring the role a ``UIViewController`` / ``Activity``
    plays on device.
    """

    def __init__(self, root: Any, stage: Any, width: float, height: float) -> None:
        self._root = root
        self._stage = stage
        self._width = float(width)
        self._height = float(height)
        self._stack: List[Any] = []
        self._error_widget: Any = None
        self._mount_failed = False
        self._component_path = ""

    # -- queried by the screen host -----------------------------------

    def viewport_size(self) -> Tuple[float, float]:
        """Return the current stage size in points (host viewport)."""
        return (self._width, self._height)

    def set_title(self, title: str) -> None:
        """Set the preview window title (called from screen options)."""
        try:
            self._root.title(title)
        except Exception:
            pass

    # -- container management -----------------------------------------

    def _new_container(self) -> Any:
        frame = tk.Frame(self._stage, highlightthickness=0, bd=0, background="#ffffff")
        frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        frame.lift()
        return frame

    def _show_container(self, host: Any) -> None:
        container = getattr(host, "container", None)
        if container is not None:
            try:
                container.place(in_=self._stage, x=0, y=0, relwidth=1.0, relheight=1.0)
                container.lift()
            except Exception:
                pass

    def _forget_container(self, host: Any) -> None:
        container = getattr(host, "container", None)
        if container is not None:
            try:
                container.place_forget()
            except Exception:
                pass

    def _activate(self, host: Any) -> None:
        """Make ``host`` the rendering target and reflow it to the viewport."""
        from .native_views import desktop as desktop_backend

        desktop_backend.set_root_container(getattr(host, "container", None))
        self._show_container(host)

    # -- lifecycle ----------------------------------------------------

    def _make_host(self, component_path: str, args: Optional[dict] = None) -> Any:
        from .hosts import create_screen
        from .native_views import desktop as desktop_backend

        container = self._new_container()
        desktop_backend.set_root_container(container)
        host = create_screen(component_path, self)
        host.container = container
        if args:
            host.set_args(args)
        return host

    def mount_root(self, component_path: str) -> None:
        """Mount the initial screen as the base of the navigation stack.

        Import-time failures (a missing dependency, a syntax error the
        developer is mid-fix on) are shown as an error overlay and flagged
        so the next successful reload remounts cleanly, rather than
        crashing the preview process.
        """
        self._component_path = component_path
        self._clear_error()
        try:
            host = self._make_host(component_path)
        except Exception:
            self._mount_failed = True
            self._show_error(traceback.format_exc())
            return
        self._stack.append(host)
        try:
            host.on_create()
            host.on_resume()
            self._mount_failed = False
        except Exception:
            self._mount_failed = True
            self._show_error(traceback.format_exc())

    def push_screen(self, component_path: str, args: Optional[dict] = None, options: Optional[dict] = None) -> None:
        """Push a new screen, suspending the current one (root stack navigation)."""
        if self._stack:
            current = self._stack[-1]
            try:
                current.on_pause()
            except Exception:
                pass
            self._forget_container(current)
        try:
            host = self._make_host(component_path, args)
        except Exception:
            self._show_error(traceback.format_exc())
            return
        self._stack.append(host)
        try:
            host.on_create()
            host.on_resume()
            if options and options.get("title"):
                self.set_title(str(options["title"]))
        except Exception:
            self._show_error(traceback.format_exc())

    def pop_screen(self) -> None:
        """Pop the top screen and restore the one beneath it."""
        if len(self._stack) <= 1:
            return
        top = self._stack.pop()
        self._teardown(top)
        restored = self._stack[-1]
        self._activate(restored)
        try:
            restored.on_resume()
            restored.set_viewport_size(self._width, self._height)
        except Exception:
            pass

    def reset_to_root(self) -> None:
        """Pop every screen above the root (declarative ``reset`` / tab root)."""
        while len(self._stack) > 1:
            self._teardown(self._stack.pop())
        if self._stack:
            root_host = self._stack[0]
            self._activate(root_host)
            try:
                root_host.on_resume()
                root_host.set_viewport_size(self._width, self._height)
            except Exception:
                pass

    def _teardown(self, host: Any) -> None:
        try:
            host.on_pause()
        except Exception:
            pass
        # ``on_destroy`` unmounts the host's reconciler: effect cleanups
        # run, native widgets are destroyed, and event registrations are
        # released.
        try:
            host.on_destroy()
        except Exception:
            pass
        container = getattr(host, "container", None)
        if container is not None:
            try:
                container.destroy()
            except Exception:
                pass

    def teardown_all(self) -> None:
        """Destroy every screen on the stack (preview window closing)."""
        while self._stack:
            self._teardown(self._stack.pop())

    def back_pressed(self) -> None:
        """Route a desktop back gesture (Escape) like a hardware back press.

        ``use_back_handler`` subscribers on the active screen get the
        first chance to consume the event; otherwise the stack pops
        (matching Android's default back behavior). At the root the
        event is ignored.
        """
        host = self.active_host()
        if host is None:
            return
        try:
            if host.on_back_pressed():
                return
        except Exception:
            pass
        self.pop_screen()

    # -- viewport / resize --------------------------------------------

    def resize(self, width: float, height: float) -> None:
        """Propagate a window resize to the active screen's reconciler."""
        if width <= 0 or height <= 0:
            return
        self._width = float(width)
        self._height = float(height)
        host = self.active_host()
        if host is not None:
            try:
                host.set_viewport_size(self._width, self._height)
            except Exception:
                pass

    def active_host(self) -> Any:
        """Return the top-of-stack host, or ``None`` if nothing is mounted."""
        return self._stack[-1] if self._stack else None

    # -- hot reload ---------------------------------------------------

    def reload(self, changed_modules: Optional[List[str]] = None) -> None:
        """Apply a hot reload across every mounted screen.

        If the initial mount failed (e.g. a syntax error the developer
        is now fixing), this re-attempts a fresh mount so the preview
        recovers without a restart. Otherwise each host on the stack
        performs Fast Refresh against the reloaded modules.
        """
        from .native_views import desktop as desktop_backend

        if self._mount_failed or not self._stack:
            self._remount_root()
            return

        self._clear_error()
        for host in self._stack:
            desktop_backend.set_root_container(getattr(host, "container", None))
            try:
                host.reload(changed_modules)
            except Exception:
                self._show_error(traceback.format_exc())
        active = self.active_host()
        if active is not None:
            desktop_backend.set_root_container(getattr(active, "container", None))

    def _remount_root(self) -> None:
        for host in list(self._stack):
            self._teardown(host)
        self._stack.clear()
        self.mount_root(self._component_path)

    # -- error overlay ------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._clear_error()
        widget = tk.Text(
            self._stage,
            wrap="word",
            background="#1c1c1e",
            foreground="#ff6b6b",
            insertbackground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            padx=16,
            pady=16,
        )
        widget.insert("1.0", "PythonNative preview error\n\n" + message)
        widget.configure(state="disabled")
        widget.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        widget.lift()
        self._error_widget = widget
        print(message, file=sys.stderr)

    def _clear_error(self) -> None:
        if self._error_widget is not None:
            try:
                self._error_widget.destroy()
            except Exception:
                pass
            self._error_widget = None


def _resolve_paths(component_path: str, project_root: Optional[str], watch_dir: Optional[str]) -> Tuple[str, str]:
    """Return ``(project_root, watch_dir)`` with sensible defaults.

    The project root (which must be importable for ``component_path`` to
    resolve) is prepended to ``sys.path``; the watch dir defaults to the
    top-level package directory of ``component_path`` under the root.
    """
    root = os.path.abspath(project_root or os.getcwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    if watch_dir is None:
        top_package = component_path.split(".", 1)[0]
        candidate = os.path.join(root, top_package)
        watch_dir = candidate if os.path.isdir(candidate) else root
    return root, os.path.abspath(watch_dir)


def run_preview(
    component_path: str,
    *,
    project_root: Optional[str] = None,
    watch_dir: Optional[str] = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    title: str = "PythonNative Preview",
    hot_reload: bool = True,
) -> None:
    """Open the preview window for ``component_path`` and run until closed.

    Args:
        component_path: Module path (``"app.main"`` → its ``App``) or a
            dotted ``module.Component`` path, same convention as
            [`create_screen`][pythonnative.hosts.create_screen].
        project_root: Directory added to ``sys.path`` so the component
            imports. Defaults to the current working directory.
        watch_dir: Directory watched for ``.py`` changes. Defaults to
            the component's top-level package (e.g. ``app/``).
        width: Initial window width in points.
        height: Initial window height in points.
        title: Window title.
        hot_reload: Watch for file changes and Fast Refresh on save.

    Raises:
        RuntimeError: If ``PN_PLATFORM=desktop`` was not set before
            PythonNative was imported (``pn preview`` sets it for you).
    """
    from . import runtime as runtime_module
    from .native_views import desktop as desktop_backend
    from .utils import IS_DESKTOP

    if not IS_DESKTOP:
        raise RuntimeError(
            "run_preview() requires the desktop backend. Set PN_PLATFORM=desktop "
            "before importing pythonnative (the `pn preview` command does this)."
        )

    root_dir, watched = _resolve_paths(component_path, project_root, watch_dir)
    _publish_desktop_color_scheme()

    # The preview is inherently a development surface: turn on dev
    # diagnostics (validation warnings, hook-order checks, RedBox).
    from . import diagnostics

    diagnostics.set_dev_mode(True)

    root = tk.Tk()
    root.title(title)
    root.geometry(f"{int(width)}x{int(height)}")
    root.minsize(240, 320)
    stage = tk.Frame(root, background="#ffffff", highlightthickness=0, bd=0)
    stage.pack(fill="both", expand=True)
    desktop_backend.set_root_container(stage)

    app = DesktopApp(root, stage, width, height)

    # Marshal asyncio-thread UI work (animations, alerts) onto the Tk
    # main thread by funneling it through this queue, drained in _poll.
    main_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
    runtime_module.set_desktop_main_dispatch(main_queue.put)

    app.mount_root(component_path)

    def _on_configure(event: Any) -> None:
        if event.widget is stage:
            app.resize(event.width, event.height)

    stage.bind("<Configure>", _on_configure)

    # Escape acts as the desktop stand-in for the hardware back button:
    # ``use_back_handler`` subscribers can intercept it, and otherwise
    # the navigation stack pops.
    root.bind("<Escape>", lambda _event: app.back_pressed())

    watcher = _build_watcher(watched, root_dir, app, main_queue) if hot_reload else None
    if watcher is not None:
        watcher.start()
        print(f"[pn preview] watching {watched} for changes", file=sys.stderr)

    from .hosts import drain_desktop_scheduled_renders

    def _poll() -> None:
        for _ in range(128):
            try:
                job = main_queue.get_nowait()
            except queue.Empty:
                break
            try:
                job()
            except Exception:
                traceback.print_exc()
        try:
            drain_desktop_scheduled_renders()
        except Exception:
            traceback.print_exc()
        try:
            root.after(_POLL_INTERVAL_MS, _poll)
        except Exception:
            pass

    def _on_close() -> None:
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                pass
        # Unmount every screen first so effect cleanups (timers, tasks,
        # subscriptions) run before the Tk interpreter goes away.
        try:
            app.teardown_all()
        except Exception:
            pass
        runtime_module.set_desktop_main_dispatch(None)
        desktop_backend.clear_root_container()
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.after(_POLL_INTERVAL_MS, _poll)
    print(f"[pn preview] {component_path} ({int(width)}x{int(height)})", file=sys.stderr)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                pass
        runtime_module.set_desktop_main_dispatch(None)
        desktop_backend.clear_root_container()


def _build_watcher(
    watch_dir: str,
    base_dir: str,
    app: DesktopApp,
    main_queue: "queue.Queue[Callable[[], None]]",
) -> Any:
    """Create a file watcher that enqueues reloads onto the main thread.

    The watcher runs on its own daemon thread; because Tkinter is not
    thread-safe, the ``on_change`` callback only *enqueues* the reload
    (translated from changed file paths into dotted module names), which
    [`run_preview`][pythonnative.preview.run_preview]'s poll loop runs
    on the Tk main thread.
    """
    from .hot_reload import FileWatcher, ModuleReloader

    def _on_change(changed_files: List[str]) -> None:
        modules: List[str] = []
        for path in changed_files:
            module = ModuleReloader.file_to_module(path, base_dir)
            if module:
                modules.append(module)

        def _apply() -> None:
            print(f"[pn preview] reloading: {', '.join(modules) or 'app'}", file=sys.stderr)
            app.reload(modules)

        main_queue.put(_apply)

    return FileWatcher(watch_dir, _on_change, interval=_WATCH_INTERVAL_S)
