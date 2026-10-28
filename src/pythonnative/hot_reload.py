"""Device-side module reloading for Fast Refresh.

The dev server (``pythonnative.devserver``) watches the project's
``app/`` directory and tells every connected dev client which files
changed. This module is the client's other half: it re-executes the
changed modules with ``importlib`` and refreshes the logical application tree.

Two strategies share the surface:

- **Fast Refresh** (default): after reloading the changed modules the
  reconciler tree is walked and every component function whose module
  was reloaded is matched to its replacement. Compatible hook signatures
  preserve state; hook-order or custom-hook changes remount the affected
  component instances. Covered screens and mounted rows participate in the
  same refresh.
- **Full remount**: a reloaded module that removes a class or changes a
  class's definition (its fields, bases, or method bodies), or an
  unsuccessful component swap, rebuilds the application tree. State is
  reset. Functions, `TypedDict` and `Protocol` classes, and classes whose
  definition didn't change never force a remount. A module import failure
  is reported while its previous definition remains available.

[`apply_reload`][pythonnative.hot_reload.apply_reload] is the single
entry point: it reloads once per process and then refreshes each live
application host.

On device, sources arrive in a writable **overlay** directory that
shadows the app bundle (see
[`configure_dev_environment`][pythonnative.hot_reload.configure_dev_environment]);
under ``pn preview`` the project directory itself is on ``sys.path``
and there is no overlay.
"""

from __future__ import annotations

import enum
import functools
import hashlib
import importlib
import importlib.util
import inspect
import os
import sys
import threading
import types
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .utils import OVERLAY_ENV, overlay_root

__all__ = [
    "DEV_ROOT_DIR",
    "ModuleReloader",
    "ReloadResult",
    "apply_reload",
    "configure_dev_environment",
]

DEV_ROOT_DIR = "pythonnative_dev"
"""Name of the writable on-device directory that shadows bundled app code."""

PACKAGES_DIR = "site-packages"
"""Overlay subdirectory holding pure-Python packages synced from the dev server."""


def configure_dev_environment(writable_root: str) -> str:
    """Create and prioritize the writable source overlay.

    The returned directory is inserted at the front of `sys.path`, so a
    synced `app/main.py` shadows the copy bundled into the native
    application, and its `site-packages/` (packages the dev server syncs)
    is appended to the end, so bundled packages win. Debug templates call
    this before importing user code. It also routes connect links
    (``pn-<app id>://connect?url=...``) to the dev client, which the
    launcher (``pn run``, ``pn go``, or a scanned QR code) uses to point
    the app at a dev server.

    Args:
        writable_root: Platform data directory that the app can write to
            (Android `filesDir`, iOS `Documents`, or a test directory).

    Returns:
        Absolute path to the overlay root.
    """
    dev_root = os.path.abspath(os.path.join(writable_root, DEV_ROOT_DIR))
    os.makedirs(os.path.join(dev_root, "app"), exist_ok=True)
    if dev_root in sys.path:
        sys.path.remove(dev_root)
    sys.path.insert(0, dev_root)
    packages = os.path.join(dev_root, PACKAGES_DIR)
    os.makedirs(packages, exist_ok=True)
    if packages not in sys.path:
        sys.path.append(packages)
    os.environ[OVERLAY_ENV] = dev_root
    from . import devclient
    from .native_modules.linking import set_interceptor

    set_interceptor(devclient.handle_link)
    return dev_root


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

        Replaces immutable element descriptions so the next diff sees
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

        def rewrite_element_tree(element: Any) -> Any:
            nonlocal rewrites
            from .element import Element

            if not isinstance(element, Element):
                return element
            new_type = replacement_map.get(element.type, element.type)
            children = tuple(rewrite_element_tree(child) for child in element.children)
            if new_type is not element.type:
                rewrites += 1
            if new_type is not element.type or any(a is not b for a, b in zip(children, element.children)):
                return Element(new_type, element.props, children, element.key)
            return element

        def visit(vnode: Any) -> None:
            if vnode is None:
                return
            vnode.element = rewrite_element_tree(vnode.element)
            if vnode.rendered is not None:
                vnode.rendered = [rewrite_element_tree(el) for el in vnode.rendered]
            for child in vnode.children:
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
        compatible = {
            old: new
            for old, new in replacement_map.items()
            if getattr(old, "refresh_signature", None) is not None
            and old.refresh_signature == getattr(new, "refresh_signature", None)
        }
        ModuleReloader.swap_components_in_tree(reconciler, compatible)
        # Incompatible types remain old in the mounted tree. The next ordinary
        # diff remounts those instances when their parent renders the new type.
        return True


