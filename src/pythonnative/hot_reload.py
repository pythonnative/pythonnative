"""Device-side module reloading for Fast Refresh.

The dev server (``pythonnative.devserver``) watches the project's
``app/`` directory and tells every connected dev client which files
changed. This module is the client's other half: it re-executes the
changed modules with ``importlib`` and refreshes every mounted screen.

Two strategies share the surface:

- **Fast Refresh** (default): after reloading the changed modules the
  reconciler tree is walked and every component function whose module
  was reloaded is swapped in place. Hook state, navigation state, and
  even scroll positions survive because the underlying ``VNode``
  objects are reused; the next render simply calls the new function
  bodies through the old slots.
- **Full remount**: when the in-place swap fails (e.g. the new module
  raised at import time, or a render exception bubbled out while
  running the new function), the host falls back to building a
  brand-new reconciler tree. State is lost but the app keeps running.

[`apply_reload`][pythonnative.hot_reload.apply_reload] is the single
entry point: it reloads once per process (several screens may be
mounted) and then refreshes each live host.

On device, sources arrive in a writable **overlay** directory that
shadows the app bundle (see
[`configure_dev_environment`][pythonnative.hot_reload.configure_dev_environment]);
under ``pn preview`` the project directory itself is on ``sys.path``
and there is no overlay.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

__all__ = [
    "DEV_ROOT_DIR",
    "ModuleReloader",
    "ReloadResult",
    "apply_reload",
    "configure_dev_environment",
    "overlay_root",
]

DEV_ROOT_DIR = "pythonnative_dev"
"""Name of the writable on-device directory that shadows bundled app code."""

_OVERLAY_ENV = "PYTHONNATIVE_HOT_RELOAD_ROOT"


def configure_dev_environment(writable_root: str, server_url: Optional[str] = None) -> str:
    """Create and prioritize the writable source overlay.

    The returned directory is inserted at the front of `sys.path`, so a
    synced `app/main.py` shadows the copy bundled into the native
    application. Debug templates call this before importing user code.

    Args:
        writable_root: Platform data directory that the app can write to
            (Android `filesDir`, iOS `Documents`, or a test directory).
        server_url: The dev server this launch should connect to, when
            the launcher passed one (``pn run`` does, through a launch
            environment variable on iOS and an intent extra on
            Android). It is exported as ``PN_DEV_SERVER`` so the dev
            client picks it up; a remembered server is used otherwise.

    Returns:
        Absolute path to the overlay root.
    """
    dev_root = os.path.abspath(os.path.join(writable_root, DEV_ROOT_DIR))
    os.makedirs(os.path.join(dev_root, "app"), exist_ok=True)
    if dev_root in sys.path:
        sys.path.remove(dev_root)
    sys.path.insert(0, dev_root)
    os.environ[_OVERLAY_ENV] = dev_root
    if server_url:
        os.environ["PN_DEV_SERVER"] = str(server_url)
    return dev_root


def overlay_root() -> Optional[str]:
    """The overlay directory configured for this process, if any."""
    return os.environ.get(_OVERLAY_ENV) or None


def _overlay_module_path(module_name: str) -> Optional[str]:
    dev_root = overlay_root()
    if not dev_root:
        return None

    rel_parts = module_name.split(".")
    module_path = os.path.join(dev_root, *rel_parts) + ".py"
    if os.path.exists(module_path):
        return module_path

    package_path = os.path.join(dev_root, *rel_parts, "__init__.py")
    if os.path.exists(package_path):
        return package_path

    return None


# ======================================================================
# Module reloader
# ======================================================================


class ModuleReloader:
    """Reload changed Python modules and rewrite mounted trees to match.

    All methods are static; the class is a namespace. The tree-rewrite
    helpers (``build_replacement_map``, ``swap_components_in_tree``,
    ``refresh_in_place``) are what make Fast Refresh state-preserving.
    """

    _reload_lock = threading.Lock()

    @staticmethod
    def reload_module(module_name: str) -> bool:
        """Reload a single module by its dotted name.

        Args:
            module_name: Dotted module name (e.g., `"app.main"`).

        Returns:
            `True` if the module imported successfully from the current
            `sys.path`; `False` otherwise (the previous module object is
            restored so the app keeps running).
        """
        previous = sys.modules.get(module_name)
        try:
            importlib.invalidate_caches()
            overlay_path = _overlay_module_path(module_name)
            if overlay_path is not None:
                spec = importlib.util.spec_from_file_location(module_name, overlay_path)
                if spec is None or spec.loader is None:
                    return False
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                sys.modules.pop(module_name, None)
                importlib.import_module(module_name)
            return True
        except Exception:
            if previous is not None:
                sys.modules[module_name] = previous
            else:
                sys.modules.pop(module_name, None)
            return False

    @staticmethod
    def reload_modules(module_names: Sequence[str]) -> List[str]:
        """Reload ``module_names`` in order, returning the names that succeeded."""
        importlib.invalidate_caches()
        reloaded: List[str] = []
        seen: set[str] = set()
        with ModuleReloader._reload_lock:
            for module_name in module_names:
                if not module_name or module_name in seen:
                    continue
                seen.add(module_name)
                if ModuleReloader.reload_module(module_name):
                    reloaded.append(module_name)
        return reloaded

    @staticmethod
    def reload_module_strict(module_name: str) -> None:
        """Reload one module, propagating the import error instead of swallowing it.

        Used by the dev client so a syntax error in a saved file shows
        up in the RedBox and the terminal rather than as a silent
        "nothing reloaded".
        """
        previous = sys.modules.get(module_name)
        try:
            importlib.invalidate_caches()
            overlay_path = _overlay_module_path(module_name)
            if overlay_path is not None:
                spec = importlib.util.spec_from_file_location(module_name, overlay_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"cannot load {module_name} from {overlay_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                sys.modules.pop(module_name, None)
                importlib.import_module(module_name)
        except Exception:
            if previous is not None:
                sys.modules[module_name] = previous
            else:
                sys.modules.pop(module_name, None)
            raise

    @staticmethod
    def expand_reload_targets(changed_modules: Sequence[str], component_path: str) -> List[str]:
        """Expand a set of changed modules into the full reload order.

        When a user edits ``app/screens/home.py``, only that module is
        reported. But the entry-point module ``app.main`` has bindings
        like ``from app.screens.home import HomeScreen`` that need to be
        re-evaluated against the freshly-loaded ``app.screens.home``;
        likewise other user-app modules may carry transitive bindings
        (e.g. through a shared ``app/theme.py``) that go stale if only
        the changed file is reloaded.

        The order is:

        1. Explicitly changed modules first (in the order given), so
           their fresh source replaces the cached version in
           ``sys.modules`` before any dependent modules re-execute.
        2. All other currently-imported modules under the entry-point's
           top-level package, deepest first. The depth heuristic biases
           toward leaves so re-executing a screen file picks up the
           newest shared utilities before the file that imports it does.
        3. The entry-point module itself, last, so its
           ``from ... import`` bindings rebind against everything that
           was refreshed in steps 1 and 2.

        Modules outside the entry-point's top-level package
        (``pythonnative.*``, stdlib, third-party) are never included;
        framework code is not reloaded.

        Args:
            changed_modules: Modules reported as changed (dotted form).
            component_path: The host's entry-point identifier, either a
                module path (``"app.main"``) or a dotted attribute path
                (``"app.main.RootScreen"``).

        Returns:
            The ordered list of modules to feed to
            [`reload_modules`][pythonnative.hot_reload.ModuleReloader.reload_modules].
        """
        entry_module: Optional[str] = None
        if component_path in sys.modules:
            entry_module = component_path
        elif "." in component_path:
            parent = component_path.rsplit(".", 1)[0]
            if parent in sys.modules:
                entry_module = parent

        app_prefix: Optional[str] = None
        if entry_module:
            app_prefix = entry_module.split(".")[0]
        else:
            for m in changed_modules:
                if m:
                    app_prefix = m.split(".")[0]
                    break

        app_modules: Set[str] = set()
        if app_prefix:
            for name in list(sys.modules):
                if name == app_prefix or name.startswith(app_prefix + "."):
                    app_modules.add(name)

        ordered: List[str] = []
        seen: Set[str] = set()
        for m in changed_modules:
            if m and m not in seen:
                ordered.append(m)
                seen.add(m)

        others = [m for m in app_modules if m not in seen and m != entry_module]
        others.sort(key=lambda m: (-m.count("."), m))
        for m in others:
            ordered.append(m)
            seen.add(m)

        if entry_module:
            if entry_module in seen:
                ordered.remove(entry_module)
            ordered.append(entry_module)

        return ordered

    @staticmethod
    def file_to_module(file_path: str, base_dir: str = "") -> Optional[str]:
        """Convert a file path to a dotted module name.

        Args:
            file_path: Path to a `.py` file (absolute or relative).
            base_dir: Base directory that names should be relative to.
                If empty, `file_path` is treated as already relative.

        Returns:
            The dotted module name (e.g., `"app.screens.home"`), or
            `None` for an empty path.
        """
        rel = os.path.relpath(file_path, base_dir) if base_dir else file_path
        rel = rel.replace("\\", os.sep).replace("/", os.sep).lstrip(os.sep)
        if rel.endswith(".py"):
            rel = rel[:-3]
        parts = rel.replace(os.sep, ".").split(".")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else None

    @staticmethod
    def modules_from_files(file_paths: Sequence[str], base_dir: str = "") -> List[str]:
        """Convert Python source paths to importable module names."""
        modules: List[str] = []
        for file_path in file_paths:
            module = ModuleReloader.file_to_module(file_path, base_dir=base_dir)
            if module is not None:
                modules.append(module)
        return modules

    @staticmethod
    def find_replacement_function(old_fn: Any) -> Optional[Any]:
        """Locate a function's post-reload counterpart by qualname.

        [`Component`][pythonnative.Component] objects forward
        ``__module__`` / ``__qualname__`` from the render function they
        wrap, so the reconciler's stored ``element.type`` carries the
        information needed to re-resolve after a module reload.

        Args:
            old_fn: The function captured in an
                [`Element`][pythonnative.Element]'s ``type`` slot.

        Returns:
            The reloaded module's matching function, ``None`` if no
            replacement was found, or the original function itself
            when the module has not been reloaded (so callers can
            skip the swap).
        """
        module_name = getattr(old_fn, "__module__", None)
        qualname = getattr(old_fn, "__qualname__", None) or getattr(old_fn, "__name__", None)
        if not module_name or not qualname:
            return None
        if "<locals>" in qualname:
            return None  # nested functions are not addressable from the module surface

        module = sys.modules.get(module_name)
        if module is None:
            return None

        obj: Any = module
        for part in qualname.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                return None

        if obj is old_fn:
            return None
        return obj

    @staticmethod
    def build_replacement_map(reconciler: Any, reloaded_modules: Iterable[str]) -> Dict[Any, Any]:
        """Compute ``{old_function: new_function}`` for one tree.

        The reconciler's stored tree references the *pre-reload*
        component functions through ``VNode.element.type``. This
        method walks the tree, collects every callable type whose
        ``__module__`` was just reloaded, and asks
        [`find_replacement_function`][pythonnative.hot_reload.ModuleReloader.find_replacement_function]
        for its successor.

        Args:
            reconciler: The reconciler whose mounted ``root`` should be inspected.
            reloaded_modules: Set of module names that were just
                reloaded (only callables from these modules are
                considered).

        Returns:
            A mapping suitable for passing to
            [`swap_components_in_tree`][pythonnative.hot_reload.ModuleReloader.swap_components_in_tree].
        """
        modules: Set[str] = {m for m in reloaded_modules if m}
        if not modules or reconciler is None or getattr(reconciler, "root", None) is None:
            return {}

        seen: Set[int] = set()
        mapping: Dict[Any, Any] = {}

        def visit(vnode: Any) -> None:
            if vnode is None:
                return
            elem = getattr(vnode, "element", None)
            if elem is not None and callable(elem.type):
                fn = elem.type
                fn_id = id(fn)
                if fn_id not in seen:
                    seen.add(fn_id)
                    if getattr(fn, "__module__", None) in modules:
                        replacement = ModuleReloader.find_replacement_function(fn)
                        if replacement is not None and replacement is not fn:
                            mapping[fn] = replacement
            for child in getattr(vnode, "children", []) or []:
                visit(child)

        visit(reconciler.root)
        return mapping

    @staticmethod
    def swap_components_in_tree(reconciler: Any, replacement_map: Dict[Any, Any]) -> int:
        """Apply a ``{old: new}`` map to every node in the reconciler tree.

        Mutates ``vnode.element.type`` directly so the NEXT diff sees
        identical types and reuses VNodes (preserving hook state).
        The element lists stored on ``vnode.rendered`` are rewritten
        too because the reconciler reads from them when comparing keys
        across renders.

        Returns:
            The number of element type references that were rewritten.
        """
        if not replacement_map or reconciler is None or getattr(reconciler, "root", None) is None:
            return 0

        rewrites = 0

        def rewrite_element_tree(element: Any) -> None:
            nonlocal rewrites
            if element is None:
                return
            new_type = replacement_map.get(element.type)
            if new_type is not None:
                element.type = new_type
                rewrites += 1
            for child in element.children or []:
                rewrite_element_tree(child)

        def visit(vnode: Any) -> None:
            if vnode is None:
                return
            if getattr(vnode, "element", None) is not None:
                rewrite_element_tree(vnode.element)
            rendered = getattr(vnode, "rendered", None)
            if isinstance(rendered, (list, tuple)):
                for rendered_el in rendered:
                    rewrite_element_tree(rendered_el)
            elif rendered is not None:
                rewrite_element_tree(rendered)
            for child in getattr(vnode, "children", []) or []:
                visit(child)

        visit(reconciler.root)
        return rewrites

    @staticmethod
    def refresh_in_place(reconciler: Any, reloaded_modules: Iterable[str]) -> bool:
        """Try a state-preserving Fast Refresh for one reconciler.

        Returns:
            ``True`` if any component function was replaced (callers
            should then trigger a re-render). ``False`` means the
            tree already references the latest functions (or has no
            nodes from the reloaded modules at all).
        """
        replacement_map = ModuleReloader.build_replacement_map(reconciler, reloaded_modules)
        if not replacement_map:
            return False
        rewrites = ModuleReloader.swap_components_in_tree(reconciler, replacement_map)
        if rewrites > 0 and hasattr(reconciler, "reset_hook_signatures"):
            # New component bodies may legitimately call a different
            # hook sequence; forget the recorded signatures so the
            # dev-mode order guard doesn't flag the refresh itself.
            reconciler.reset_hook_signatures()
        return rewrites > 0


# ======================================================================
# Process-wide reload
# ======================================================================


@dataclass
class ReloadResult:
    """What [`apply_reload`][pythonnative.hot_reload.apply_reload] did.

    Attributes:
        requested: Modules the caller reported as changed.
        reloaded: Modules actually re-executed (in reload order).
        mode: ``"fast_refresh"`` when every host refreshed in place,
            ``"remount"`` when at least one fell back to a full remount,
            ``"error"`` when a host hit an exception (shown in its
            RedBox), or ``"none"`` when nothing could be reloaded.
        error: The import error text when a changed module failed to
            execute (the previous module stays in ``sys.modules``).
        hosts: Number of hosts refreshed.
    """

    requested: List[str] = field(default_factory=list)
    reloaded: List[str] = field(default_factory=list)
    mode: str = "none"
    error: Optional[str] = None
    hosts: int = 0


def apply_reload(changed_modules: Sequence[str], hosts: Optional[Sequence[Any]] = None) -> ReloadResult:
    """Reload ``changed_modules`` once and refresh every mounted screen.

    Args:
        changed_modules: Dotted module names whose source changed.
        hosts: Screen hosts to refresh; defaults to every live host on
            the current platform (``pythonnative.hosts.live_hosts``).

    Returns:
        A [`ReloadResult`][pythonnative.hot_reload.ReloadResult].
    """
    import traceback

    from . import diagnostics

    if hosts is None:
        from .hosts import live_hosts

        hosts = list(live_hosts())
    result = ReloadResult(requested=[m for m in changed_modules if m])
    if not result.requested or not hosts:
        # Nothing changed, or nothing is mounted yet (the files landed
        # before the first screen, and the first import will read them).
        return result
    entry = hosts[0].component_path
    # A changed module that was never imported needs no re-execution;
    # re-running the entry module (always last) imports it if it's used.
    imported = [m for m in result.requested if m in sys.modules]
    targets = ModuleReloader.expand_reload_targets(imported, entry)

    # Changed modules are reloaded strictly so a syntax error is reported
    # with its traceback; the dependents (which didn't change) reload
    # leniently, since a failure there is almost always caused by the
    # same error and would only repeat it.
    reloaded: List[str] = []
    for name in targets:
        if name in imported:
            try:
                ModuleReloader.reload_module_strict(name)
            except Exception as exc:
                result.error = traceback.format_exc()
                for host in hosts:
                    if diagnostics.is_dev():
                        host.show_redbox(exc, phase=f"reloading {name}")
                result.mode = "error"
                return result
            reloaded.append(name)
        elif ModuleReloader.reload_module(name):
            reloaded.append(name)
    result.reloaded = reloaded
    if not reloaded:
        return result

    modes: List[str] = []
    for host in hosts:
        try:
            modes.append(host.refresh(reloaded))
        except Exception as exc:
            result.error = traceback.format_exc()
            if diagnostics.is_dev():
                host.show_redbox(exc, phase="hot reload")
            modes.append("error")
    result.hosts = len(hosts)
    if "error" in modes:
        result.mode = "error"
    elif "remount" in modes:
        result.mode = "remount"
    elif "fast_refresh" in modes:
        result.mode = "fast_refresh"
    else:
        result.mode = "fast_refresh"
    return result
