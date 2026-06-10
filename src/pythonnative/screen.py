"""Screen host: the bridge between native lifecycle and function components.

Users do not write screen classes by hand. Instead they write
``@component`` functions and the native template calls
[`create_screen`][pythonnative.create_screen] to obtain a host that
manages the reconciler and lifecycle for that screen.

The screen host owns:

- A [`Reconciler`][pythonnative.reconciler.Reconciler] backed by the
  platform's native-view registry.
- A [`NavigationHandle`][pythonnative.hooks.NavigationHandle] (delivered to
  components via the navigation context) so screens can push and pop
  without holding a direct reference to native classes.
- Render scheduling. State changes during render are queued and drained
  in batches so the reconciler runs at most a bounded number of passes
  per user gesture.

Example:
    User code defines a top-level component named ``App``:

    ```python
    import pythonnative as pn

    @pn.component
    def App():
        count, set_count = pn.use_state(0)
        return pn.Column(
            pn.Text(f"Count: {count}", style={"font_size": 24}),
            pn.Button("Tap me", on_click=lambda: set_count(count + 1)),
            style={"spacing": 12, "padding": 16},
        )
    ```

    The native template wires it in:

    ```python
    host = pythonnative.screen.create_screen(
        "app.main",
        native_instance,
    )
    host.on_create()
    ```
"""

import importlib
import json
import os
import sys
import threading
from typing import Any, Dict, Optional, Sequence

from .utils import IS_ANDROID, IS_DESKTOP, IS_IOS, set_android_context

_MAX_RENDER_PASSES = 25
_DEBUG_ENV = "PYTHONNATIVE_DEBUG"


def _debug_enabled() -> bool:
    return os.environ.get(_DEBUG_ENV, "").lower() in {"1", "true", "yes", "on"}


def _log_pn(msg: str) -> None:
    """Emit optional diagnostics when ``PYTHONNATIVE_DEBUG`` is enabled."""
    if not _debug_enabled():
        return
    try:
        print(f"[PN] {msg}", flush=True)
    except Exception:
        pass


# ======================================================================
# Component path resolution
# ======================================================================


def _resolve_component_path(component_ref: Any) -> str:
    """Resolve a component function or string into a `module.name` path."""
    if isinstance(component_ref, str):
        return component_ref
    func = getattr(component_ref, "__wrapped__", component_ref)
    module = getattr(func, "__module__", None)
    name = getattr(func, "__name__", None)
    if module and name:
        return f"{module}.{name}"
    raise ValueError(f"Cannot resolve component path for {component_ref!r}")


def _missing_module_is_target(exc: ModuleNotFoundError, dotted: str) -> bool:
    """Return ``True`` when ``exc`` means ``dotted`` itself is absent.

    Distinguishes "the component module/package cannot be found" (so the
    caller should fall through to the next resolution strategy) from "the
    module exists but raised :class:`ModuleNotFoundError` while importing
    one of *its own* dependencies". The latter must propagate so the
    developer sees the real missing import (e.g. ``No module named
    'emoji'``) instead of a misleading "could not resolve component".
    """
    missing = exc.name or ""
    return missing == dotted or dotted.startswith(missing + ".")


