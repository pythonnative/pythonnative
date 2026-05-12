"""Tests for the `pn.run(App)` entry point and component resolution.

The convention is that a user's module declares an ``App`` component
and registers it once via ``pn.run(App)``. Templates then load the
app by passing the *module* path (e.g. ``"app.main_page"``) to
``create_page`` and PythonNative looks up the registered component.

These tests pin down:

- ``pn.run`` stores the component for later lookup.
- ``_import_component`` resolves dotted paths (legacy) AND module-only
  paths (new) without losing the original behaviour.
- ``_import_component`` raises a useful error when nothing resolves.
"""

import os
import sys
from pathlib import Path
from typing import Any

import pytest

import pythonnative as pn
from pythonnative import app_registry
from pythonnative.page import _import_component


@pytest.fixture(autouse=True)
def _reset_app_registry() -> Any:
    """Clear the registered App before and after each test."""
    app_registry.clear()
    yield
    app_registry.clear()


def test_run_registers_app_component() -> None:
    @pn.component
    def MyApp() -> pn.Element:
        return pn.Text("hi")

    pn.run(MyApp)
    assert app_registry.get_registered_app() is MyApp


def test_run_returns_component_so_it_can_be_a_decorator() -> None:
    @pn.component
    def DecApp() -> pn.Element:
        return pn.Text("hi")

    same = pn.run(DecApp)
    assert same is DecApp


def test_run_rejects_non_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        pn.run("not a function")  # type: ignore[arg-type]


def test_import_component_resolves_dotted_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_import_component`` accepts the legacy ``module.attr`` shape."""
    pkg = tmp_path / "demo_dotted"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "main.py").write_text(
        "from pythonnative.element import Element\n\n"
        "def Root():\n"
        "    return Element('Text', {'text': 'dotted'}, [])\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    sys.modules.pop("demo_dotted.main", None)
    sys.modules.pop("demo_dotted", None)

    fn = _import_component("demo_dotted.main.Root")
    el = fn()
    assert el.type == "Text"
    assert el.props["text"] == "dotted"


def test_import_component_resolves_module_via_pn_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_import_component`` finds an App registered via ``pn.run``."""
    pkg = tmp_path / "demo_register"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "entry.py").write_text(
        "import pythonnative as pn\n"
        "from pythonnative.element import Element\n\n"
        "def App():\n"
        "    return Element('Text', {'text': 'registered'}, [])\n\n"
        "pn.run(App)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    sys.modules.pop("demo_register.entry", None)
    sys.modules.pop("demo_register", None)

    fn = _import_component("demo_register.entry")
    el = fn()
    assert el.props["text"] == "registered"


def test_import_component_falls_back_to_App_attribute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the module defines ``App`` but doesn't call ``pn.run``, find it anyway."""
    pkg = tmp_path / "demo_implicit"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "entry.py").write_text(
        "from pythonnative.element import Element\n\n"
        "def App():\n"
        "    return Element('Text', {'text': 'implicit'}, [])\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    sys.modules.pop("demo_implicit.entry", None)
    sys.modules.pop("demo_implicit", None)

    fn = _import_component("demo_implicit.entry")
    el = fn()
    assert el.props["text"] == "implicit"


def test_import_component_raises_when_nothing_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helpful error when neither a dotted attr nor an App is found."""
    pkg = tmp_path / "demo_missing"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "entry.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(os.fspath(tmp_path))
    sys.modules.pop("demo_missing.entry", None)
    sys.modules.pop("demo_missing", None)

    with pytest.raises(ImportError, match="Could not resolve component"):
        _import_component("demo_missing.entry")
