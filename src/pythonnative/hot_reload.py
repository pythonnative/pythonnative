"""Hot-reload support for PythonNative development.

Two cooperating pieces:

- **Host-side**: [`FileWatcher`][pythonnative.hot_reload.FileWatcher]
  polls the developer's ``app/`` directory for ``.py`` changes and
  triggers a callback (typically ``adb push`` on Android or a
  ``simctl`` file copy on iOS).
- **Device-side**:
  [`ModuleReloader`][pythonnative.hot_reload.ModuleReloader] reloads
  changed Python modules using ``importlib`` and asks the screen
  host to re-render its current tree.

Two strategies share the device-side surface:

- **Fast Refresh** (default): after reloading the changed modules
  the reconciler tree is walked and every component function whose
  module was reloaded is swapped in place. Hook state, navigation
  state, and even scroll positions survive because the underlying
  ``VNode`` objects are reused — the next render simply calls the
  new function bodies through the old slots.
- **Full remount**: when the in-place swap fails (e.g. the new
  module raised at import time, or a render exception bubbled out
  while running the new function), the host falls back to building
  a brand-new reconciler tree. State is lost but the app keeps
  running.

Example:
    Integrated into ``pn run --hot-reload``:

    ```python
    from pythonnative.hot_reload import FileWatcher

    def push(changed):
        for path in changed:
            print("changed:", path)

    watcher = FileWatcher("app/", on_change=push)
    watcher.start()
    ```
"""

import importlib
import importlib.util
import json
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

DEV_ROOT_DIR = "pythonnative_dev"
"""Name of the writable on-device directory that shadows bundled app code."""

RELOAD_MANIFEST = "reload.json"
"""Manifest filename written by the host and polled by native templates."""


def configure_dev_environment(writable_root: str) -> str:
    """Create and prioritize the writable hot-reload source overlay.

    The returned directory is inserted at the front of `sys.path`, so a
    pushed `app/main.py` shadows the copy bundled into the native
    application. Templates call this before importing user code.

    Args:
        writable_root: Platform data directory that the app can write to
            (Android `filesDir`, iOS `Documents`, or a test directory).

    Returns:
        Absolute path to the hot-reload overlay root.
    """
    dev_root = os.path.abspath(os.path.join(writable_root, DEV_ROOT_DIR))
    os.makedirs(os.path.join(dev_root, "app"), exist_ok=True)
    if dev_root in sys.path:
        sys.path.remove(dev_root)
    sys.path.insert(0, dev_root)
    os.environ["PYTHONNATIVE_HOT_RELOAD_ROOT"] = dev_root
    return dev_root


def manifest_path_for(dev_root: str) -> str:
    """Return the reload-manifest path inside a hot-reload overlay."""
    return os.path.join(dev_root, RELOAD_MANIFEST)


def _overlay_module_path(module_name: str) -> Optional[str]:
    dev_root = os.environ.get("PYTHONNATIVE_HOT_RELOAD_ROOT")
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
# Host-side file watcher
# ======================================================================


