"""``pythonnative.background``: the off-device fallback, the facade, and the plugin manifest."""

from __future__ import annotations

import asyncio
import json
import plistlib
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

import pytest

import pythonnative.background as background
from pythonnative.native_modules.registry import NativeModuleError, emit, native_module, register_python_module
from pythonnative.project.config import AppConfig
from pythonnative.project.plugin_config import resolve_plugin
from pythonnative.project.plugins import load_plugin
from pythonnative.runtime import drain, run_blocking
from pythonnative.sdk import schema

NATIVE = Path(background.__file__).parent / "native"
EVERY = timedelta(minutes=15)


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    register_python_module("Background", background._Fallback)
    declared = dict(background._tasks)
    background._tasks.clear()
    yield
    background._tasks.clear()
    background._tasks.update(declared)
    background._running.clear()
    register_python_module("Background", background._Fallback)


def _impl() -> Any:
    return native_module("Background").impl  # type: ignore[attr-defined]


def test_every_below_the_floor_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 0:15:00"):
        background.task("sync", every=timedelta(minutes=14))
    background.task("sync", every=background.MINIMUM_INTERVAL)(lambda: None)


@pytest.mark.parametrize("name", ["", "has space", "slash/name"])
def test_malformed_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="letters, digits"):
        background.task(name, every=EVERY)


def test_the_decorator_returns_the_function() -> None:
    async def sync() -> None: ...

    assert background.task("sync", every=EVERY)(sync) is sync


def test_schedule_passes_the_declaration_to_native() -> None:
    background.task("sync", every=timedelta(minutes=30))(lambda: None)
    background.schedule("sync")
    assert _impl().scheduled == {"sync": 1800.0}


def test_requires_charging_implies_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def record(**args: Any) -> None:
        seen.update(args)

    monkeypatch.setattr(_impl(), "schedule", record)
    background.task("sync", every=EVERY, requires_charging=True, requires_network=True)(lambda: None)
    background.schedule("sync")
    assert seen["processing"] is True
    assert seen["requires_network"] is True


@pytest.mark.parametrize("call", [background.schedule, lambda name: asyncio.run(background.run_now(name))])
def test_an_undeclared_task_raises_unknown_task(call: Any) -> None:
    with pytest.raises(NativeModuleError) as caught:
        call("nope")
    assert caught.value.code == "unknown_task"


def test_status_merges_declarations_with_what_native_knows() -> None:
    background.task("sync", every=EVERY)(lambda: None)
    background.task("idle", every=timedelta(hours=1))(lambda: None)
    background.schedule("sync")
    rows = {row.name: row for row in background.status()}
    assert rows["sync"].scheduled is True
    assert rows["sync"].every == EVERY
    assert rows["idle"].scheduled is False
    assert rows["idle"].every == timedelta(hours=1)
    background.cancel("sync")
    assert {row.name: row.scheduled for row in background.status()} == {"sync": False, "idle": False}


