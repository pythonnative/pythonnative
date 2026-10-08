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
from pythonnative.bridge.commits import PROTOCOL_VERSION, CommitState
from pythonnative.sdk import schema
from pythonnative.testing import render

# ``import pythonnative`` in a fresh interpreter, reporting what it did.
_PROBE = """
import ast, inspect, json, sys, typing

calls = []
for owner, name in ((inspect, "getsource"), (typing, "get_type_hints"), (ast, "parse")):
    original = getattr(owner, name)
    def spy(*args, _name=name, _original=original, **kwargs):
        calls.append(_name)
        return _original(*args, **kwargs)
    setattr(owner, name, spy)

import pythonnative

modules = sorted(name for name in sys.modules if name.split(".")[0] == "pythonnative")
print(json.dumps({"calls": calls, "modules": modules}))
"""

LAZY_SUBSYSTEMS = (
    "pythonnative.animated",
    "pythonnative.gestures",
    "pythonnative.icons",
    "pythonnative.navigation",
    "pythonnative.net",
)

MODULE_BUDGET = 90
"""Upper bound on ``pythonnative`` modules loaded by ``import pythonnative``."""


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


def test_lazy_names_resolve_to_the_same_objects() -> None:
    from pythonnative import navigation, net

    assert pn.StackNavigator is navigation.StackNavigator
    assert pn.fetch is net.fetch
    assert set(pn.__all__) <= set(dir(pn))


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


def test_release_commits_skip_python_prop_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    validated: List[str] = []
    monkeypatch.setattr(schema.ComponentSchema, "validate", lambda self, *a, **k: validated.append(self.name))
    envelope = {
        "version": PROTOCOL_VERSION,
        "application": "budget",
        "surface": 1,
        "revision": 1,
        "ops": [["c", 1, "Text", {"text": "hi"}]],
    }
    diagnostics.set_dev_mode(False)
    CommitState().prepare(envelope)
    assert validated == []
    diagnostics.set_dev_mode(True)
    CommitState().prepare(envelope)
    assert validated == ["Text"]