# ======================================================================
# Class fingerprints
# ======================================================================

# Class-dict entries that change without the class's shape changing: line
# numbers, docstrings, caches, and bookkeeping that Python or `dataclasses`
# derives from entries fingerprinted elsewhere.
_CLASS_DICT_NOISE = frozenset(
    {
        "__module__",
        "__qualname__",
        "__doc__",
        "__dict__",
        "__weakref__",
        "__firstlineno__",
        "__static_attributes__",
        "__annotations__",
        "__annotate__",
        "__annotate_func__",
        "__annotations_cache__",
        "__orig_bases__",
        "__parameters__",
        "__type_params__",
        "__dataclass_params__",
        "__dataclass_fields__",
        "__abstractmethods__",
        "_abc_impl",
    }
)

_PRIMITIVES = (type(None), bool, int, float, complex, str, bytes, type(Ellipsis))

_MAX_VALUE_DEPTH = 4


def _qualified_name(obj: Any) -> str:
    module = getattr(obj, "__module__", None) or ""
    qualname = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", None) or type(obj).__qualname__
    return f"{module}.{qualname}"


def _code_digest(code: types.CodeType, doc: Optional[str] = None) -> Any:
    """A structural digest of ``code`` that ignores line numbers and file names.

    ``doc`` is the owning function's docstring; its text is left out so
    editing it keeps the digest.
    """
    consts = tuple(
        ("doc",) if index == 0 and doc is not None and const == doc else _const_digest(const)
        for index, const in enumerate(code.co_consts)
    )
    return (
        "code",
        code.co_qualname,
        code.co_code,
        consts,
        code.co_names,
        code.co_varnames,
        code.co_freevars,
        code.co_cellvars,
        code.co_argcount,
        code.co_posonlyargcount,
        code.co_kwonlyargcount,
        code.co_flags,
    )


def _const_digest(const: Any) -> Any:
    if isinstance(const, types.CodeType):
        return _code_digest(const)
    if isinstance(const, tuple):
        return ("tuple", tuple(_const_digest(item) for item in const))
    if isinstance(const, frozenset):
        return ("frozenset", tuple(sorted(repr(_const_digest(item)) for item in const)))
    if isinstance(const, _PRIMITIVES):
        return (type(const).__name__, repr(const))
    return ("object", _qualified_name(type(const)))


def _function_digest(function: types.FunctionType) -> Any:
    layers = []
    current: Any = function
    seen: Set[int] = set()
    # Decorators that use `functools.wraps` hide the body behind a wrapper whose
    # code never changes, so the wrapped chain is digested too.
    while isinstance(current, types.FunctionType) and id(current) not in seen:
        seen.add(id(current))
        layers.append(
            (
                _code_digest(current.__code__, current.__doc__),
                _value_digest(current.__defaults__, 1),
                _value_digest(current.__kwdefaults__, 1),
            )
        )
        current = getattr(current, "__wrapped__", None)
    return ("function", tuple(layers))


def _value_digest(value: Any, depth: int = 0) -> Any:
    """A stable digest of a class attribute, a default, or a nested container."""
    if isinstance(value, types.FunctionType):
        return _function_digest(value)
    if isinstance(value, (staticmethod, classmethod)):
        return (type(value).__name__, _value_digest(value.__func__, depth))
    if isinstance(value, property):
        return (
            "property",
            _value_digest(value.fget, depth),
            _value_digest(value.fset, depth),
            _value_digest(value.fdel, depth),
        )
    if isinstance(value, functools.cached_property):
        return ("cached_property", _value_digest(value.func, depth))
    if isinstance(value, _PRIMITIVES):
        return (type(value).__name__, repr(value))
    if isinstance(value, type):
        return ("class", _qualified_name(value))
    if isinstance(value, enum.Enum):
        return ("member", _qualified_name(type(value)), value.name, _value_digest(value.value, depth + 1))
    if depth < _MAX_VALUE_DEPTH:
        if isinstance(value, tuple):
            return ("tuple", tuple(_value_digest(item, depth + 1) for item in value))
        if isinstance(value, frozenset):
            return ("frozenset", tuple(sorted(repr(_value_digest(item, depth + 1)) for item in value)))
    # Mutable containers (a class-level cache filled at run time would
    # otherwise differ from its fresh copy) and arbitrary objects
    # (descriptors, builtins, framework values, whose identity differs on
    # every execution) contribute their type only.
    return ("object", _qualified_name(type(value)))


