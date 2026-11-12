"""Deterministic budgets for startup and rendering (RFC 0005).

Wall-clock thresholds vary with hardware, so these tests check the work
that made PythonNative slow instead: deriving contracts or parsing source
at import, importing subsystems an app may never use, journaling a render
field by field, binding calls through ``inspect.Signature``, and
validating every commit twice in release builds. Timings are recorded by
``scripts/benchmark-runtime.py``.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from typing import Any, List

import pytest

import pythonnative as pn
from pythonnative import diagnostics, journal
from pythonnative.sdk import schema
from pythonnative.testing import render

# ``import pythonnative`` in a fresh interpreter, reporting what it did.
_PROBE = """
import ast, dataclasses, inspect, json, sys, typing

calls = []
for owner, name in ((inspect, "getsource"), (typing, "get_type_hints"), (ast, "parse")):
    original = getattr(owner, name)
    def spy(*args, _name=name, _original=original, **kwargs):
        calls.append(_name)
        return _original(*args, **kwargs)
    setattr(owner, name, spy)

dataclass_definitions = []
process_class = dataclasses._process_class
def counted(cls, *args, **kwargs):
    dataclass_definitions.append(f"{cls.__module__}.{cls.__qualname__}")
    return process_class(cls, *args, **kwargs)
dataclasses._process_class = counted

import pythonnative

modules = sorted(name for name in sys.modules if name.split(".")[0] == "pythonnative")
print(json.dumps({"calls": calls, "modules": modules, "dataclasses": dataclass_definitions}))
"""

LAZY_SUBSYSTEMS = (
    "pythonnative.animated",
    "pythonnative.components.lists",
    "pythonnative.components.vector",
    "pythonnative.gestures",
    "pythonnative.icons",
    "pythonnative.list_data",
    "pythonnative.native_modules.app_state",
    "pythonnative.native_modules.device",
    "pythonnative.native_modules.file_system",
    "pythonnative.native_modules.images",
    "pythonnative.native_modules.keyboard",
    "pythonnative.navigation",
    "pythonnative.net",
    "pythonnative.sdk.plugin",
    "pythonnative.svg",
)

MODULE_BUDGET = 48
"""Upper bound on ``pythonnative`` modules loaded by ``import pythonnative`` (46 at RFC 0010)."""

DATACLASS_BUDGET = 30
"""Upper bound on dataclass definitions ``import pythonnative`` executes (29 at RFC 0010).

Each costs an ``exec`` of generated methods, about a millisecond on a laptop.
Framework classes that are dataclasses only for convenience are slotted
classes instead; public records with dataclass behavior (``Theme``, the
event records, ``Props``) stay dataclasses.
"""


@pytest.fixture(scope="module")
def probe() -> Any:
    result = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_import_neither_parses_source_nor_evaluates_type_hints(probe: Any) -> None:
    assert probe["calls"] == []


def test_import_loads_the_generated_contracts(probe: Any) -> None:
    assert "pythonnative.sdk.builtins" not in probe["modules"]
    assert "pythonnative.refresh" not in probe["modules"]


def test_import_defers_optional_subsystems(probe: Any) -> None:
    assert not set(LAZY_SUBSYSTEMS) & set(probe["modules"])
    assert len(probe["modules"]) <= MODULE_BUDGET, len(probe["modules"])


def test_import_defines_few_dataclasses(probe: Any) -> None:
    assert len(probe["dataclasses"]) <= DATACLASS_BUDGET, probe["dataclasses"]


def test_lazy_names_resolve_to_the_same_objects() -> None:
    from pythonnative import list_data, navigation, net, sdk, svg
    from pythonnative.components import lists, vector
    from pythonnative.native_modules import app_state
    from pythonnative.sdk import plugin

    assert pn.StackNavigator is navigation.StackNavigator
    assert pn.fetch is net.fetch
    assert pn.FlatList is lists.FlatList and pn.components.SectionList is lists.SectionList
    assert pn.Svg is vector.Svg is pn.components.Svg and pn.svg is svg
    assert pn.ListData is list_data.ListData
    assert pn.AppState is app_state.AppState is pn.native_modules.AppState
    assert sdk.plugin_module is plugin.plugin_module
    assert set(pn.__all__) <= set(dir(pn))
    for module in (pn.components, pn.native_modules, sdk):
        assert set(module.__all__) <= set(dir(module)), module.__name__
        for name in module.__all__:
            getattr(module, name)


def test_native_events_load_the_facade_that_keeps_their_state() -> None:
    script = (
        "import sys, pythonnative as pn\n"
        "from pythonnative.native_modules.registry import emit\n"
        "assert 'pythonnative.native_modules.app_state' not in sys.modules\n"
        "emit('AppState', 'change', 'background')\n"
        "assert pn.AppState.current_state() == 'background', pn.AppState.current_state()\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True)


def test_generated_contracts_match_the_factories() -> None:
    from pathlib import Path

    from pythonnative.sdk.builtins import derive

    document = json.loads(Path(schema.__file__).with_name(schema.BUILTIN_CONTRACTS).read_text(encoding="utf-8"))
    components, modules = dict(schema.COMPONENTS), dict(schema.MODULES)
    try:
        derived = derive()
        assert document["components"].keys() == derived["components"].keys()
        assert document["modules"].keys() == derived["modules"].keys()
        assert document["fingerprint"] == schema.fingerprint()
    finally:
        schema.COMPONENTS.clear()
        schema.COMPONENTS.update(components)
        schema.MODULES.clear()
        schema.MODULES.update(modules)


def test_framework_components_have_no_refresh_signature() -> None:
    assert pn.FlatList.refresh_signature is None
    assert pn.SectionList.refresh_signature is None


@pn.component
def _Cell(label: str, n: int) -> pn.Node:
    value, _set_value = pn.use_state(0)
    pn.use_effect(lambda: None, [n])
    return pn.Row(pn.Text(label), pn.Text(str(n + value)))


@pn.component
def _Grid(n: int) -> pn.Node:
    return pn.Column(*(_Cell(f"cell {i}", n).with_key(str(i)) for i in range(20)))


def test_a_render_pass_captures_each_object_once(monkeypatch: pytest.MonkeyPatch) -> None:
    result = render(_Grid(0), viewport=None)
    captured: List[int] = []
    original = journal.Journal.snapshot

    def snapshot(self: journal.Journal, obj: Any, fields: tuple[str, ...]) -> None:
        captured.append(id(obj))
        original(self, obj, fields)

    monkeypatch.setattr(journal.Journal, "snapshot", snapshot)
    result.rerender(_Grid(1))
    assert captured
    assert len(captured) == len(set(captured))
    # One hook state and at most a handful of nodes per rendered cell.
    assert len(captured) <= 20 * 6 + 4


def test_element_construction_and_render_skip_signature_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Signature.bind on the render path")

    monkeypatch.setattr(inspect.Signature, "bind", forbidden)
    monkeypatch.setattr(inspect, "BoundArguments", forbidden)
    result = render(_Grid(0), viewport=None)
    result.rerender(_Grid(2))
    assert result.get_by_text("cell 3")


def test_release_renders_never_validate_props_in_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """The renderer core validates every commit; release builds skip the Python walk entirely."""
    validated: List[str] = []
    monkeypatch.setattr(schema.ComponentSchema, "validate", lambda self, *a, **k: validated.append(self.name))
    diagnostics.set_dev_mode(False)
    try:
        result = render(_Grid(0))
        result.rerender(_Grid(1))
        result.unmount()
    finally:
        diagnostics.set_dev_mode(True)
    assert validated == []
