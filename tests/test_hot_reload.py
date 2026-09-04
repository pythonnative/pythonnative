"""Tests for the device-side half of Fast Refresh: overlays, module reloading, apply_reload."""

import importlib
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.hot_reload import (
    DEV_ROOT_DIR,
    ModuleReloader,
    apply_reload,
    configure_dev_environment,
)
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend as _MockBackend


def _write_module(path: Path, value: str) -> None:
    path.write_text(f"VALUE = {value!r}\n", encoding="utf-8")


def test_configure_dev_environment_prioritizes_overlay(tmp_path: Path) -> None:
    writable_root = os.fspath(tmp_path)
    dev_root = configure_dev_environment(writable_root)

    assert dev_root == os.path.join(writable_root, DEV_ROOT_DIR)
    assert os.path.isdir(os.path.join(dev_root, "app"))
    assert sys.path[0] == dev_root


def test_file_to_module_normalizes_relative_paths() -> None:
    assert ModuleReloader.file_to_module("app/main.py") == "app.main"
    assert ModuleReloader.file_to_module("app\\pages\\home.py") == "app.pages.home"
    assert ModuleReloader.file_to_module("app/__init__.py") == "app"


def test_reload_module_imports_from_prioritized_sys_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundled = tmp_path / "bundled"
    overlay = tmp_path / "overlay"
    bundled_pkg = bundled / "reload_pkg"
    overlay_pkg = overlay / "reload_pkg"
    bundled_pkg.mkdir(parents=True)
    overlay_pkg.mkdir(parents=True)
    (bundled_pkg / "__init__.py").write_text("", encoding="utf-8")
    (overlay_pkg / "__init__.py").write_text("", encoding="utf-8")
    _write_module(bundled_pkg / "screen.py", "bundled")
    _write_module(overlay_pkg / "screen.py", "overlay")

    monkeypatch.syspath_prepend(os.fspath(bundled))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    sys.modules.pop("reload_pkg.screen", None)
    sys.modules.pop("reload_pkg", None)

    screen = importlib.import_module("reload_pkg.screen")

    assert screen.VALUE == "bundled"

    monkeypatch.syspath_prepend(os.fspath(overlay))
    monkeypatch.setenv("PYTHONNATIVE_HOT_RELOAD_ROOT", os.fspath(overlay))
    assert ModuleReloader.reload_module("reload_pkg.screen") is True

    reloaded = importlib.import_module("reload_pkg.screen")

    assert reloaded.VALUE == "overlay"


# ======================================================================
# expand_reload_targets
# ======================================================================


def _register_modules(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    """Register stub modules in ``sys.modules`` for the lifetime of a test."""
    import types

    for name in names:
        if name in sys.modules:
            continue
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))


def test_expand_reload_targets_appends_entry_point_after_changed_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_modules(monkeypatch, "app", "app.main", "app.screens", "app.screens.home")

    targets = ModuleReloader.expand_reload_targets(["app.screens.home"], "app.main")

    assert targets[0] == "app.screens.home"
    assert targets[-1] == "app.main"


def test_expand_reload_targets_orders_other_app_modules_deepest_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_modules(
        monkeypatch,
        "app",
        "app.main",
        "app.theme",
        "app.screens",
        "app.screens.home",
        "app.screens.forms",
    )

    targets = ModuleReloader.expand_reload_targets(["app.screens.home"], "app.main")

    assert targets[0] == "app.screens.home"
    assert targets[-1] == "app.main"
    forms_idx = targets.index("app.screens.forms")
    theme_idx = targets.index("app.theme")
    pkg_idx = targets.index("app")
    assert forms_idx < theme_idx < pkg_idx


def test_expand_reload_targets_moves_entry_point_to_end_when_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_modules(monkeypatch, "app", "app.main", "app.screens", "app.screens.home")

    targets = ModuleReloader.expand_reload_targets(["app.main"], "app.main")

    assert targets[-1] == "app.main"
    assert targets.count("app.main") == 1


def test_expand_reload_targets_supports_dotted_attribute_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_modules(monkeypatch, "app", "app.main", "app.screens", "app.screens.home")

    targets = ModuleReloader.expand_reload_targets(["app.screens.home"], "app.main.RootScreen")

    assert targets[-1] == "app.main"


def test_expand_reload_targets_excludes_modules_outside_app_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_modules(
        monkeypatch,
        "app",
        "app.main",
        "app.screens.home",
        "pythonnative",
        "pythonnative.navigation",
    )

    targets = ModuleReloader.expand_reload_targets(["app.screens.home"], "app.main")

    assert "pythonnative" not in targets
    assert "pythonnative.navigation" not in targets