def _annotation_names(cls: type) -> List[str]:
    try:
        import annotationlib  # type: ignore[import-not-found, unused-ignore]

        return sorted(annotationlib.get_annotations(cls, format=annotationlib.Format.FORWARDREF))
    except ImportError:
        pass
    except Exception:
        return []
    try:
        return sorted(inspect.get_annotations(cls))
    except Exception:
        return []


def _class_fingerprint(cls: type) -> str:
    """Hash the parts of ``cls`` that its instances depend on.

    The fingerprint covers the qualified name, the metaclass and bases, the
    annotated field names, and every class attribute: functions, methods, and
    properties by their bytecode, constants, names, and defaults, and
    immutable data by value. Line numbers, file names, and docstrings are
    left out, so moving a class or adding a comment above it keeps its
    fingerprint.
    """
    attributes = tuple(
        (name, _value_digest(value)) for name, value in sorted(vars(cls).items()) if name not in _CLASS_DICT_NOISE
    )
    # Dataclass defaults and factories reach `__init__` through its globals
    # rather than its code, so the fields are digested directly.
    fields = tuple(
        (
            name,
            _value_digest(getattr(spec, "default", None)),
            _value_digest(getattr(spec, "default_factory", None)),
            repr(getattr(spec, "_field_type", None)),
            tuple(bool(getattr(spec, flag, False)) for flag in ("init", "repr", "compare", "kw_only")),
        )
        for name, spec in sorted((vars(cls).get("__dataclass_fields__") or {}).items())
    )
    parts = (
        cls.__qualname__,
        _qualified_name(type(cls)),
        tuple(_qualified_name(base) for base in cls.__bases__),
        tuple(_annotation_names(cls)),
        attributes,
        fields,
    )
    return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()


def _is_exempt_class(cls: type) -> bool:
    # TypedDicts and Protocols only describe shapes: nothing holds an instance
    # of the class object itself, so redefining one never strands state.
    return typing.is_typeddict(cls) or bool(getattr(cls, "_is_protocol", False))


def _module_classes(module_name: str) -> Dict[str, type]:
    """Classes defined by ``module_name`` (nested ones included), by qualname."""
    module = sys.modules.get(module_name)
    if module is None:
        return {}
    classes: Dict[str, type] = {}

    def collect(candidates: Iterable[Any]) -> None:
        for value in candidates:
            if not isinstance(value, type) or value.__module__ != module_name:
                continue
            qualname = value.__qualname__
            if "<locals>" in qualname or qualname in classes:
                continue
            classes[qualname] = value
            collect(vars(value).values())

    collect(list(vars(module).values()))
    return classes


def _class_fingerprints(module_names: Iterable[str]) -> Dict[str, Dict[str, str]]:
    """Fingerprint every class the named modules define.

    Args:
        module_names: Dotted names of imported modules.

    Returns:
        ``{module_name: {qualname: fingerprint}}``. `TypedDict` and `Protocol`
        classes are omitted because redefining them never strands state.
    """
    result: Dict[str, Dict[str, str]] = {}
    for module_name in module_names:
        result[module_name] = {
            qualname: _class_fingerprint(cls)
            for qualname, cls in _module_classes(module_name).items()
            if not _is_exempt_class(cls)
        }
    return result


def _classes_changed(before: Dict[str, Dict[str, str]], after: Dict[str, Dict[str, str]]) -> List[str]:
    """Qualified names of classes that were removed or redefined differently.

    New classes are not listed: no live instance can reference them yet.
    """
    changed: List[str] = []
    for module_name, old_classes in before.items():
        new_classes = after.get(module_name)
        if new_classes is None:
            continue
        for qualname, fingerprint in old_classes.items():
            if new_classes.get(qualname) != fingerprint:
                changed.append(f"{module_name}.{qualname}")
    return changed


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
            RedBox), or ``"none"`` when nothing could be reloaded or no
            host had a mounted tree to refresh.
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
    # Instances of application classes can live in state, memo, or ref slots.
    # A class whose definition changed (or disappeared) would leave them
    # stranded, so those reloads remount. Functions are rebound by the module
    # re-execution and picked up on the next render.
    fingerprints = _class_fingerprints(t for t in targets if t in sys.modules)

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
    before = {name: fingerprints[name] for name in reloaded if name in fingerprints}
    changed_classes = _classes_changed(before, _class_fingerprints(before))
    remount = bool(changed_classes)
    if remount:
        diagnostics.log(f"reload: class definitions changed ({', '.join(changed_classes)}); remounting")

    modes: List[str] = []
    for host in hosts:
        try:
            modes.append(host.refresh(reloaded, force_remount=True) if remount else host.refresh(reloaded))
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
        # No host had a mounted tree to refresh.
        result.mode = "none"
    return result
