"""Ahead-of-time bytecode for the embedded interpreter."""

from __future__ import annotations

import importlib.util
import marshal
import sys
from pathlib import Path

from pythonnative.project import bytecode


def _tree(root: Path) -> Path:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("VALUE = 41\n", encoding="utf-8")
    (root / "pkg" / "mod.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    return root


def _code_filename(pyc: Path) -> str:
    return marshal.loads(pyc.read_bytes()[16:]).co_filename


def test_debug_bytecode_keeps_sources_and_names_bundle_paths(tmp_path: Path) -> None:
    root = _tree(tmp_path / "app")

    assert bytecode.compile_tree(root, sys.executable, sourceless=False, label="app")

    assert (root / "pkg" / "mod.py").is_file()
    (compiled,) = (root / "pkg" / "__pycache__").glob("mod.*.pyc")
    assert int.from_bytes(compiled.read_bytes()[4:8], "little") == 0b01
    assert _code_filename(compiled) == "app/pkg/mod.py"


def test_release_bytecode_is_sourceless_and_importable(tmp_path: Path) -> None:
    root = _tree(tmp_path / "app_packages")

    assert bytecode.compile_tree(root, sys.executable, sourceless=True, label="app_packages")

    assert not list(root.rglob("*.py"))
    assert not list(root.rglob("__pycache__"))
    compiled = root / "pkg" / "mod.pyc"
    assert _code_filename(compiled) == "app_packages/pkg/mod.py"
    spec = importlib.util.spec_from_file_location("pn_sourceless_mod", compiled)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.answer() == 42


def test_a_syntax_error_fails_and_keeps_the_source(tmp_path: Path) -> None:
    root = _tree(tmp_path / "app")
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    assert not bytecode.compile_tree(root, sys.executable, sourceless=True, label="app")

    assert (root / "broken.py").is_file()
    assert (root / "pkg" / "mod.pyc").is_file()


def test_missing_roots_are_fine(tmp_path: Path) -> None:
    assert bytecode.compile_tree(tmp_path / "absent", sys.executable, sourceless=True, label="app")
