"""Platform-independent screen host.

A host bridges one native screen (an Android fragment, an iOS view
controller, a desktop preview page) to a [`Reconciler`][pythonnative.reconciler.Reconciler]
rendering the app's root component. It owns:

- **Lifecycle**: ``on_create`` mounts the tree, ``on_resume`` /
  ``on_pause`` track focus, ``on_destroy`` unmounts.
- **Render scheduling**: state changes during a render are queued and
  drained in bounded batches; platforms hop off-main-thread requests
  onto the UI thread.
- **Navigation bridging**: the host implements
  [`HostNavigator`][pythonnative.navigation.HostNavigator], so a root
  ``Stack.Navigator`` can push real native screens. Each pushed screen
  runs the same root component with its navigation history in
  ``args["pn_nav"]``.
- **Dev tooling**: the RedBox error overlay and hot reload (Fast Refresh
  with a full-remount fallback).

Subclasses implement the handful of ``_native_*`` primitives for their
platform (attach a root view, push a screen, set the title, ...).
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import diagnostics
from ..element import Element

__all__ = ["ScreenHost", "import_component", "log_pn", "debug_enabled"]

MAX_RENDER_PASSES = 25
_DEBUG_ENV = "PYTHONNATIVE_DEBUG"


def debug_enabled() -> bool:
    """Return whether the ``PYTHONNATIVE_DEBUG`` environment variable turns on host diagnostics."""
    return os.environ.get(_DEBUG_ENV, "").lower() in {"1", "true", "yes", "on"}


def log_pn(msg: str) -> None:
    """Emit optional diagnostics when ``PYTHONNATIVE_DEBUG`` is enabled."""
    if not debug_enabled():
        return
    try:
        print(f"[PN] {msg}", flush=True)
    except Exception:
        pass


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
            (``Activity``, ``UIViewController``, ``DesktopApp``).
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
        self._hot_reload_manifest_path: Optional[str] = None
        self._hot_reload_last_version: Optional[str] = None
        self._hot_reload_pending_version: Optional[str] = None
        self._redbox_reconciler: Any = None
        self._redbox_root: Any = None

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

    def _native_push(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        raise RuntimeError("Pushing native screens requires a native runtime (iOS, Android, or `pn preview`)")

    def _native_pop(self, count: int) -> None:
        raise RuntimeError("Popping native screens requires a native runtime (iOS, Android, or `pn preview`)")

    def _native_replace(self, component_path: str, args: Dict[str, Any], options: Dict[str, Any]) -> None:
        self._native_pop(1)
        self._native_push(component_path, args, options)

    def _native_reset(self, component_path: str, screens: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]) -> None:
        """Pop to the root native screen, then push ``screens`` (``(args, options)`` pairs)."""
        self._native_pop_to_root()
        for args, options in screens:
            self._native_push(component_path, args, options)

    def _native_pop_to_root(self) -> None:
        pass

    def _native_set_options(self, options: Dict[str, Any]) -> None:
        """Apply header options (``title`` at minimum) to the native chrome."""

    # ------------------------------------------------------------------
    # HostNavigator protocol
    # ------------------------------------------------------------------

    def initial_navigation_state(self) -> Optional[Dict[str, Any]]:
        """Return the serialized navigation state from ``args["pn_nav"]``, or ``None`` for the first screen."""
        from ..navigation.host import initial_state_from_args

        return initial_state_from_args(self.args)

    def push_screen(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Push a native screen running the same root component, seeded with ``state``."""
        from ..navigation.host import NAV_STATE_ARG

        self._native_push(self.component_path, {NAV_STATE_ARG: state}, options)

    def pop_screens(self, count: int) -> None:
        """Pop ``count`` native screens (at least one)."""
        self._native_pop(max(1, int(count)))

    def replace_screen(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Replace the current native screen with one seeded with ``state``."""
        from ..navigation.host import NAV_STATE_ARG

        self._native_replace(self.component_path, {NAV_STATE_ARG: state}, options)

    def reset_screens(self, state: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Rebuild the native stack for ``state``.

        The root native screen stays; every route above the first gets
        its own native screen carrying the history up to it, so the
        back button walks the new stack.
        """
        from ..navigation.host import NAV_STATE_ARG

        routes = list(state.get("routes") or [])
        screens: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for depth in range(2, len(routes) + 1):
            partial = {"routes": routes[:depth], "index": depth - 1}
            screens.append(({NAV_STATE_ARG: partial}, options if depth == len(routes) else {}))
        self._native_reset(self.component_path, screens)

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
        if self.reconciler is not None and self.root_native_view is not None:
            self._attach_root(self.root_native_view)
            return

        self.reconciler = self._new_reconciler()
        self._seed_viewport()
        try:
            self._is_rendering = True
            try:
                self.root_native_view = self.reconciler.mount(self._root_element())
                self._attach_root(self.root_native_view)
                self._drain_renders()
            finally:
                self._is_rendering = False
        except Exception as exc:
            if not diagnostics.is_dev():
                raise
            self.show_redbox(exc, phase="mount")

    def on_start(self) -> None:
        """Handle the platform's start event (no-op by default)."""
        pass

    def on_resume(self) -> None:
        """Mark the screen focused and notify focus listeners."""
        self.set_focused(True)

    def on_layout(self) -> None:
        """Handle a native layout pass (no-op by default; platforms sync the viewport here)."""
        pass

    def on_pause(self) -> None:
        """Mark the screen unfocused and notify focus listeners."""
        self.set_focused(False)

    def on_stop(self) -> None:
        """Handle the platform's stop event (no-op by default)."""
        pass

    def on_restart(self) -> None:
        """Handle the platform's restart event (no-op by default)."""
        pass

    def on_save_instance_state(self) -> None:
        """Handle the platform's save-state request (no-op by default)."""
        pass

    def on_restore_instance_state(self) -> None:
        """Handle the platform's restore-state event (no-op by default)."""
        pass

    def on_destroy(self) -> None:
        """Tear down: unmount (running effect cleanups), release native views."""
        self.clear_redbox(reattach=False)
        diagnostics.set_error_reporter(self, None)
        reconciler, self.reconciler = self.reconciler, None
        if reconciler is not None:
            try:
                reconciler.unmount()
            except Exception:
                log_pn("on_destroy: reconciler.unmount() failed")
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
        if self._redbox_reconciler is not None:
            self._redbox_reconciler.set_viewport_size(float(width), float(height))
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
        from ..native_views import get_registry
        from ..reconciler import Reconciler

        reconciler = Reconciler(get_registry())
        reconciler.on_render_requested = self.request_render
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
        log_pn("_re_render: starting local render pass")
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
        log_pn("_re_render: done")

    def _commit_dirty(self) -> None:
        new_root = self.reconciler.flush_dirty()
        if new_root is not self.root_native_view:
            log_pn("_commit_dirty: root view changed; reattaching")
            self._detach_root(self.root_native_view)
            self.root_native_view = new_root
            self._attach_root(new_root)

    def _drain_renders(self) -> None:
        """Flush renders queued by effects; capped to break runaway loops."""
        for i in range(MAX_RENDER_PASSES):
            if not self._render_queued:
                break
            log_pn(f"_drain_renders: pass #{i + 1}")
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
        log_pn(f"show_redbox: {type(exc).__name__} during {phase}")
        try:
            print(f"[PN] {phase} error:", file=sys.stderr)
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        except Exception:
            pass

        def mount() -> None:
            try:
                self.clear_redbox(reattach=False)
                from ..native_views import get_registry
                from ..reconciler import Reconciler

                redbox = Reconciler(get_registry())
                element = _redbox_element(exc, phase, lambda: self.clear_redbox())
                root = redbox.mount(element)
                width, height = self.reconciler.viewport_size if self.reconciler is not None else (0.0, 0.0)
                if width <= 0 or height <= 0:
                    from .. import platform_metrics

                    dims = platform_metrics.get_window_dimensions()
                    width, height = dims.width, dims.height
                if width > 0 and height > 0:
                    redbox.set_viewport_size(width, height)
                self._redbox_reconciler = redbox
                self._redbox_root = root
                if self.root_native_view is not None:
                    self._detach_root(self.root_native_view)
                self._attach_root(root)
            except Exception:
                print("[PN] RedBox failed to mount:", file=sys.stderr)
                traceback.print_exc()

        from ..runtime import call_on_main_thread

        call_on_main_thread(mount)

    def clear_redbox(self, reattach: bool = True) -> None:
        """Dismiss the dev error overlay, reattaching the app's root view unless ``reattach`` is ``False``."""
        redbox, self._redbox_reconciler = self._redbox_reconciler, None
        self._redbox_root = None
        if redbox is None:
            return
        try:
            redbox.unmount()
        except Exception:
            pass
        if reattach and self.root_native_view is not None:
            try:
                self._attach_root(self.root_native_view)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hot reload
    # ------------------------------------------------------------------

    def enable_hot_reload(self, manifest_path: str, source_root: Optional[str] = None) -> None:
        """Start polling ``manifest_path`` for reloads (see ``hot_reload_tick``) and switch on dev mode.

        ``source_root`` is accepted for the native templates, which pass the
        dev directory alongside the manifest; the reloader derives module
        paths from the manifest itself, so it is currently unused.
        """
        self._hot_reload_manifest_path = manifest_path
        self._hot_reload_last_version = None
        # Hot reload only runs on debug builds, so it doubles as the
        # on-device dev-mode switch (validation warnings, RedBox).
        diagnostics.set_dev_mode(True)
        self._register_redbox_reporter()

    def hot_reload_tick(self) -> bool:
        """Poll the reload manifest; returns whether a reload was applied."""
        manifest_path = self._hot_reload_manifest_path
        if not manifest_path:
            return False
        from ..hot_reload import ModuleReloader

        last = self._hot_reload_last_version
        if not os.path.exists(manifest_path) and last is None:
            return False
        next_version = ModuleReloader.reload_from_manifest(self, manifest_path, last_version=last)
        if next_version == last:
            return False
        self._hot_reload_last_version = next_version
        return True

    def reload(self, changed_modules: Optional[Sequence[str]] = None) -> None:
        """Reload modules and refresh the tree (Fast Refresh, else full remount)."""
        from ..hot_reload import ModuleReloader

        requested = list(changed_modules or [])
        targets = ModuleReloader.expand_reload_targets(requested, self.component_path)
        reloaded = ModuleReloader.reload_modules_for_version(targets, self._hot_reload_pending_version)
        if not reloaded:
            log_pn(f"reload: no modules could be reloaded from {targets!r}")
            return
        try:
            self.component = import_component(self.component_path)
        except Exception as exc:
            if diagnostics.is_dev():
                self.show_redbox(exc, phase="hot reload import")
            return
        if self.reconciler is None:
            return
        self.clear_redbox()
        if self._try_fast_refresh(reloaded):
            print(f"[hot-reload] Fast Refresh: {', '.join(requested) or ', '.join(reloaded)}", file=sys.stderr)
            return
        try:
            self._full_remount(reloaded)
        except Exception as exc:
            if not diagnostics.is_dev():
                raise
            self.show_redbox(exc, phase="hot reload")

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
            log_pn(f"fast refresh: render failed after swap: {exc!r}; falling back to remount")
            return False
        finally:
            self._is_rendering = False
        self._drain_renders()
        return True

    def _full_remount(self, reloaded_modules: Sequence[str]) -> None:
        old_reconciler, old_root = self.reconciler, self.root_native_view
        new_reconciler = self._new_reconciler()
        self.reconciler = new_reconciler
        self._is_rendering = True
        try:
            new_root = new_reconciler.mount(self._root_element())
        except Exception:
            self.reconciler = old_reconciler
            raise
        finally:
            self._is_rendering = False
        if old_reconciler is not None:
            old_reconciler.unmount()
        if old_root is not None:
            self._detach_root(old_root)
        self.root_native_view = new_root
        self._attach_root(new_root)
        self._drain_renders()
        print(f"[hot-reload] Remounted: {', '.join(reloaded_modules)}", file=sys.stderr)


def _redbox_element(exc: BaseException, phase: str, on_dismiss: Callable[[], None]) -> Element:
    from ..components import Button, Column, ScrollView, Text

    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    message = str(exc) or "(no message)"
    return Column(
        Column(
            Text(f"{type(exc).__name__} in {phase}", style={"color": "#FFD3DA", "font_size": 13, "bold": True}),
            Text(message, style={"color": "#FFFFFF", "font_size": 17, "bold": True}),
            style={"background_color": "#C4283C", "padding": 16, "padding_top": 56, "spacing": 6},
        ),
        ScrollView(
            Text(trace, style={"color": "#FF9AA8", "font_size": 12}),
            style={"flex": 1, "padding": 12},
        ),
        Column(
            Button("Dismiss", on_press=on_dismiss, style={"color": "#FFFFFF"}),
            Text(
                "Fix the error and save to reload.", style={"color": "#8E8E93", "font_size": 12, "text_align": "center"}
            ),
            style={"padding": 12, "padding_bottom": 32, "spacing": 4},
        ),
        style={"flex": 1, "background_color": "#1C1C1E"},
    )


def flush_hosts(hosts: Sequence[ScreenHost]) -> None:
    """Run deferred renders for ``hosts`` (platform UI-thread drains call this)."""
    for host in hosts:
        host.flush_scheduled_render()