def test_expand_reload_targets_returns_only_changed_when_entry_point_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No entry module in sys.modules; should fall back to just the changed list.
    monkeypatch.delitem(sys.modules, "app.main", raising=False)
    monkeypatch.delitem(sys.modules, "app", raising=False)

    targets = ModuleReloader.expand_reload_targets(["totally_unrelated.module"], "app.main")

    assert targets == ["totally_unrelated.module"]


# ======================================================================
# Fast Refresh: find_replacement_function / refresh_in_place
# ======================================================================


def test_find_replacement_function_returns_new_function_for_reloaded_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = tmp_path / "refresh_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "comp.py").write_text(
        "from pythonnative.element import Element\n\ndef Screen():\n    return Element('Text', {'text': 'v1'}, [])\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    sys.modules.pop("refresh_pkg.comp", None)
    sys.modules.pop("refresh_pkg", None)

    module = importlib.import_module("refresh_pkg.comp")
    old_fn = module.Screen

    # Rewrite and reload.
    (pkg / "comp.py").write_text(
        "from pythonnative.element import Element\n\ndef Screen():\n    return Element('Text', {'text': 'v2'}, [])\n",
        encoding="utf-8",
    )
    assert ModuleReloader.reload_module("refresh_pkg.comp") is True
    new_fn = sys.modules["refresh_pkg.comp"].Screen

    assert new_fn is not old_fn
    resolved = ModuleReloader.find_replacement_function(old_fn)
    assert resolved is new_fn


def test_find_replacement_function_skips_when_module_not_reloaded() -> None:
    """An unchanged function returns ``None`` (caller knows not to swap)."""

    def Untouched() -> None:
        return None

    Untouched.__module__ = __name__
    assert ModuleReloader.find_replacement_function(Untouched) is None


def test_refresh_in_place_swaps_components_and_preserves_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: reload module, walk tree, and the next render uses new bodies."""
    pkg = tmp_path / "rstate_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "comp.py").write_text(
        "import pythonnative as pn\n"
        "from pythonnative.element import Element\n"
        "from pythonnative.component import component\nfrom pythonnative.hooks import use_state\n\n"
        "@component\n"
        "def Counter():\n"
        "    count, set_count = use_state(0)\n"
        "    set_counter._set_count = set_count\n"
        "    return Element('Text', {'text': f'A:{count}'}, [])\n\n"
        "class _Holder:\n"
        "    _set_count = None\n"
        "set_counter = _Holder\n",
        encoding="utf-8",
    )
    # Disable bytecode caching: without this, two writes inside the same
    # second can leave Python serving the stale .pyc (mtime resolution).
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    sys.modules.pop("rstate_pkg.comp", None)
    sys.modules.pop("rstate_pkg", None)

    module = importlib.import_module("rstate_pkg.comp")

    backend = _MockBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None

    root = rec.mount(module.Counter())

    def get_text(view: Any) -> Any:
        if view.type_name == "Text":
            return view.props.get("text")
        for c in view.children:
            r = get_text(c)
            if r is not None:
                return r
        return None

    assert get_text(root) == "A:0"

    # Bump the counter so the hook state is non-default.
    module.set_counter._set_count(5)
    rec.reconcile(module.Counter())
    assert get_text(rec.root.native_view) == "A:5"

    # Edit the module (change the prefix from "A:" to "B:").
    (pkg / "comp.py").write_text(
        "import pythonnative as pn\n"
        "from pythonnative.element import Element\n"
        "from pythonnative.component import component\nfrom pythonnative.hooks import use_state\n\n"
        "@component\n"
        "def Counter():\n"
        "    count, set_count = use_state(0)\n"
        "    set_counter._set_count = set_count\n"
        "    return Element('Text', {'text': f'B:{count}'}, [])\n\n"
        "class _Holder:\n"
        "    _set_count = None\n"
        "set_counter = _Holder\n",
        encoding="utf-8",
    )
    # Force the mtime to advance so the import system rereads from disk
    # even on filesystems with second-resolution mtimes.
    import time as _time

    _time.sleep(0.01)
    os.utime(pkg / "comp.py")
    assert ModuleReloader.reload_module("rstate_pkg.comp") is True

    refreshed = ModuleReloader.refresh_in_place(rec, ["rstate_pkg.comp"])
    assert refreshed is True

    # Render with the reloaded module's Counter; the new function is
    # called against the same VNode (and HookState), so state survives.
    new_module = sys.modules["rstate_pkg.comp"]
    rec.reconcile(new_module.Counter())
    assert get_text(rec.root.native_view) == "B:5"


def test_refresh_in_place_returns_false_for_unreloaded_modules() -> None:
    """No-op when none of the tree's components belong to a reloaded module."""

    backend = _MockBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    rec.mount(Element("Text", {"text": "static"}, []))

    refreshed = ModuleReloader.refresh_in_place(rec, ["some.other.module"])
    assert refreshed is False