def test_status_reports_a_scheduled_task_no_longer_declared(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {"name": "old", "scheduled": True, "every": 900.0, "last_run": 1700000000.0, "last_result": "expired"}
    monkeypatch.setattr(_impl(), "status", lambda: [row])
    (status,) = background.status()
    assert status.name == "old"
    assert status.last_result == "expired"
    assert status.last_run is not None and status.last_run.timestamp() == 1700000000.0


def test_run_now_runs_sync_and_async_functions_in_process() -> None:
    async def later() -> background.Result:
        return background.Result.RETRY

    background.task("later", every=EVERY)(later)
    background.task("plain", every=EVERY)(lambda: None)
    assert run_blocking(background.run_now("later")) is background.Result.RETRY
    assert run_blocking(background.run_now("plain")) is background.Result.SUCCESS
    assert _impl().completed == {}


def test_run_now_lets_exceptions_propagate() -> None:
    def boom() -> None:
        raise KeyError("boom")

    background.task("boom", every=EVERY)(boom)
    with pytest.raises(KeyError):
        run_blocking(background.run_now("boom"))


def _emit_run(invocation: str, name: str) -> None:
    emit("Background", "run", {"id": invocation, "name": name})
    assert drain(2.0, until=lambda: invocation in _impl().completed)


def test_a_run_event_completes_with_the_result() -> None:
    background.task("ok", every=EVERY)(lambda: background.Result.RETRY)
    _emit_run("a", "ok")
    assert _impl().completed == {"a": "retry"}
    assert background._running == {}


def test_a_function_returning_none_succeeds() -> None:
    background.task("ok", every=EVERY)(lambda: None)
    _emit_run("a", "ok")
    assert _impl().completed == {"a": "success"}


def test_an_exception_completes_as_failure() -> None:
    def boom() -> None:
        raise RuntimeError("boom")

    background.task("boom", every=EVERY)(boom)
    _emit_run("a", "boom")
    assert _impl().completed == {"a": "failure"}


def test_a_nonsense_result_completes_as_failure() -> None:
    background.task("odd", every=EVERY)(lambda: "maybe")  # type: ignore[type-var]
    _emit_run("a", "odd")
    assert _impl().completed == {"a": "failure"}


def test_an_unknown_task_completes_as_failure(capsys: pytest.CaptureFixture[str]) -> None:
    _emit_run("a", "ghost")
    assert _impl().completed == {"a": "failure"}
    assert "ghost" in capsys.readouterr().err


def test_a_run_waits_for_a_declaration_still_being_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    # On a device `run` can arrive while the entry module is still importing.
    monkeypatch.setattr("pythonnative.bridge.has_transport", lambda: True)
    monkeypatch.setattr("pythonnative.bootstrap.status", lambda: {})

    async def go() -> Any:
        waiting = asyncio.ensure_future(background._declared("late"))
        await asyncio.sleep(0.05)
        assert not waiting.done()
        background.task("late", every=EVERY)(lambda: None)
        return await waiting

    assert run_blocking(go()).name == "late"


def test_expired_cancels_the_function_without_completing() -> None:
    state: dict[str, bool] = {}

    async def slow() -> None:
        state["started"] = True
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise

    background.task("slow", every=EVERY)(slow)
    emit("Background", "run", {"id": "a", "name": "slow"})
    assert drain(2.0, until=lambda: state.get("started", False))
    emit("Background", "expired", {"id": "a"})
    assert drain(2.0, until=lambda: state.get("cancelled", False))
    drain(0.05)
    assert _impl().completed == {}


def test_expired_for_an_unknown_run_is_harmless() -> None:
    emit("Background", "expired", {"id": "nothing"})


def test_the_contract_lists_the_events_and_methods() -> None:
    contract = schema.MODULES["Background"]
    assert set(contract.events) == {"run", "expired"}
    assert {"ready", "schedule", "cancel", "status", "complete"} <= set(contract.methods)
    on_disk = json.loads((NATIVE / "schema.json").read_text())["modules"]["Background"]
    assert set(on_disk["methods"]) == set(contract.methods)


def test_the_manifest_loads() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "background"
    assert plugin.ios_entry == "BackgroundPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.background.BackgroundPlugin"
    assert any(path.suffix == ".swift" for path in plugin.ios_sources)
    assert any(path.suffix == ".kt" for path in plugin.android_sources)
    assert any(item.startswith("androidx.work:work-runtime-ktx:") for item in plugin.maven_dependencies)


def _config(tmp_path: Path, table: str) -> AppConfig:
    (tmp_path / "pythonnative.toml").write_text(
        f'[app]\nid = "com.example.tasks"\nname = "tasks"\n\n[plugins]\nuse = ["background"]\n{table}'
    )
    return AppConfig.load(tmp_path)


def test_the_tasks_option_reaches_the_plist_as_a_list(tmp_path: Path) -> None:
    config = _config(tmp_path, '\n[plugins.background]\ntasks = ["sync", "report"]\n')
    info = resolve_plugin(load_plugin(NATIVE), config, environ={}).ios["info_plist"]
    assert info["BGTaskSchedulerPermittedIdentifiers"] == ["sync", "report"]
    assert info["UIBackgroundModes"] == ["fetch", "processing"]
    plistlib.dumps(info)


def test_without_tasks_the_plist_is_untouched(tmp_path: Path) -> None:
    # App Store validation rejects these modes without permitted identifiers.
    resolved = resolve_plugin(load_plugin(NATIVE), _config(tmp_path, ""), environ={})
    assert "info_plist" not in resolved.ios
