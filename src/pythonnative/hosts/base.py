"""Platform-independent application surface host.

A host mounts one logical application tree, publishes native lifecycle and
viewport changes, schedules Python work on the application thread, and caches
navigation restoration state. Logical screen containers present the tree's
screen roots through native navigation controllers and fragments.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import diagnostics
from ..element import Element

__all__ = ["ScreenHost", "import_component"]


# ======================================================================
# Component resolution
# ======================================================================


def _missing_module_is_target(exc: ModuleNotFoundError, dotted: str) -> bool:
    """Whether ``exc`` means ``dotted`` itself is absent (vs. one of its imports)."""
    missing = exc.name or ""
    return missing == dotted or dotted.startswith(missing + ".")


def import_component(component_path: str) -> Any:
    """Import a root component by module path or dotted attribute path.

    ``"app.main"`` imports the module and returns its ``App`` attribute;
    ``"app.main.RootScreen"`` returns the named attribute. Errors raised
    *inside* a resolvable module (a missing third-party dependency, a
    syntax error) propagate unchanged so the real cause stays visible.

    Raises:
        ImportError: When neither form resolves.
    """
    try:
        module = importlib.import_module(component_path)
    except ModuleNotFoundError as exc:
        if not _missing_module_is_target(exc, component_path):
            raise
        module = None
    if module is not None:
        component = getattr(module, "App", None)
        if component is not None:
            return component

    if "." in component_path:
        module_path, attr = component_path.rsplit(".", 1)
        try:
            parent = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            if not _missing_module_is_target(exc, module_path):
                raise
            parent = None
        if parent is not None:
            component = getattr(parent, attr, None)
            if component is not None:
                return component

    raise ImportError(
        f"Could not resolve component {component_path!r}. Define a top-level `App` function in the "
        "module (e.g. `app/main.py`) or pass an explicit dotted path like `app.main.RootScreen`."
    )


# ======================================================================
# Host
# ======================================================================


class ScreenHost:
    """Base screen host; see the module docstring.

    Attributes:
        native_instance: The platform object owning this screen
            (an integer screen id on the bridge platforms).
        component_path: Import path of the root component.
        args: Launch arguments (``set_args``), including the serialized
            navigation state under ``"pn_nav"`` for pushed screens.
        reconciler: The mounted reconciler, or ``None`` before
            ``on_create`` / after ``on_destroy``.
        is_focused: Whether the screen is presented (``on_resume`` /
            ``on_pause``).
    """

    def __init__(self, native_instance: Any, component_path: str, component: Any) -> None:
        self.native_instance = native_instance
        self.component_path = component_path
        self.component = component
        self.args: Dict[str, Any] = {}
        self.reconciler: Any = None
        self.root_native_view: Any = None
        self.is_focused = True
        self._focus_listeners: List[Callable[[bool], None]] = []
        self._is_rendering = False
        self._render_queued = False
        self._render_scheduled = False
        self._redbox_visible = False
        self._refresh_task: asyncio.Task[Any] | None = None

    # ------------------------------------------------------------------
    # Platform primitives (override)
    # ------------------------------------------------------------------

    def _attach_root(self, native_view: Any) -> None:
        """Place ``native_view`` into the platform container."""

    def _detach_root(self, native_view: Any) -> None:
        """Remove ``native_view`` from the platform container."""

    def _initial_viewport_size(self) -> Optional[Tuple[float, float]]:
        """A plausible viewport size before the first layout (see ``_seed_viewport``)."""
        return None

    def _schedule_render_async(self) -> bool:
        """Defer a render to the platform's next UI turn; ``False`` renders inline."""
        return False

    def _show_error(self, payload: Dict[str, Any]) -> None:
        """Show a host-owned diagnostic view (native hosts override)."""

    def _dismiss_error(self) -> None:
        """Dismiss the platform diagnostic view."""

    def _native_set_options(self, options: Dict[str, Any]) -> None:
        """Apply header options (``title`` at minimum) to the native chrome."""

    # ------------------------------------------------------------------
    # HostNavigator protocol
    # ------------------------------------------------------------------

    def initial_navigation_state(self) -> Optional[Dict[str, Any]]:
        """Return the serialized navigation state from ``args["pn_nav"]``, or ``None`` for the first screen."""
        from ..navigation.host import initial_state_from_args

        return initial_state_from_args(self.args)

    def cache_navigation_state(self, state: Dict[str, Any]) -> None:
        """Publish a restorable immutable navigation snapshot to the native host."""
        from ..navigation.host import NAV_STATE_ARG

        self.args = dict(self.args or {}) | {NAV_STATE_ARG: state}

    def set_screen_options(self, options: Dict[str, Any]) -> None:
        """Apply header ``options`` (``title`` and friends) to the native chrome."""
        self._native_set_options(dict(options))

    def add_focus_listener(self, callback: Callable[[bool], None]) -> Callable[[], None]:
        """Subscribe to focus changes (``on_resume`` / ``on_pause``); returns an unsubscribe callable."""
        self._focus_listeners.append(callback)

        def remove() -> None:
            try:
                self._focus_listeners.remove(callback)
            except ValueError:
                pass

        return remove

    # ------------------------------------------------------------------
    # Lifecycle (called by the platform)
    # ------------------------------------------------------------------

    def on_create(self) -> None:
        """Mount the root component (idempotent across native view recreation).

        Android destroys and recreates a fragment's view when the user
        pops back to it and calls ``on_create`` again; the Python host
        persists, so an already-mounted tree is simply re-attached.
        """
        self._register_redbox_reporter()
        if self.reconciler is not None:
            if self.root_native_view is not None:
                self._attach_root(self.root_native_view)
            return

        self.reconciler = self._new_reconciler()
        self._seed_viewport()
        try:
            self._is_rendering = True
            try:
                self.root_native_view = self.reconciler.mount(self._root_element())
                if self.root_native_view is not None:
                    self._attach_root(self.root_native_view)
                self._drain_renders()
            finally:
                self._is_rendering = False
        except Exception as exc:
            if not diagnostics.is_dev():
                raise
            self.show_redbox(exc, phase="mount")

    def on_resume(self) -> None:
        """Mark the screen focused and notify focus listeners."""
        self.set_focused(True)

    def on_pause(self) -> None:
        """Mark the screen unfocused and notify focus listeners."""
        self.set_focused(False)

    def on_destroy(self) -> None:
        """Tear down: unmount (running effect cleanups), release native views."""
        self.clear_redbox(reattach=False)
        diagnostics.set_error_reporter(self, None)
        reconciler, self.reconciler = self.reconciler, None
        if reconciler is not None:
            try:
                reconciler.unmount()
            except Exception:
                diagnostics.log("on_destroy: reconciler.unmount() failed")
        root, self.root_native_view = self.root_native_view, None
        if root is not None:
            try:
                self._detach_root(root)
            except Exception:
                pass
        self._focus_listeners = []

    def on_back_pressed(self) -> bool:
        """Offer the system back action to ``use_back_handler`` subscribers.

        Returns ``True`` when a handler consumed the event, in which
        case the platform must not pop the screen.
        """
        if self.reconciler is None:
            return False
        try:
            return bool(self.reconciler.dispatch_back_press())
        except Exception as exc:
            if not diagnostics.report_error(exc, phase="back handler"):
                traceback.print_exc()
            return False

    def set_args(self, args: Any) -> None:
        """Record launch arguments (a dict or a JSON string)."""
        if isinstance(args, str):
            try:
                parsed = json.loads(args) or {}
            except Exception:
                parsed = {}
            self.args = parsed if isinstance(parsed, dict) else {}
            return
        self.args = args if isinstance(args, dict) else {}

    def set_focused(self, focused: bool) -> None:
        """Update ``is_focused`` and notify focus listeners when the value changes."""
        if self.is_focused == focused:
            return
        self.is_focused = focused
        for callback in list(self._focus_listeners):
            try:
                callback(focused)
            except Exception:
                pass

    def set_viewport_size(self, width: float, height: float) -> None:
        """Forward a viewport-size change (in points) to the reconciler."""
        if self.reconciler is None or width <= 0 or height <= 0:
            return
        self.reconciler.set_viewport_size(float(width), float(height))
        try:
            from .. import platform_metrics

            platform_metrics.set_window_dimensions(float(width), float(height))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _root_element(self) -> Element:
        from ..navigation.host import HostRoot

        self.component = import_component(self.component_path)
        return HostRoot(self.component(), host=self)

    def _new_reconciler(self) -> Any:
        from ..native_views import get_backend
        from ..reconciler import Reconciler

        reconciler = Reconciler(get_backend())
        reconciler.on_render_requested = self.request_render

        def mounted() -> None:
            if self.reconciler is not reconciler:
                return
            root = reconciler.root_view()
            if root is not self.root_native_view:
                if self.root_native_view is not None:
                    self._detach_root(self.root_native_view)
                self.root_native_view = root
                if root is not None:
                    self._attach_root(root)

        reconciler.on_commit = mounted

        def failed(error: BaseException) -> None:
            if diagnostics.is_dev():
                self.show_redbox(error, phase="native commit")
            else:
                from ..runtime import get_loop

                get_loop().call_exception_handler({"message": "Native commit failed", "exception": error})

        reconciler.on_commit_error = failed
        return reconciler

    def _seed_viewport(self) -> None:
        """Give the reconciler a plausible viewport before the first mount.

        The authoritative size arrives right after attach, but the mount
        commit has already run by then; without a viewport its layout
        pass is skipped and mount-time ``use_layout_effect`` callbacks
        would observe no frames.
        """
        try:
            size = self._initial_viewport_size()
        except Exception:
            return
        if size and size[0] > 0 and size[1] > 0:
            self.reconciler.set_viewport_size(float(size[0]), float(size[1]))

    def request_render(self) -> None:
        """Request a render pass (queued if one is in progress)."""
        if self.reconciler is None:
            return
        if self._is_rendering:
            self._render_queued = True
            return
        if self._schedule_render_async():
            return
        self._re_render()

    def flush_scheduled_render(self) -> None:
        """Run a render deferred by ``_schedule_render_async`` (platform UI turn)."""
        self._render_scheduled = False
        if self.reconciler is None:
            return
        if self._is_rendering:
            self._render_queued = True
            self._schedule_render_async()
            return
        self._re_render()

    def _re_render(self) -> None:
        diagnostics.log("_re_render: starting local render pass")
        try:
            self._is_rendering = True
            try:
                self._render_queued = False
                self._commit_dirty()
                self._drain_renders()
            finally:
                self._is_rendering = False
        except Exception as exc:
            if not diagnostics.is_dev():
                raise
            self.show_redbox(exc, phase="render")
        diagnostics.log("_re_render: done")

    def _commit_dirty(self) -> None:
        new_root = self.reconciler.flush_dirty()
        if new_root is not self.root_native_view:
            diagnostics.log("_commit_dirty: root view changed; reattaching")
            self._detach_root(self.root_native_view)
            self.root_native_view = new_root
            self._attach_root(new_root)

    def _drain_renders(self) -> None:
        """Flush renders requested while this host was rendering.

        The reconciler drains updates requested during its own pass and
        raises ``RuntimeError("Too many re-renders")`` on a storm, so no
        second cap is needed here.
        """
        while self._render_queued:
            diagnostics.log("_drain_renders: flushing a queued render")
            self._render_queued = False
            self._commit_dirty()

    # ------------------------------------------------------------------
    # RedBox (dev-mode error overlay)
    # ------------------------------------------------------------------

    def _register_redbox_reporter(self) -> None:
        if diagnostics.is_dev():
            diagnostics.set_error_reporter(self, lambda exc, phase: self.show_redbox(exc, phase))

    def show_redbox(self, exc: BaseException, phase: str = "render") -> None:
        """Mount the dev error overlay over this screen (from any thread)."""
        diagnostics.log(f"show_redbox: {type(exc).__name__} during {phase}")
        try:
            print(f"[PN] {phase} error:", file=sys.stderr)
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        except Exception:
            pass

        def show() -> None:
            self._redbox_visible = True
            payload = {
                "screen": getattr(self, "screen_id", 0),
                "title": f"{type(exc).__name__} in {phase}: {exc}",
                "trace": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            }
            self._show_error(payload)

        from ..runtime import call_on_application_thread

        call_on_application_thread(show)

    def clear_redbox(self, reattach: bool = True) -> None:
        """Dismiss the host-owned error overlay without touching the surface."""
        del reattach
        if not self._redbox_visible:
            return
        self._redbox_visible = False
        self._dismiss_error()

    # ------------------------------------------------------------------
    # Hot reload
    # ------------------------------------------------------------------

    def reload(self, changed_modules: Optional[Sequence[str]] = None) -> str:
        """Reload ``changed_modules`` (and their dependents) and refresh this tree.

        A convenience for a single host (tests, scripts). The dev client
        reloads modules once per process and then calls
        [`refresh`][pythonnative.hosts.ScreenHost.refresh] on every live
        host; see ``pythonnative.hot_reload.apply_reload``.

        Returns:
            ``"fast_refresh"``, ``"remount"``, ``"error"``, or ``"none"``
            (nothing was reloaded).
        """
        from ..hot_reload import ModuleReloader

        requested = list(changed_modules or [])
        targets = ModuleReloader.expand_reload_targets(requested, self.component_path)
        reloaded = ModuleReloader.reload_modules(targets)
        if not reloaded:
            diagnostics.log(f"reload: no modules could be reloaded from {targets!r}")
            return "none"
        return self.refresh(reloaded)

    def refresh(self, reloaded_modules: Sequence[str], *, force_remount: bool = False) -> str:
        """Refresh the mounted tree against already-reloaded modules.

        Tries Fast Refresh first (swap component functions in place so
        hook state survives) and falls back to a full remount.

        Returns:
            ``"fast_refresh"``, ``"remount"``, or ``"error"`` (the error
            is shown in the RedBox in dev mode, re-raised otherwise).
        """
        reloaded = list(reloaded_modules)
        try:
            self.component = import_component(self.component_path)
        except Exception as exc:
            if not diagnostics.is_dev():
                raise
            self.show_redbox(exc, phase="hot reload import")
            return "error"
        if self.reconciler is None:
            return "none"
        self.clear_redbox()
        if self.reconciler.commit_pending:
            self._schedule_refresh(reloaded, force_remount=force_remount)
            return "remount" if force_remount else "fast_refresh"
        if (
            not force_remount
            and not getattr(self.reconciler.backend, "_failed", False)
            and self._try_fast_refresh(reloaded)
        ):
            return "fast_refresh"
        try:
            self._full_remount(reloaded)
        except Exception as exc:
            if not diagnostics.is_dev():
                raise
            self.show_redbox(exc, phase="hot reload")
            return "error"
        return "remount"

    def _try_fast_refresh(self, reloaded_modules: Sequence[str]) -> bool:
        from ..hot_reload import ModuleReloader

        reconciler = self.reconciler
        if reconciler is None or reconciler.root is None:
            return False
        if not ModuleReloader.refresh_in_place(reconciler, reloaded_modules):
            return False
        self._is_rendering = True
        try:
            new_root = reconciler.reconcile(self._root_element())
            if new_root is not self.root_native_view:
                self._detach_root(self.root_native_view)
                self.root_native_view = new_root
                self._attach_root(new_root)
        except Exception as exc:
            diagnostics.log(f"fast refresh: render failed after swap: {exc!r}; falling back to remount")
            return False
        finally:
            self._is_rendering = False
        self._drain_renders()
        return True

    def _schedule_refresh(self, reloaded: Sequence[str], *, force_remount: bool) -> None:
        from ..runtime import get_loop

        async def refresh_when_idle() -> None:
            current = self.reconciler
            try:
                if current is not None:
                    try:
                        await current.wait_for_commit()
                    except Exception:
                        pass  # A failed surface is reset by the remount below.
                if self.reconciler is current and current is not None:
                    self.refresh(reloaded, force_remount=force_remount)
            finally:
                self._refresh_task = None

        if self._refresh_task is not None:
            self._refresh_task.cancel()
        self._refresh_task = get_loop().create_task(refresh_when_idle())

    def _full_remount(self, reloaded_modules: Sequence[str]) -> None:
        del reloaded_modules
        old = self.reconciler
        backend = old.backend

        def mount() -> None:
            if self.reconciler is not old:
                return
            if getattr(backend, "_failed", False):
                backend.reset()
            if self.root_native_view is not None:
                self._detach_root(self.root_native_view)
            self.root_native_view = None
            self.reconciler = self._new_reconciler()
            self._seed_viewport()
            self.reconciler.mount(self._root_element())
            self._drain_renders()

        old.unmount()
        if not old.commit_pending:
            mount()
            return
        from ..runtime import get_loop

        async def remount() -> None:
            try:
                await old.wait_for_commit()
                mount()
            except Exception as error:
                if diagnostics.is_dev():
                    self.show_redbox(error, phase="hot reload")
                else:
                    raise

        self._refresh_task = get_loop().create_task(remount())


def flush_hosts(hosts: Sequence[ScreenHost]) -> None:
    """Run deferred renders for ``hosts`` (platform UI-thread drains call this)."""
    for host in hosts:
        host.flush_scheduled_render()
