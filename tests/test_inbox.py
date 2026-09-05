"""Exercise the reference application's real data and screen composition."""

import importlib
import sys
import types
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

import pytest

import pythonnative as pn
from pythonnative import runtime
from pythonnative.query import _reset_for_tests
from pythonnative.testing import render


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[types.ModuleType, dict[str, Any]]]:
    package = types.ModuleType("pn_reference_inbox")
    package.__path__ = [str(Path(__file__).parents[1] / "examples/inbox/app")]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    app = importlib.import_module("pn_reference_inbox.main")
    storage: dict[str, Any] = {}

    async def get(key: str) -> Any:
        return storage.get(key)

    async def set_value(key: str, value: Any) -> None:
        storage[key] = value

    monkeypatch.setattr(pn.AsyncStorage, "get", get)
    monkeypatch.setattr(pn.AsyncStorage, "set", set_value)
    _reset_for_tests()
    yield app, storage
    _reset_for_tests()
    for name in list(sys.modules):
        if name.startswith("pn_reference_inbox."):
            sys.modules.pop(name)


def test_search_edit_back_and_persistence(inbox: tuple[types.ModuleType, dict[str, Any]]) -> None:
    app, storage = inbox
    result = render(app.App())
    try:
        assert result.get_by_text("2000 issues")
        result.change_text(result.get_by_label("Search issues"), "2000")
        assert result.get_by_text("1 issues")
        result.press(result.get_by_label("Issue 2000: Check accessibility"))
        assert result.get_by_text("Issue #2000")
        result.change_text(result.get_by_label("Issue title"), "Reviewed issue 2000")
        result.press(result.get_by_text("Close issue"))
        assert result.get_by_text("Reopen")
        result.press(result.get_by_text("Save"))
        assert result.get_by_text("Reviewed issue 2000")
        assert result.get_by_text("Closed")
        assert result.get_by_label("Search issues").props["value"] == "2000"
        assert "Reviewed issue 2000" in storage["inbox.issues"]
    finally:
        result.unmount()
    repository = app.Repository()
    runtime.run_blocking(repository.load())
    assert repository.snapshot.issues[-1].title == "Reviewed issue 2000"
    assert repository.snapshot.issues[-1].closed


def test_failed_persistence_rolls_back_shared_snapshot(
    inbox: tuple[types.ModuleType, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = inbox
    repository = app.Repository()
    runtime.run_blocking(repository.load())
    before = repository.snapshot
    observed = []
    repository.subscribe(lambda: observed.append(repository.snapshot))

    async def fail(key: str, value: Any) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(pn.AsyncStorage, "set", fail)
    with pytest.raises(OSError, match="disk unavailable"):
        runtime.run_blocking(repository.update(replace(before.issues[0], title="Optimistic")))
    assert observed[0].issues[0].title == "Optimistic"
    assert repository.snapshot.issues == before.issues
    assert "disk unavailable" in repository.snapshot.error