def test_build_replacement_map_skips_nested_functions() -> None:
    """Functions defined inside other functions cannot be re-resolved.

    ``inner``'s ``__qualname__`` contains ``<locals>``, which is not a
    module-level attribute path. The replacement-map builder should
    notice and skip rather than crash trying to ``getattr`` through
    ``<locals>``.
    """

    def make_nested() -> Any:
        def inner() -> Element:
            return Element("Text", {"text": "nested"}, [])

        return inner

    inner = make_nested()
    backend = _MockBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    rec.mount(component(inner)())

    mapping = ModuleReloader.build_replacement_map(rec, [inner.__module__])
    assert mapping == {}


# ======================================================================
# apply_reload: the dev client's single entry point
# ======================================================================


def _write_screen(path: Path, text: str) -> None:
    path.write_text(
        "from pythonnative.component import component\n"
        "from pythonnative.element import Element\n\n"
        "@component\n"
        "def App():\n"
        f"    return Element('Text', {{'text': {text!r}}}, [])\n",
        encoding="utf-8",
    )


def _texts(view: Any) -> list:
    return [v.text for v in view.walk() if v.text is not None] if view is not None else []


@pytest.fixture
def _screen_backend(monkeypatch: pytest.MonkeyPatch) -> Any:
    from pythonnative.native_views import set_registry

    backend = _MockBackend()
    set_registry(backend)
    yield backend
    set_registry(None)


def _mount_screen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pkg: str, text: str) -> Any:
    from pythonnative.hosts import create_screen

    package_dir = tmp_path / pkg
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    _write_screen(package_dir / "main.py", text)
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    for name in (f"{pkg}.main", pkg):
        sys.modules.pop(name, None)
    host = create_screen(f"{pkg}.main")
    host.on_create()
    assert _texts(host.root_native_view) == [text]
    return host


def _rewrite(path: Path, text: str) -> None:
    import time as _time

    _time.sleep(0.01)
    _write_screen(path, text)
    os.utime(path)


def test_apply_reload_reloads_once_and_refreshes_every_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _screen_backend: Any
) -> None:
    host = _mount_screen(tmp_path, monkeypatch, "ar_pkg", "before")
    _rewrite(tmp_path / "ar_pkg" / "main.py", "after")

    result = apply_reload(["ar_pkg.main"], [host])

    assert result.mode in ("fast_refresh", "remount")
    # The package's other modules re-execute too; the entry module goes last.
    assert result.reloaded[-1] == "ar_pkg.main"
    assert set(result.reloaded) == {"ar_pkg", "ar_pkg.main"}
    assert result.hosts == 1
    assert result.error is None
    assert _texts(host.root_native_view) == ["after"]
    host.on_destroy()


def test_apply_reload_skips_modules_that_were_never_imported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _screen_backend: Any
) -> None:
    """A changed file nobody imported needs no re-execution."""
    host = _mount_screen(tmp_path, monkeypatch, "ar_unused", "hello")
    (tmp_path / "ar_unused" / "extra.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = apply_reload(["ar_unused.extra"], [host])

    # Only the entry module (re-imported so it can pick the new file up) runs.
    assert "ar_unused.extra" not in result.reloaded
    assert result.mode in ("fast_refresh", "remount", "none")
    host.on_destroy()


def test_apply_reload_reports_import_errors_without_replacing_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _screen_backend: Any
) -> None:
    from pythonnative import diagnostics

    host = _mount_screen(tmp_path, monkeypatch, "ar_broken", "ok")
    good_module = sys.modules["ar_broken.main"]
    broken = tmp_path / "ar_broken" / "main.py"
    import time as _time

    _time.sleep(0.01)
    broken.write_text("def App(:\n    pass\n", encoding="utf-8")
    os.utime(broken)

    was_dev = diagnostics.is_dev()
    diagnostics.set_dev_mode(True)
    try:
        result = apply_reload(["ar_broken.main"], [host])
    finally:
        diagnostics.set_dev_mode(was_dev)

    assert result.mode == "error"
    assert result.error is not None and "SyntaxError" in result.error
    assert result.reloaded == []
    # The previous module object stays importable for the next attempt.
    assert sys.modules["ar_broken.main"] is good_module
    host.on_destroy()


def test_apply_reload_with_no_hosts_is_a_noop() -> None:
    result = apply_reload(["anything.at.all"], [])
    assert result.mode == "none"
    assert result.reloaded == []
    assert result.requested == ["anything.at.all"]
