"""Tests for hot-reload source overlays and manifest handling."""

import importlib
import json
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
    configure_dev_environment,
    manifest_path_for,
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


def test_reload_from_manifest_calls_reload_once(tmp_path: Path) -> None:
    writable_root = os.fspath(tmp_path)
    dev_root = configure_dev_environment(writable_root)
    manifest_path = manifest_path_for(dev_root)
    calls: list[list[str]] = []

    class Page:
        def reload(self, module_names: list[str]) -> None:
            calls.append(module_names)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "1",
                "files": ["app/main.py"],
                "modules": ["app.main"],
            },
            f,
        )

    version = ModuleReloader.reload_from_manifest(Page(), manifest_path)
    assert version == "1"
    assert calls == [["app.main"]]

    version = ModuleReloader.reload_from_manifest(Page(), manifest_path, last_version=version)
    assert version == "1"
    assert calls == [["app.main"]]


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
# reload_modules_for_version (cross-host dedup)
# ======================================================================


@pytest.fixture
def _reset_reloaded_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate `ModuleReloader._last_reloaded_version` per test."""
    monkeypatch.setattr(ModuleReloader, "_last_reloaded_version", None, raising=False)


def _make_reloadable_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> str:
    """Create a package with one module that can be reloaded; returns the dotted name."""
    pkg = tmp_path / "dedup_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "comp.py").write_text(f"VALUE = {value!r}\n", encoding="utf-8")
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    sys.modules.pop("dedup_pkg.comp", None)
    sys.modules.pop("dedup_pkg", None)
    importlib.import_module("dedup_pkg.comp")
    return "dedup_pkg.comp"


def test_reload_modules_for_version_reloads_first_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reset_reloaded_version: None,
) -> None:
    module_name = _make_reloadable_pkg(tmp_path, monkeypatch, "v1")
    first_module = sys.modules[module_name]

    # Edit the file and reload through the version-aware API.
    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v2'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")

    reloaded = ModuleReloader.reload_modules_for_version([module_name], version="1")

    assert reloaded == [module_name]
    assert sys.modules[module_name] is not first_module
    assert sys.modules[module_name].VALUE == "v2"
    assert ModuleReloader._last_reloaded_version == "1"


def test_reload_modules_for_version_skips_second_call_for_same_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reset_reloaded_version: None,
) -> None:
    """A second host on the same version must reuse already-loaded modules."""
    module_name = _make_reloadable_pkg(tmp_path, monkeypatch, "v1")

    # First host reloads against the new source.
    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v2'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")
    ModuleReloader.reload_modules_for_version([module_name], version="1")
    after_first = sys.modules[module_name]
    assert after_first.VALUE == "v2"

    # Simulate another host calling for the same version. The source on disk has
    # advanced (would be a v3 if reloaded), but the dedup must keep the v2 object.
    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v3'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")
    reloaded = ModuleReloader.reload_modules_for_version([module_name], version="1")

    assert reloaded == [module_name]
    assert sys.modules[module_name] is after_first
    assert sys.modules[module_name].VALUE == "v2"


def test_reload_modules_for_version_reloads_again_when_version_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reset_reloaded_version: None,
) -> None:
    """A bumped manifest version must trigger a fresh reload."""
    module_name = _make_reloadable_pkg(tmp_path, monkeypatch, "v1")

    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v2'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")
    ModuleReloader.reload_modules_for_version([module_name], version="1")

    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v3'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")
    ModuleReloader.reload_modules_for_version([module_name], version="2")

    assert sys.modules[module_name].VALUE == "v3"
    assert ModuleReloader._last_reloaded_version == "2"


def test_reload_modules_for_version_without_version_always_reloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _reset_reloaded_version: None,
) -> None:
    """``version=None`` falls back to unconditional ``reload_modules``."""
    module_name = _make_reloadable_pkg(tmp_path, monkeypatch, "v1")

    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v2'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")
    ModuleReloader.reload_modules_for_version([module_name], version=None)
    assert sys.modules[module_name].VALUE == "v2"
    assert ModuleReloader._last_reloaded_version is None

    (tmp_path / "dedup_pkg" / "comp.py").write_text("VALUE = 'v3'\n", encoding="utf-8")
    os.utime(tmp_path / "dedup_pkg" / "comp.py")
    ModuleReloader.reload_modules_for_version([module_name], version=None)
    assert sys.modules[module_name].VALUE == "v3"


def test_reload_from_manifest_stashes_version_on_screen_instance(
    tmp_path: Path,
    _reset_reloaded_version: None,
) -> None:
    """``reload_from_manifest`` must surface the version to ``host.reload`` via
    ``_hot_reload_pending_version`` so the host can dedupe ``reload_modules``."""
    writable_root = os.fspath(tmp_path)
    dev_root = configure_dev_environment(writable_root)
    manifest_path = manifest_path_for(dev_root)
    observed: list[str | None] = []

    class _Host:
        def reload(self, module_names: list[str]) -> None:
            observed.append(getattr(self, "_hot_reload_pending_version", None))

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"version": "abc-123", "modules": ["app.main"]}, f)

    host = _Host()
    ModuleReloader.reload_from_manifest(host, manifest_path)

    assert observed == ["abc-123"]
    # The attribute is restored to its previous value (``None``) after the call.
    assert getattr(host, "_hot_reload_pending_version", "missing") is None


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