class FileWatcher:
    """Watch a directory tree for `.py` file changes.

    Uses simple `os.path.getmtime` polling rather than a native
    inotify/FSEvents binding so the watcher works on every platform
    where Python runs without extra dependencies.

    Args:
        watch_dir: Directory to watch (recursively).
        on_change: Called with a list of changed file paths when
            modifications are detected.
        interval: Polling interval, in seconds.

    Attributes:
        watch_dir: Directory being watched.
        on_change: Change callback.
        interval: Polling interval.
    """

    def __init__(self, watch_dir: str, on_change: Callable[[List[str]], None], interval: float = 1.0) -> None:
        self.watch_dir = watch_dir
        self.on_change = on_change
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._mtimes: Dict[str, float] = {}

    def start(self) -> None:
        """Begin watching in a background daemon thread.

        Performs an initial scan to seed mtimes so the first
        notification reflects subsequent edits, not pre-existing files.
        """
        self._running = True
        self._scan()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher and join the background thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 2)
            self._thread = None

    def _scan(self) -> List[str]:
        changed: List[str] = []
        current_files: set = set()

        for root, _dirs, files in os.walk(self.watch_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                current_files.add(fpath)
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue
                if fpath in self._mtimes:
                    if mtime > self._mtimes[fpath]:
                        changed.append(fpath)
                self._mtimes[fpath] = mtime

        for old in list(self._mtimes):
            if old not in current_files:
                del self._mtimes[old]

        return changed

    def _loop(self) -> None:
        while self._running:
            time.sleep(self.interval)
            changed = self._scan()
            if changed:
                try:
                    self.on_change(changed)
                except Exception:
                    pass


# ======================================================================
# Device-side module reloader
# ======================================================================


class ModuleReloader:
    """Reload changed Python modules on device and trigger a re-render.

    Designed to be invoked from device-side glue when a hot-reload
    push completes. The class itself holds no state; all methods are
    static.
    """

    @staticmethod
    def reload_module(module_name: str) -> bool:
        """Reload a single module by its dotted name.

        Args:
            module_name: Dotted module name (e.g., `"app.main"`).

        Returns:
            `True` if the module imported successfully from the current
            `sys.path`; `False` otherwise.
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
        """Reload the modules that are already imported.

        Args:
            module_names: Dotted module names to reload.

        Returns:
            Names that were successfully reloaded.
        """
        importlib.invalidate_caches()
        reloaded: List[str] = []
        seen: set[str] = set()
        for module_name in module_names:
            if not module_name or module_name in seen:
                continue
            seen.add(module_name)
            if ModuleReloader.reload_module(module_name):
                reloaded.append(module_name)
        return reloaded

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
    def reload_screen(screen_instance: Any, module_names: Optional[Sequence[str]] = None) -> None:
        """Force a screen re-render after a module reload.

        Args:
            screen_instance: A `_ScreenHost` instance (or duck-typed
                equivalent) that exposes a `_reconciler` attribute.
            module_names: Optional modules that changed. Reload-aware
                screen hosts use this to refresh imports before re-render.
        """
        reload_fn = getattr(screen_instance, "reload", None)
        if callable(reload_fn):
            reload_fn(list(module_names or []))
            return

        from .screen import _request_render

        if hasattr(screen_instance, "_reconciler") and screen_instance._reconciler is not None:
            _request_render(screen_instance)

    @staticmethod
    def find_replacement_function(old_fn: Any) -> Optional[Any]:
        """Locate a function's post-reload counterpart by qualname.

        Functions decorated with [`component`][pythonnative.component]
        store the user's original function on the wrapper's
        ``__wrapped__`` attribute and forward ``__module__`` /
        ``__qualname__`` so that the reconciler's stored
        ``element.type`` (the unwrapped function) still has the
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

        if getattr(obj, "_pn_component", False):
            obj = getattr(obj, "__wrapped__", obj)

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
            reconciler: The reconciler whose
                ``_tree`` should be inspected.
            reloaded_modules: Set of module names that were just
                reloaded (only callables from these modules are
                considered).

        Returns:
            A mapping suitable for passing to
            [`swap_components_in_tree`][pythonnative.hot_reload.ModuleReloader.swap_components_in_tree].
        """
        modules: Set[str] = {m for m in reloaded_modules if m}
        if not modules or reconciler is None or getattr(reconciler, "_tree", None) is None:
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

        visit(reconciler._tree)
        return mapping

    @staticmethod
    def swap_components_in_tree(reconciler: Any, replacement_map: Dict[Any, Any]) -> int:
        """Apply a ``{old: new}`` map to every node in the reconciler tree.

        Mutates ``vnode.element.type`` directly so the NEXT diff sees
        identical types and reuses VNodes (preserving hook state).
        Pending ``Element`` trees stored on ``vnode._rendered`` are
        rewritten too because the reconciler reads from them when
        comparing keys across renders.

        Returns:
            The number of element type references that were rewritten.
        """
        if not replacement_map or reconciler is None or getattr(reconciler, "_tree", None) is None:
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
            rendered = getattr(vnode, "_rendered", None)
            if rendered is not None:
                rewrite_element_tree(rendered)
            for child in getattr(vnode, "children", []) or []:
                visit(child)

        visit(reconciler._tree)
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
        return rewrites > 0

    @staticmethod
    def reload_from_manifest(
        screen_instance: Any,
        manifest_path: str,
        *,
        last_version: Optional[str] = None,
    ) -> Optional[str]:
        """Apply a reload manifest if it is newer than `last_version`.

        Args:
            screen_instance: Screen host to refresh.
            manifest_path: JSON manifest written by the CLI.
            last_version: Version already applied by this screen host.

        Returns:
            The manifest version after applying, or `last_version` when
            no new manifest is available.
        """
        if not os.path.exists(manifest_path):
            return last_version

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        version = str(manifest.get("version", ""))
        if not version or version == last_version:
            return last_version

        modules = manifest.get("modules")
        if not isinstance(modules, list):
            files = manifest.get("files", [])
            modules = ModuleReloader.modules_from_files(files if isinstance(files, list) else [])

        ModuleReloader.reload_screen(screen_instance, [str(module) for module in modules])
        return version