def _import_component(component_path: str) -> Any:
    """Import a component by module or dotted-attribute path.

    PythonNative's entry-point convention is "define a function named
    ``App`` at the top of your module, and the native templates will
    find it". So the templates pass a *module path* like
    ``"app.main"`` and this helper imports the module and returns its
    ``App`` attribute.

    A dotted ``module.Attribute`` path is also accepted as an escape
    hatch (e.g. ``"app.main.RootScreen"``) for users who want to
    expose a differently-named component without renaming it to
    ``App``.

    Resolution order:

    1. If ``component_path`` resolves cleanly as a module, return its
       ``App`` attribute.
    2. Otherwise split on the final ``.``: import the parent module
       and return the named attribute.

    Args:
        component_path: Either ``"app.main"`` (module path with an
            ``App`` attribute) or ``"app.main.SomeComponent"`` (dotted
            path to a specific component).

    Returns:
        The resolved component callable.

    Raises:
        ImportError: If the module or dotted path cannot be found.
            Errors raised *inside* a resolvable module (such as a
            missing third-party dependency it imports) propagate
            unchanged so the real cause stays visible.
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
        f"Could not resolve component {component_path!r}. "
        "Define a top-level `App` function in the module (e.g. "
        "`app/main.py`) or pass an explicit dotted path like "
        "`app.main.RootScreen`."
    )


# ======================================================================
# Shared helpers
# ======================================================================


def _init_host_common(host: Any, component_path: str, component_func: Any) -> None:
    host._component_path = component_path
    host._component = component_func
    host._args = {}
    host._reconciler = None
    host._root_native_view = None
    host._nav_handle = None
    host._is_rendering = False
    host._render_queued = False
    host._render_scheduled = False
    host._hot_reload_manifest_path = None
    host._hot_reload_last_version = None
    host._layout_listener = None  # retained on Android to prevent GC
    # Focus state — drives ``use_focus_effect``. Starts focused because
    # a host is only created when the screen is being presented; the
    # platform lifecycle hooks (``on_resume`` / ``on_pause``) flip this
    # when the user navigates to / from another screen.
    host._is_focused = True
    host._focus_subscribers = []


def _set_host_focused(host: Any, focused: bool) -> None:
    """Update ``host._is_focused`` and notify ``use_focus_effect`` subscribers."""
    if getattr(host, "_is_focused", True) == focused:
        return
    host._is_focused = focused
    subscribers = list(getattr(host, "_focus_subscribers", ()) or ())
    for callback in subscribers:
        try:
            callback(focused)
        except Exception:
            pass


def _push_viewport_size(host: Any, width: float, height: float) -> None:
    """Forward a viewport-size change to the reconciler.

    Called by the native template (or our injected layout listener
    on Android, or `_attach_root` on iOS) whenever the screen
    container's bounds change. Coordinates must be in points (not
    raw pixels). Also publishes the new dimensions to
    `pythonnative.platform_metrics` so the
    [`use_window_dimensions`][pythonnative.use_window_dimensions]
    hook re-renders subscribers.
    """
    if host._reconciler is None:
        return
    if width <= 0 or height <= 0:
        return
    host._reconciler.set_viewport_size(float(width), float(height))
    try:
        from . import platform_metrics

        platform_metrics.set_window_dimensions(float(width), float(height))
    except Exception:
        pass


def _get_component(host: Any) -> Any:
    """Resolve the current component function from its dotted path."""
    host._component = _import_component(host._component_path)
    return host._component


def _render_app(host: Any) -> Any:
    """Call the current root component and return its element tree."""
    return _get_component(host)()


def _new_reconciler(host: Any) -> Any:
    from .native_views import get_registry
    from .reconciler import Reconciler

    reconciler = Reconciler(get_registry())
    reconciler._screen_re_render = lambda: _request_render(host)
    return reconciler


def _schedule_render_async(host: Any) -> bool:
    """Schedule a render for a later platform turn, if supported."""
    return False


def _flush_scheduled_renders(hosts: Sequence[Any]) -> None:
    """Run renders that were deferred out of a native event callback."""
    for host in hosts:
        host._render_scheduled = False
        if host._reconciler is None:
            continue
        if host._is_rendering:
            host._render_queued = True
            _schedule_render_async(host)
            continue
        _re_render(host)


def _on_create(host: Any) -> None:
    from .hooks import NavigationHandle, Provider, _NavigationContext

    # ``on_create`` is idempotent across native-view recreations. On
    # Android the FragmentManager destroys and recreates a screen's
    # view every time the user pops back to it, and the platform
    # template calls ``screen.on_create()`` again from
    # ``onViewCreated`` — but the Python screen object (and therefore
    # the reconciler, hook state, focus subscribers, etc.) persists
    # across that. Re-running the full mount path here would reset
    # use_state, clobber use_focus_effect subscriptions, and break
    # navigation handles held by existing components, which is why
    # the focus counter never advanced past ``1`` before this guard.
    # If we're already mounted, just re-attach the existing root view
    # to the (newly created) native container — ``on_resume`` will
    # fire the focus subscribers separately.
    if host._reconciler is not None and host._root_native_view is not None:
        host._attach_root(host._root_native_view)
        return

    host._nav_handle = NavigationHandle(host)
    host._reconciler = _new_reconciler(host)

    app_element = _render_app(host)
    provider_element = Provider(_NavigationContext, host._nav_handle, app_element)

    host._is_rendering = True
    try:
        host._root_native_view = host._reconciler.mount(provider_element)
        host._attach_root(host._root_native_view)
        _drain_renders(host)
    finally:
        host._is_rendering = False


def _request_render(host: Any) -> None:
    """Request a render pass.

    If a render is already in progress (state changed mid-render or
    inside an effect), the request is queued and drained at the end of
    the current pass so the reconciler is never re-entered.
    """
    if host._reconciler is None:
        return
    if host._is_rendering:
        host._render_queued = True
        return
    if _schedule_render_async(host):
        return
    _re_render(host)


def _re_render(host: Any) -> None:
    """Run one *local* render pass, then drain any renders queued during it.

    State setters mark only their own component subtree dirty (see
    [`mark_dirty`][pythonnative.reconciler.Reconciler.mark_dirty]), so
    this drains the reconciler's dirty set via
    [`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
    instead of re-running the whole ``App`` from the root. The app's
    element tree is only rebuilt from scratch on mount, navigation, and
    hot reload.
    """
    _log_pn("_re_render: starting local render pass")
    host._is_rendering = True
    try:
        host._render_queued = False
        _commit_dirty(host)
        _drain_renders(host)
    finally:
        host._is_rendering = False
    _log_pn("_re_render: done")


def _commit_dirty(host: Any) -> None:
    """Flush the reconciler's dirty components and re-attach the root if it changed."""
    new_root = host._reconciler.flush_dirty()
    if new_root is not host._root_native_view:
        _log_pn(f"_commit_dirty: ROOT VIEW CHANGED ({id(host._root_native_view)} -> {id(new_root)}); reattaching")
        host._detach_root(host._root_native_view)
        host._root_native_view = new_root
        host._attach_root(new_root)


def _drain_renders(host: Any) -> None:
    """Flush additional renders queued by effects that set state.

    Capped at `_MAX_RENDER_PASSES` to break runaway feedback loops
    (e.g., an effect that unconditionally calls a setter).
    """
    for i in range(_MAX_RENDER_PASSES):
        if not host._render_queued:
            break
        _log_pn(f"_drain_renders: draining pass #{i + 1}")
        host._render_queued = False
        _commit_dirty(host)


def _set_args(host: Any, args: Any) -> None:
    if isinstance(args, str):
        try:
            host._args = json.loads(args) or {}
        except Exception:
            host._args = {}
        return
    host._args = args if isinstance(args, dict) else {}


def _enable_hot_reload(host: Any, manifest_path: str) -> None:
    host._hot_reload_manifest_path = manifest_path
    host._hot_reload_last_version = None


def _hot_reload_tick(host: Any) -> bool:
    manifest_path = getattr(host, "_hot_reload_manifest_path", None)
    if not manifest_path:
        return False

    from .hot_reload import ModuleReloader

    last = getattr(host, "_hot_reload_last_version", None)
    manifest_exists = os.path.exists(manifest_path)
    if not manifest_exists and last is None:
        return False

    # The iOS template polls every 0.5s per UIViewController, so this
    # tick fires several times per second per host. The per-tick log is
    # gated behind ``PYTHONNATIVE_DEBUG`` to keep normal output quiet
    # while preserving the breadcrumb when investigating reload races.
    if _debug_enabled():
        manifest_version: Optional[str] = None
        if manifest_exists:
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    raw_version = json.load(f).get("version", "")
                manifest_version = str(raw_version) if raw_version else None
            except Exception:
                manifest_version = None
        action = "reload" if (manifest_version is not None and manifest_version != last) else "skip"
        _log_pn(
            f"_hot_reload_tick: host=0x{id(host):x} component={host._component_path} "
            f"last={last!r} manifest={manifest_version!r} action={action}"
        )

    next_version = ModuleReloader.reload_from_manifest(
        host,
        manifest_path,
        last_version=last,
    )
    if next_version == last:
        return False
    host._hot_reload_last_version = next_version
    return True


def _reload_host(host: Any, changed_modules: Optional[Sequence[str]] = None) -> None:
    """Reload modules and refresh the host's reconciler tree.

    Tries **Fast Refresh** first: the changed modules are reloaded
    and every ``element.type`` reference in the current ``VNode``
    tree is rewritten to point at the new module's functions. The
    next render then runs the new bodies through the existing hook
    slots, so component state survives.

    The reload set is **expanded** to include every currently-imported
    module under the entry-point's top-level package (see
    [`expand_reload_targets`][pythonnative.hot_reload.ModuleReloader.expand_reload_targets]).
    This catches transitive ``from ... import`` bindings that would
    otherwise remain stale: if ``app/main.py`` does
    ``from app.screens.home import HomeScreen`` and the user edits
    ``home.py``, reloading just ``app.screens.home`` leaves
    ``app.main.HomeScreen`` pointing at the pre-edit function, so the
    new render emits stale element types and the reconciler is forced
    to unmount and remount the screen (losing state and showing old
    code). Reloading every user-app module in dependency-friendly
    order, with the entry-point last, keeps every binding fresh.

    If Fast Refresh fails (the new module raised at import time, no
    replacements could be located, or the next render itself
    threw), the host falls back to a full remount: a brand-new
    reconciler tree is mounted into the same native root. State is
    lost but the app keeps running so the developer can fix the
    error and try again.
    """
    from .hot_reload import ModuleReloader

    requested = list(changed_modules or [])
    targets = ModuleReloader.expand_reload_targets(requested, host._component_path)

    pending_version = getattr(host, "_hot_reload_pending_version", None)
    already_loaded = pending_version is not None and pending_version == ModuleReloader._last_reloaded_version
    _log_pn(
        f"_reload_host: host=0x{id(host):x} component={host._component_path} "
        f"requested={requested!r} targets={len(targets)} version={pending_version!r} "
        f"action={'reuse_modules' if already_loaded else 'reload_modules'}"
    )

    reloaded = ModuleReloader.reload_modules_for_version(targets, pending_version)
    if not reloaded:
        _log_pn(f"_reload_host: no modules could be reloaded from {targets!r}; aborting")
        return

    try:
        new_component = _import_component(host._component_path)
    except Exception as e:
        _log_pn(f"_reload_host: re-import failed: {e!r}; aborting reload")
        return
    host._component = new_component

    if host._reconciler is None:
        _log_pn(f"_reload_host: host=0x{id(host):x} reconciler=None; skipping refresh")
        return

    if _try_fast_refresh(host, reloaded):
        print(f"[hot-reload] Fast Refresh: {', '.join(requested) or ', '.join(reloaded)}", file=sys.stderr)
        return

    _full_remount(host, reloaded)


def _try_fast_refresh(host: Any, reloaded_modules: Sequence[str]) -> bool:
    """Attempt an in-place component swap + re-render.

    Returns ``True`` only if the swap happened and the subsequent
    render completed without raising. On exception we restore the
    pre-render reconciler state so the caller can fall back to a
    full remount.
    """
    from .hooks import Provider, _NavigationContext
    from .hot_reload import ModuleReloader

    reconciler = host._reconciler
    if reconciler is None or reconciler._tree is None:
        return False

    rewrote = ModuleReloader.refresh_in_place(reconciler, reloaded_modules)
    if not rewrote:
        return False

    host._is_rendering = True
    try:
        app_element = _render_app(host)
        provider_element = Provider(_NavigationContext, host._nav_handle, app_element)
        new_root = reconciler.reconcile(provider_element)
        if new_root is not host._root_native_view:
            host._detach_root(host._root_native_view)
            host._root_native_view = new_root
            host._attach_root(new_root)
    except Exception as e:
        _log_pn(f"_try_fast_refresh: render failed after swap: {e!r}; falling back to remount")
        return False
    finally:
        host._is_rendering = False

    _drain_renders(host)
    return True


def _full_remount(host: Any, reloaded_modules: Sequence[str]) -> None:
    """Destroy the existing tree and mount a fresh one.

    Used by [`_reload_host`][pythonnative.screen._reload_host] as the
    fallback path when Fast Refresh cannot apply (e.g. the user
    deleted a component that was on screen).
    """
    from .hooks import NavigationHandle, Provider, _NavigationContext

    old_reconciler = host._reconciler
    old_root = host._root_native_view
    old_nav = host._nav_handle

    new_reconciler = _new_reconciler(host)
    host._reconciler = new_reconciler
    host._nav_handle = NavigationHandle(host)
    host._is_rendering = True
    try:
        app_element = _render_app(host)
        provider_element = Provider(_NavigationContext, host._nav_handle, app_element)
        new_root = new_reconciler.mount(provider_element)
    except Exception:
        host._reconciler = old_reconciler
        host._nav_handle = old_nav
        raise
    finally:
        host._is_rendering = False

    if old_reconciler is not None:
        # ``unmount`` queues the DestroyOps *and* flushes them to the
        # backend in one batch (releasing native views and their event
        # registrations).
        old_reconciler.unmount()
    if old_root is not None:
        host._detach_root(old_root)

    host._root_native_view = new_root
    host._attach_root(new_root)
    _drain_renders(host)
    print(f"[hot-reload] Remounted: {', '.join(reloaded_modules)}", file=sys.stderr)


# ======================================================================
# Platform implementations
# ======================================================================

if IS_ANDROID:
    from java import dynamic_proxy, jclass

    _ANDROID_SCHEDULED_RENDER_HOSTS: Dict[int, Any] = {}
    _android_render_scheduler_handler: Any = None
    _android_render_scheduler_runnable: Any = None
    _android_main_looper: Any = None

    def _is_android_main_thread() -> bool:
        """Return True when running on Android's main looper thread."""
        global _android_main_looper
        try:
            Looper = jclass("android.os.Looper")
            if _android_main_looper is None:
                _android_main_looper = Looper.getMainLooper()
            return Looper.myLooper() == _android_main_looper
        except Exception:
            return threading.current_thread() is threading.main_thread()

    def _flush_android_scheduled_renders() -> None:
        hosts = list(_ANDROID_SCHEDULED_RENDER_HOSTS.values())
        _ANDROID_SCHEDULED_RENDER_HOSTS.clear()
        _flush_scheduled_renders(hosts)

    def _schedule_render_async(host: Any) -> bool:
        global _android_render_scheduler_handler, _android_render_scheduler_runnable
        if not IS_ANDROID:
            return False
        if getattr(host, "_render_scheduled", False):
            return True
        if _is_android_main_thread():
            return False

        host._render_scheduled = True
        _ANDROID_SCHEDULED_RENDER_HOSTS[id(host)] = host
        try:
            if _android_render_scheduler_handler is None:
                Handler = jclass("android.os.Handler")
                Looper = jclass("android.os.Looper")
                Runnable = jclass("java.lang.Runnable")
                _android_render_scheduler_handler = Handler(Looper.getMainLooper())

                class _PNRenderRunnable(dynamic_proxy(Runnable)):  # type: ignore[misc]
                    def run(self) -> None:
                        _flush_android_scheduled_renders()

                _android_render_scheduler_runnable = _PNRenderRunnable()
            _android_render_scheduler_handler.post(_android_render_scheduler_runnable)
            return True
        except Exception:
            host._render_scheduled = False
            _ANDROID_SCHEDULED_RENDER_HOSTS.pop(id(host), None)
            return False

    def _android_publish_window_insets(view: Any) -> None:
        """Read system-bar insets from *view* and publish them to platform_metrics.

        Most production Android themes already exclude the system
        navigation bar from the activity content area, so the bottom
        inset reported here is typically ``0`` on classic devices.
        On edge-to-edge themes (or 3-button gesture nav strips), the
        bottom inset is non-zero and the tab bar needs to claim that
        space so the system gesture indicator does not overlap its
        labels.

        The function is best-effort: API levels < 30 expose
        ``getSystemWindowInsetBottom`` instead of the typed
        ``getInsets(systemBars())`` API, and very old phones may
        not expose ``getRootWindowInsets`` at all. All branches are
        wrapped in ``try/except`` because diagnostics here must
        never crash a screen host.
        """
        try:
            from . import platform_metrics
        except Exception:
            return
        try:
            insets_obj = view.getRootWindowInsets()
            if insets_obj is None:
                return
            density = float(view.getResources().getDisplayMetrics().density) or 1.0
            top_px = 0
            left_px = 0
            bottom_px = 0
            right_px = 0
            try:
                WindowInsets = jclass("android.view.WindowInsets")
                Type = WindowInsets.Type
                bars = Type.systemBars()
                typed = insets_obj.getInsets(bars)
                top_px = int(typed.top)
                left_px = int(typed.left)
                bottom_px = int(typed.bottom)
                right_px = int(typed.right)
            except Exception:
                top_px = int(insets_obj.getSystemWindowInsetTop() or 0)
                left_px = int(insets_obj.getSystemWindowInsetLeft() or 0)
                bottom_px = int(insets_obj.getSystemWindowInsetBottom() or 0)
                right_px = int(insets_obj.getSystemWindowInsetRight() or 0)
            platform_metrics.set_safe_area_insets(
                top_px / density,
                left_px / density,
                bottom_px / density,
                right_px / density,
            )
        except Exception:
            pass

    def _android_register_layout_listener(host: Any, view: Any) -> None:
        """Push the container's measured size into the reconciler whenever it changes."""
        try:
            View = jclass("android.view.View")

            class _PNLayoutChangeListener(dynamic_proxy(View.OnLayoutChangeListener)):  # type: ignore[misc]
                def __init__(self, host_obj: Any) -> None:
                    super().__init__()
                    self.host_obj = host_obj

                def onLayoutChange(
                    self,
                    v: Any,
                    left: int,
                    top: int,
                    right: int,
                    bottom: int,
                    old_left: int,
                    old_top: int,
                    old_right: int,
                    old_bottom: int,
                ) -> None:
                    try:
                        # Publish insets *before* the viewport push so
                        # the layout pass triggered by the size change
                        # sees the latest values; otherwise inset-aware
                        # handlers (e.g., a future ``SafeAreaView``)
                        # would lay out one frame stale and the user
                        # would see a flicker on first paint.
                        _android_publish_window_insets(v)
                        density = float(v.getResources().getDisplayMetrics().density) or 1.0
                        _push_viewport_size(self.host_obj, (right - left) / density, (bottom - top) / density)
                    except Exception:
                        pass

            listener = _PNLayoutChangeListener(host)
            view.addOnLayoutChangeListener(listener)
            host._layout_listener = listener  # retain to prevent GC
        except Exception:
            pass

    def _android_push_initial_viewport(host: Any, view: Any) -> None:
        """Push the current measured size if available (no-op until layout completes)."""
        try:
            # Publish insets first so the very first layout pass sees
            # them. Otherwise handlers reading insets at first paint
            # would get ``(0, 0, 0, 0)`` and re-measure once the
            # ``OnLayoutChangeListener`` fires moments later — a
            # measurable flicker (~50–200 ms on a stock Pixel
            # emulator).
            _android_publish_window_insets(view)
            w = int(view.getWidth() or 0)
            h = int(view.getHeight() or 0)
            if w > 0 and h > 0:
                density = float(view.getResources().getDisplayMetrics().density) or 1.0
                _push_viewport_size(host, w / density, h / density)
            else:
                # Fall back to display metrics so we always have a non-zero
                # viewport even before the first layout pass; the listener
                # will refine it as soon as the container is measured.
                metrics = view.getResources().getDisplayMetrics()
                density = float(metrics.density) or 1.0
                _push_viewport_size(host, metrics.widthPixels / density, metrics.heightPixels / density)
        except Exception:
            pass

    class _ScreenHost:
        """Android host backed by an `Activity` and fragment-based navigation.

        Owned by the screen fragment template. Bridges Android lifecycle
        callbacks (`onCreate`, `onPause`, etc.) to the reconciler and
        the function component.
        """

        def __init__(self, native_instance: Any, component_path: str, component_func: Any) -> None:
            self.native_instance = native_instance
            set_android_context(native_instance)
            _init_host_common(self, component_path, component_func)

        def on_create(self) -> None:
            _on_create(self)

        def on_start(self) -> None:
            pass

        def on_resume(self) -> None:
            _set_host_focused(self, True)

        def on_layout(self) -> None:
            # Android pushes viewport changes through the
            # ``OnLayoutChangeListener`` registered in ``_attach_root``;
            # this no-op exists so callers can fire the same lifecycle
            # event on both platforms.
            pass

        def on_pause(self) -> None:
            _set_host_focused(self, False)

        def on_stop(self) -> None:
            pass

        def on_destroy(self) -> None:
            pass

        def enable_hot_reload(self, manifest_path: str, source_root: Optional[str] = None) -> None:
            _enable_hot_reload(self, manifest_path)

        def hot_reload_tick(self) -> bool:
            return _hot_reload_tick(self)

        def reload(self, changed_modules: Optional[Sequence[str]] = None) -> None:
            _reload_host(self, changed_modules)

        def on_restart(self) -> None:
            pass

        def on_save_instance_state(self) -> None:
            pass

        def on_restore_instance_state(self) -> None:
            pass

        def set_args(self, args: Any) -> None:
            _set_args(self, args)

        def _get_nav_args(self) -> Dict[str, Any]:
            return self._args

        def _push(self, component: Any, args: Optional[Dict[str, Any]] = None) -> None:
            screen_path = _resolve_component_path(component)
            Navigator = jclass(f"{self.native_instance.getPackageName()}.Navigator")
            args_json = json.dumps(args) if args else None
            Navigator.push(self.native_instance, screen_path, args_json)

        def _pop(self) -> None:
            try:
                Navigator = jclass(f"{self.native_instance.getPackageName()}.Navigator")
                Navigator.pop(self.native_instance)
            except Exception:
                self.native_instance.finish()

        def _reset_to_root(self) -> None:
            """Pop everything above the root view-controller (best-effort)."""
            try:
                Navigator = jclass(f"{self.native_instance.getPackageName()}.Navigator")
                reset_fn = getattr(Navigator, "popToRoot", None)
                if reset_fn is not None:
                    reset_fn(self.native_instance)
            except Exception:
                pass

        def _set_screen_options(self, options: Dict[str, Any]) -> None:
            """Bind screen options (title, etc.) to the native action bar."""
            title = options.get("title") if isinstance(options, dict) else None
            try:
                activity = self.native_instance
                if hasattr(activity, "setTitle") and title:
                    activity.setTitle(title)
            except Exception:
                pass

        def _attach_root(self, native_view: Any) -> None:
            container = None
            try:
                from .utils import get_android_fragment_container

                container = get_android_fragment_container()
                try:
                    container.removeAllViews()
                except Exception:
                    pass
                # When the user pops back to a previously mounted screen,
                # ``native_view`` is the root from the prior mount and may
                # still be parented under the old (destroyed) FrameLayout.
                # ViewGroup.addView() throws if a view already has a
                # parent, so detach it from the old one before re-attaching
                # to the freshly created container.
                try:
                    old_parent = native_view.getParent()
                    if old_parent is not None:
                        old_parent.removeView(native_view)
                except Exception:
                    pass
                LayoutParams = jclass("android.view.ViewGroup$LayoutParams")
                lp = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
                container.addView(native_view, lp)
            except Exception:
                self.native_instance.setContentView(native_view)
                container = native_view

            if container is not None:
                _android_register_layout_listener(self, container)
                _android_push_initial_viewport(self, container)

        def _detach_root(self, native_view: Any) -> None:
            try:
                from .utils import get_android_fragment_container

                container = get_android_fragment_container()
                container.removeAllViews()
            except Exception:
                pass

        def set_viewport_size(self, width: float, height: float) -> None:
            """Public hook for native code to push viewport sizes (Maestro/tests)."""
            _push_viewport_size(self, width, height)

elif IS_DESKTOP:
    # ------------------------------------------------------------------
    # Desktop preview host (Tkinter), driven by ``pn preview``.
    #
    # The screen host owns the reconciler + lifecycle just like the
    # device hosts; placement of the root view and the navigation stack
    # are delegated to the ``DesktopApp`` controller in
    # ``pythonnative.preview`` (passed in as ``native_instance``). The
    # controller runs the Tk event loop on the main thread and polls
    # ``drain_desktop_scheduled_renders`` so renders requested from the
    # asyncio worker thread are applied on the main thread.
    # ------------------------------------------------------------------

    _DESKTOP_SCHEDULED_RENDER_HOSTS: Dict[int, Any] = {}
    _desktop_render_lock = threading.Lock()

    def _schedule_render_async(host: Any) -> bool:
        """Queue an off-main-thread render for the Tk poll loop to drain.

        Renders requested on the Tk main thread (button handlers, etc.)
        run synchronously (returns ``False``); requests from the asyncio
        worker thread are queued and applied by
        [`drain_desktop_scheduled_renders`][pythonnative.screen.drain_desktop_scheduled_renders].
        """
        if not IS_DESKTOP:
            return False
        if threading.current_thread() is threading.main_thread():
            return False
        if getattr(host, "_render_scheduled", False):
            return True
        host._render_scheduled = True
        with _desktop_render_lock:
            _DESKTOP_SCHEDULED_RENDER_HOSTS[id(host)] = host
        return True

    def drain_desktop_scheduled_renders() -> None:
        """Apply renders queued from worker threads (called on the main thread)."""
        with _desktop_render_lock:
            hosts = list(_DESKTOP_SCHEDULED_RENDER_HOSTS.values())
            _DESKTOP_SCHEDULED_RENDER_HOSTS.clear()
        _flush_scheduled_renders(hosts)

    class _ScreenHost:
        """Desktop host backed by a Tk window and an in-process nav stack.

        Created by ``pythonnative.preview`` for
        each screen on the navigation stack. ``native_instance`` is the
        ``DesktopApp`` controller, which provides the stage frame,
        viewport size, and push/pop primitives.
        """

        def __init__(self, native_instance: Any = None, component_path: str = "", component_func: Any = None) -> None:
            self.native_instance = native_instance
            _init_host_common(self, component_path, component_func)

        def on_create(self) -> None:
            _on_create(self)

        def on_start(self) -> None:
            pass

        def on_resume(self) -> None:
            _set_host_focused(self, True)

        def on_layout(self) -> None:
            pass

        def on_pause(self) -> None:
            _set_host_focused(self, False)

        def on_stop(self) -> None:
            pass

        def on_destroy(self) -> None:
            pass

        def enable_hot_reload(self, manifest_path: str, source_root: Optional[str] = None) -> None:
            _enable_hot_reload(self, manifest_path)

        def hot_reload_tick(self) -> bool:
            return _hot_reload_tick(self)

        def reload(self, changed_modules: Optional[Sequence[str]] = None) -> None:
            _reload_host(self, changed_modules)

        def on_restart(self) -> None:
            pass

        def on_save_instance_state(self) -> None:
            pass

        def on_restore_instance_state(self) -> None:
            pass

        def set_args(self, args: Any) -> None:
            _set_args(self, args)

        def _get_nav_args(self) -> Dict[str, Any]:
            return self._args

        def _push(self, component: Any, args: Optional[Dict[str, Any]] = None) -> None:
            screen_path = _resolve_component_path(component)
            app = self.native_instance
            if app is None or not hasattr(app, "push_screen"):
                raise RuntimeError("desktop navigation requires a running `pn preview` session")
            app.push_screen(screen_path, args)

        def _pop(self) -> None:
            app = self.native_instance
            if app is not None and hasattr(app, "pop_screen"):
                app.pop_screen()

        def _reset_to_root(self) -> None:
            app = self.native_instance
            if app is not None and hasattr(app, "reset_to_root"):
                try:
                    app.reset_to_root()
                except Exception:
                    pass

        def _set_screen_options(self, options: Dict[str, Any]) -> None:
            title = options.get("title") if isinstance(options, dict) else None
            app = self.native_instance
            if title and app is not None and hasattr(app, "set_title"):
                try:
                    app.set_title(str(title))
                except Exception:
                    pass

        def _attach_root(self, native_view: Any) -> None:
            from .native_views import desktop as _desktop_backend

            stage = _desktop_backend.get_root_container()
            if stage is not None and native_view is not None:
                try:
                    native_view.place(in_=stage, x=0, y=0, relwidth=1.0, relheight=1.0)
                    native_view.lift()
                except Exception:
                    pass
            app = self.native_instance
            if app is not None and hasattr(app, "viewport_size"):
                try:
                    width, height = app.viewport_size()
                    if width > 0 and height > 0:
                        _push_viewport_size(self, float(width), float(height))
                except Exception:
                    pass

        def _detach_root(self, native_view: Any) -> None:
            if native_view is not None:
                try:
                    native_view.place_forget()
                except Exception:
                    pass

        def set_viewport_size(self, width: float, height: float) -> None:
            """Push a viewport-size change (called on window resize)."""
            _push_viewport_size(self, width, height)

else:
    from typing import Dict as _Dict

    _rubicon_available = False
    try:
        from rubicon.objc import SEL, ObjCClass, ObjCInstance, objc_method

        _rubicon_available = True

        import gc as _gc

        _gc.disable()
    except ImportError:
        pass

    # Redirect Python's stdout/stderr through fd 2 so ``print()`` output is
    # visible via ``xcrun simctl launch --console-pty``. This runs at
    # ``pythonnative.screen`` import time, i.e. before any user app module
    # (e.g. ``app.main``) is imported, so their top-level ``print()``
    # calls are captured too. Gated on ``IS_IOS`` rather than rubicon-objc
    # being importable, so installing the ``[ios]`` extra on macOS does
    # not silently swap ``sys.stdout`` on a dev machine.
    if IS_IOS:
        try:
            from . import _ios_log

            _ios_log.install()
        except Exception:
            pass

    _IOS_SCREEN_REGISTRY: _Dict[int, Any] = {}
    _IOS_SCHEDULED_RENDER_HOSTS: _Dict[int, Any] = {}
    _ios_render_scheduler_target: Any = None
    _ios_native_render_scheduler: Any = None

    def _objc_addr(obj: Any) -> Optional[int]:
        """Return the underlying address of an ``ObjCInstance`` as an int.

        rubicon-objc exposes the pointer as ``ObjCInstance.ptr``, but
        the concrete type varies between releases:

        - On rubicon-objc 0.5.x ``ptr`` is ``bytes`` (the raw 8-byte,
          little-endian address) — ``int(ptr)`` raises ``ValueError``
          because Python tries to parse the bytes as a decimal string.
        - Older releases return a ``c_void_p`` for which ``int(ptr)``
          works.
        - Pure-Python integers also occur (e.g., when the caller has
          already converted).

        This helper covers all three so the screen-host registry is
        keyed under the same integer Swift sends back via
        ``forward_lifecycle``. Returns ``None`` only if every conversion
        path fails, in which case the caller logs a diagnostic.
        """
        ptr = getattr(obj, "ptr", None)
        if ptr is None:
            return None
        if isinstance(ptr, (bytes, bytearray)):
            try:
                return int.from_bytes(ptr, byteorder=sys.byteorder, signed=False)
            except Exception:
                return None
        if isinstance(ptr, int):
            return ptr
        value = getattr(ptr, "value", None)
        if isinstance(value, int):
            return value
        try:
            return int(ptr)
        except Exception:
            return None

    def _log_pn(msg: str) -> None:
        """Emit optional diagnostics when ``PYTHONNATIVE_DEBUG`` is enabled."""
        if not _debug_enabled():
            return
        try:
            print(f"[PN] {msg}", flush=True)
        except Exception:
            pass

    def _ios_register_screen(vc_instance: Any, host_obj: Any) -> None:
        ptr = _objc_addr(vc_instance)
        if ptr is None:
            _log_pn(f"register_screen: could not extract address from {type(vc_instance).__name__}")
            return
        _IOS_SCREEN_REGISTRY[ptr] = host_obj
        _log_pn(f"register_screen: addr={ptr} (registry size={len(_IOS_SCREEN_REGISTRY)})")

    def _ios_unregister_screen(vc_instance: Any) -> None:
        ptr = _objc_addr(vc_instance)
        if ptr is None:
            return
        _IOS_SCREEN_REGISTRY.pop(ptr, None)

    def _flush_ios_scheduled_renders() -> None:
        hosts = list(_IOS_SCHEDULED_RENDER_HOSTS.values())
        _IOS_SCHEDULED_RENDER_HOSTS.clear()
        if hosts:
            _log_pn(f"render_scheduler: flushing {len(hosts)} host(s)")
        _flush_scheduled_renders(hosts)

    def drain_ios_scheduled_renders() -> None:
        """Entry point used by the iOS template to drain pending renders."""
        _flush_ios_scheduled_renders()

    def _schedule_ios_native_render_drain() -> bool:
        """Wake the iOS template so it drains renders on the main thread."""
        global _ios_native_render_scheduler
        try:
            if _ios_native_render_scheduler is None:
                import ctypes as _ct

                scheduler = _ct.CDLL(None).pn_schedule_render_drain
                scheduler.restype = None
                scheduler.argtypes = []
                _ios_native_render_scheduler = scheduler
            _ios_native_render_scheduler()
            return True
        except Exception as exc:
            _log_pn(f"render_scheduler: native iOS wake failed: {exc!r}")
            return False

    def forward_lifecycle(native_addr: int, event: str) -> None:
        """Forward a Swift `UIViewController` lifecycle event to its host.

        Args:
            native_addr: Pointer (`int`) of the calling
                `UIViewController` instance, used to look up the
                registered host.
            event: Lifecycle method name (e.g., `"on_resume"`).
        """
        try:
            key = int(native_addr)
        except Exception as e:
            _log_pn(f"forward_lifecycle: bad native_addr={native_addr!r}: {e!r}")
            return
        host = _IOS_SCREEN_REGISTRY.get(key)
        if host is None:
            _log_pn(
                f"forward_lifecycle: NO HOST for event={event!r} addr={key} "
                f"(registry has {len(_IOS_SCREEN_REGISTRY)} entry(ies): "
                f"{list(_IOS_SCREEN_REGISTRY.keys())})"
            )
            return
        handler = getattr(host, event, None)
        if handler is None:
            _log_pn(f"forward_lifecycle: host has no '{event}' attr")
            return
        try:
            handler()
        except Exception as e:
            _log_pn(f"forward_lifecycle: '{event}' handler raised: {e!r}")

    if _rubicon_available and IS_IOS:
        NSObject = ObjCClass("NSObject")

        class _PNRenderSchedulerTarget(NSObject):  # type: ignore[misc, valid-type]
            @objc_method
            def onRenderTimer_(self, timer: object) -> None:
                _flush_ios_scheduled_renders()

        def _ensure_ios_render_scheduler_target() -> Any:
            global _ios_render_scheduler_target

            if _ios_render_scheduler_target is None:
                target = _PNRenderSchedulerTarget.new()
                try:
                    target.retain()
                except Exception:
                    pass
                _ios_render_scheduler_target = target
            return _ios_render_scheduler_target

        def _schedule_render_async(host: Any) -> bool:
            if not IS_IOS:
                return False
            if getattr(host, "_render_scheduled", False):
                return True

            host._render_scheduled = True
            _IOS_SCHEDULED_RENDER_HOSTS[id(host)] = host
            if threading.current_thread() is not threading.main_thread():
                if _schedule_ios_native_render_drain():
                    _log_pn("_request_render: deferred iOS render via native scheduler")
                    return True
                _log_pn("_request_render: native iOS scheduler unavailable; render remains queued")
                return True
            try:
                NSTimer = ObjCClass("NSTimer")
                target = _ensure_ios_render_scheduler_target()
                NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    0.0,
                    target,
                    SEL("onRenderTimer:"),
                    None,
                    False,
                )
                _log_pn("_request_render: deferred iOS render to next run-loop turn")
                return True
            except Exception as e:
                host._render_scheduled = False
                _IOS_SCHEDULED_RENDER_HOSTS.pop(id(host), None)
                _log_pn(f"_request_render: iOS defer failed ({e!r}); rendering synchronously")
                return False

        class _ScreenHost:
            """iOS host backed by a `UIViewController`.

            Owned by the screen view-controller template. Bridges iOS
            lifecycle callbacks (`viewDidLoad`, `viewWillDisappear`,
            etc.) to the reconciler and the function component.
            """

            def __init__(self, native_instance: Any, component_path: str, component_func: Any) -> None:
                if isinstance(native_instance, int):
                    try:
                        native_instance = ObjCInstance(native_instance)
                    except Exception:
                        native_instance = None
                self.native_instance = native_instance
                _init_host_common(self, component_path, component_func)
                if self.native_instance is not None:
                    _ios_register_screen(self.native_instance, self)

            def on_create(self) -> None:
                _on_create(self)

            def on_start(self) -> None:
                pass

            def on_pause(self) -> None:
                _set_host_focused(self, False)

            def on_stop(self) -> None:
                pass

            def on_destroy(self) -> None:
                if self.native_instance is not None:
                    _ios_unregister_screen(self.native_instance)

            def enable_hot_reload(self, manifest_path: str, source_root: Optional[str] = None) -> None:
                _enable_hot_reload(self, manifest_path)

            def hot_reload_tick(self) -> bool:
                return _hot_reload_tick(self)

            def reload(self, changed_modules: Optional[Sequence[str]] = None) -> None:
                _reload_host(self, changed_modules)

            def on_restart(self) -> None:
                pass

            def on_save_instance_state(self) -> None:
                pass

            def on_restore_instance_state(self) -> None:
                pass

            def set_args(self, args: Any) -> None:
                _set_args(self, args)

            def _get_nav_args(self) -> Dict[str, Any]:
                return self._args

            def _push(self, component: Any, args: Optional[Dict[str, Any]] = None) -> None:
                screen_path = _resolve_component_path(component)
                ViewController = None
                try:
                    ViewController = ObjCClass("ViewController")
                except Exception:
                    try:
                        NSBundle = ObjCClass("NSBundle")
                        bundle = NSBundle.mainBundle
                        module_name = bundle.objectForInfoDictionaryKey_("CFBundleName")
                        if module_name is None:
                            module_name = bundle.objectForInfoDictionaryKey_("CFBundleExecutable")
                        if module_name:
                            ViewController = ObjCClass(f"{module_name}.ViewController")
                    except Exception:
                        pass

                if ViewController is None:
                    raise NameError("ViewController class not found; ensure Swift class is ObjC-visible")

                next_vc = ViewController.alloc().init()
                try:
                    next_vc.setValue_forKey_(screen_path, "requestedScreenPath")
                    if args:
                        next_vc.setValue_forKey_(json.dumps(args), "requestedScreenArgsJSON")
                except Exception:
                    pass
                nav = getattr(self.native_instance, "navigationController", None)
                if nav is None:
                    raise RuntimeError(
                        "No UINavigationController available; ensure template embeds root in navigation controller"
                    )
                nav.pushViewController_animated_(next_vc, True)

            def _pop(self) -> None:
                nav = getattr(self.native_instance, "navigationController", None)
                if nav is not None:
                    nav.popViewControllerAnimated_(True)

            def _reset_to_root(self) -> None:
                """Pop everything above the root view-controller."""
                nav = getattr(self.native_instance, "navigationController", None)
                if nav is not None:
                    try:
                        nav.popToRootViewControllerAnimated_(True)
                    except Exception:
                        pass

            def _set_screen_options(self, options: Dict[str, Any]) -> None:
                """Bind screen options (e.g. title) to the native nav bar.

                Setting ``UIViewController.title`` propagates to the
                view controller's ``navigationItem.title`` so the
                surrounding ``UINavigationController`` picks up the
                new title on its next layout pass.
                """
                title = options.get("title") if isinstance(options, dict) else None
                if title is None or self.native_instance is None:
                    return
                try:
                    self.native_instance.setTitle_(str(title))
                except Exception as e:
                    _log_pn(f"_set_screen_options: setTitle failed: {e!r}")

            def _attach_root(self, native_view: Any) -> None:
                root_view = self.native_instance.view
                root_view.addSubview_(native_view)
                # Use classic frame-based layout for the root container so
                # the layout engine's per-child frames inside it are honored
                # without competing with Auto Layout constraints.
                try:
                    native_view.setTranslatesAutoresizingMaskIntoConstraints_(True)
                    native_view.setAutoresizingMask_(2 | 16)  # FlexibleWidth | FlexibleHeight
                except Exception:
                    pass
                self._sync_root_frame(native_view)
                self._push_viewport_from_root(native_view)

            def _detach_root(self, native_view: Any) -> None:
                try:
                    native_view.removeFromSuperview()
                except Exception:
                    pass

            def _sync_root_frame(self, native_view: Any) -> None:
                """Position the root view below the top safe area, full-bleed at the bottom.

                The frame intentionally extends *past* the bottom
                safe-area inset so a tab bar can reach the home
                indicator (otherwise it floats with an empty 34 pt
                gap below it). The bottom inset itself is published
                via `pythonnative.platform_metrics` so handlers like
                [`TabBarHandler`][pythonnative.native_views.ios.TabBarHandler]
                can absorb it into their intrinsic height. Apps that
                render content directly at the bottom (no tab bar)
                opt back into safe-area padding via ``SafeAreaView``
                or by reading the insets explicitly.

                Uses ``safeAreaInsets`` rather than
                ``safeAreaLayoutGuide.layoutFrame`` because the
                latter returns ``CGRectZero`` until UIKit has run its
                first layout pass; the insets are populated as soon
                as the controller's view is in a window, which is
                reliably true by the time ``viewDidLayoutSubviews``
                fires.
                """
                root_view = self.native_instance.view
                if root_view is None:
                    _log_pn("sync_root_frame: root_view is None, skipping")
                    return
                try:
                    bounds = root_view.bounds
                    insets = root_view.safeAreaInsets
                    bw = float(bounds.size.width)
                    bh = float(bounds.size.height)
                    top = float(insets.top)
                    left = float(insets.left)
                    right = float(insets.right)
                    bottom = float(insets.bottom)
                    w = max(0.0, bw - left - right)
                    h = max(0.0, bh - top)
                    _log_pn(
                        "sync_root_frame: "
                        f"root.bounds=({bw:.1f},{bh:.1f}) "
                        f"insets=(t{top:.1f},l{left:.1f},b{bottom:.1f},r{right:.1f}) "
                        f"-> child frame=({left:.1f},{top:.1f},{w:.1f},{h:.1f}) "
                        f"(bottom inset {bottom:.1f} published to platform_metrics)"
                    )
                    try:
                        from . import platform_metrics

                        platform_metrics.set_safe_area_insets(0.0, left, bottom, right)
                    except Exception as e:
                        _log_pn(f"sync_root_frame: publish insets failed: {e!r}")
                    if w > 0 and h > 0:
                        native_view.setFrame_(((left, top), (w, h)))
                        return
                except Exception as e:
                    _log_pn(f"sync_root_frame: insets-path failed: {e!r}")
                try:
                    bounds = root_view.bounds
                    bw2 = float(bounds.size.width)
                    bh2 = float(bounds.size.height)
                    _log_pn(f"sync_root_frame: fallback to bounds=({bw2:.1f},{bh2:.1f})")
                    native_view.setFrame_(((0, 0), (bw2, bh2)))
                except Exception as e:
                    _log_pn(f"sync_root_frame: bounds fallback failed: {e!r}")

            def _push_viewport_from_root(self, native_view: Any) -> None:
                """Push the root view's measured size into the reconciler."""
                try:
                    bounds = native_view.bounds
                    w = float(bounds.size.width)
                    h = float(bounds.size.height)
                    source = "native_view.bounds"
                    if w <= 0 or h <= 0:
                        UIScreen = ObjCClass("UIScreen")
                        screen_bounds = UIScreen.mainScreen.bounds
                        w = float(screen_bounds.size.width)
                        h = float(screen_bounds.size.height)
                        source = "UIScreen.mainScreen.bounds"
                    _log_pn(f"push_viewport: ({w:.1f},{h:.1f}) from {source}")
                    _push_viewport_size(self, w, h)
                except Exception as e:
                    _log_pn(f"push_viewport: failed: {e!r}")

            def on_layout(self) -> None:
                # Forwarded from ``viewDidLayoutSubviews``: the safe area
                # insets are now valid (initial layout, rotation,
                # multitasking, …). Re-sync the root frame and push the
                # viewport so the layout engine matches the visible area.
                if self._root_native_view is None:
                    _log_pn("on_layout: no root_native_view yet, skipping")
                    return
                _log_pn("on_layout: re-syncing")
                self._sync_root_frame(self._root_native_view)
                self._push_viewport_from_root(self._root_native_view)

            def on_resume(self) -> None:
                # ``viewDidAppear`` always follows ``viewDidLayoutSubviews``,
                # but trigger one extra sync here for safety in case a
                # template overrides the layout call without forwarding.
                _set_host_focused(self, True)
                if self._root_native_view is None:
                    _log_pn("on_resume: no root_native_view yet, skipping")
                    return
                _log_pn("on_resume: re-syncing")
                self._sync_root_frame(self._root_native_view)
                self._push_viewport_from_root(self._root_native_view)

            def set_viewport_size(self, width: float, height: float) -> None:
                """Public hook for native code (Swift) to push viewport sizes."""
                _push_viewport_size(self, width, height)

    else:

        class _ScreenHost:
            """Desktop stub used when no native runtime is available.

            Fully functional for unit tests when a mock backend is
            installed via
            [`set_registry`][pythonnative.native_views.set_registry].
            Calls to navigation methods raise `RuntimeError` because
            there is no native navigation stack to push onto.
            """

            def __init__(
                self,
                native_instance: Any = None,
                component_path: str = "",
                component_func: Any = None,
            ) -> None:
                self.native_instance = native_instance
                _init_host_common(self, component_path, component_func)

            def on_create(self) -> None:
                _on_create(self)

            def on_start(self) -> None:
                pass

            def on_resume(self) -> None:
                pass

            def on_layout(self) -> None:
                pass

            def on_pause(self) -> None:
                pass

            def on_stop(self) -> None:
                pass

            def on_destroy(self) -> None:
                pass

            def enable_hot_reload(self, manifest_path: str, source_root: Optional[str] = None) -> None:
                _enable_hot_reload(self, manifest_path)

            def hot_reload_tick(self) -> bool:
                return _hot_reload_tick(self)

            def reload(self, changed_modules: Optional[Sequence[str]] = None) -> None:
                _reload_host(self, changed_modules)

            def on_restart(self) -> None:
                pass

            def on_save_instance_state(self) -> None:
                pass

            def on_restore_instance_state(self) -> None:
                pass

            def set_args(self, args: Any) -> None:
                _set_args(self, args)

            def _get_nav_args(self) -> Dict[str, Any]:
                return self._args

            def _push(self, component: Any, args: Optional[Dict[str, Any]] = None) -> None:
                raise RuntimeError("navigate() requires a native runtime (iOS or Android)")

            def _pop(self) -> None:
                raise RuntimeError("go_back() requires a native runtime (iOS or Android)")

            def _reset_to_root(self) -> None:
                pass

            def _set_screen_options(self, options: Dict[str, Any]) -> None:
                """No-op on desktop; native hosts override this."""
                return

            def _attach_root(self, native_view: Any) -> None:
                pass

            def _detach_root(self, native_view: Any) -> None:
                pass


# ======================================================================
# Public factory
# ======================================================================


def create_screen(
    component_path: str,
    native_instance: Any = None,
    args_json: Optional[str] = None,
) -> _ScreenHost:
    """Create a screen host for a function component.

    Called by native templates (`ScreenFragment.kt` on Android,
    `ViewController.swift` on iOS) to bridge the native lifecycle to a
    [`@component`][pythonnative.component] function.

    Args:
        component_path: Either a module path like `"app.main"` (the
            module's top-level ``App`` attribute is used) or a dotted
            attribute path like `"app.main.RootScreen"`. The function
            is imported lazily so user modules can be reloaded by the
            dev server.
        native_instance: The native `Activity` (Android) or
            `UIViewController` (iOS) pointer that owns this screen.
        args_json: Optional JSON string of navigation arguments to pass
            to the component on first render.

    Returns:
        A `_ScreenHost` ready to receive lifecycle callbacks (`on_create`,
        `on_pause`, etc.) from the platform.

    Example:
        ```python
        host = pythonnative.screen.create_screen(
            "app.main",
            native_instance,
            args_json='{"id": 42}',
        )
        host.on_create()
        ```
    """
    component_func = _import_component(component_path)
    host = _ScreenHost(native_instance, component_path, component_func)
    if args_json:
        _set_args(host, args_json)
    return host
