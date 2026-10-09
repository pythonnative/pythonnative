"""`pn start` single-key commands and editor links (RFC 0006)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import pytest

from pythonnative.cli.keys import KeyCommands
from pythonnative.devserver import editor
from pythonnative.devserver.compat import ProjectRuntime


class FakeServer:
    def __init__(self, runtime: ProjectRuntime) -> None:
        self.project_runtime = runtime
        self.commands: List[str] = []
        self.debug_port = 5678
        self.info = SimpleNamespace(
            preview_url=lambda host: f"http://{host}:8765/?token=t",
            devtools_url=lambda host: f"http://{host}:8765/devtools?token=t",
        )
        self.hub = SimpleNamespace(default_target=lambda: None)

    def broadcast_command(self, name: str) -> None:
        self.commands.append(name)


def _keys(runtime: ProjectRuntime) -> tuple:
    server = FakeServer(runtime)
    logs: List[str] = []
    spawned: List[List[str]] = []
    stopped: List[bool] = []
    session = SimpleNamespace(server=server)
    commands = KeyCommands(session, 8765, logs.append, lambda: stopped.append(True), spawn=spawned.append)
    return commands, server, logs, spawned, stopped


def test_i_and_a_open_go_when_the_project_can_run_there() -> None:
    commands, _server, _logs, spawned, _stopped = _keys(ProjectRuntime(pythonnative="1", protocol=6))
    assert commands.handle("i") and commands.handle("a")
    assert spawned == [["go", "ios", "--port", "8765"], ["go", "android", "--port", "8765"]]


def test_native_code_falls_back_to_the_projects_own_build() -> None:
    commands, _server, logs, spawned, _stopped = _keys(ProjectRuntime(pythonnative="1", protocol=6, plugins=["maps"]))
    commands.handle("i")
    assert spawned == [["run", "ios", "--port", "8765", "--no-logs"]]
    assert any("maps" in line for line in logs)


def test_capital_letters_always_build_the_project() -> None:
    commands, _server, _logs, spawned, _stopped = _keys(ProjectRuntime(pythonnative="1", protocol=6))
    commands.handle("A")
    assert spawned == [["run", "android", "--port", "8765", "--no-logs"]]


def test_reload_menu_and_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    commands, server, logs, _spawned, stopped = _keys(ProjectRuntime(pythonnative="1", protocol=6))
    assert commands.handle("r") and commands.handle("m")
    assert server.commands == ["reload", "menu"]
    commands.handle("?")
    assert any("open DevTools" in line for line in logs)
    commands.handle("d")
    assert any('"port": 5678' in line for line in logs)
    assert commands.handle("q") is False and stopped == [True]


def test_w_and_j_open_the_preview_and_devtools(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: List[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    commands, *_rest = _keys(ProjectRuntime(pythonnative="1", protocol=6))
    commands.handle("w")
    commands.handle("j")
    assert opened == ["http://localhost:8765/?token=t", "http://localhost:8765/devtools?token=t"]


# ======================================================================
# Editor links
# ======================================================================


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("x = 1\n")
    (tmp_path / "secret.txt").write_text("no")
    return root


def test_device_and_relative_paths_resolve_into_the_project(tmp_path: Path) -> None:
    root = _project(tmp_path)
    expected = (root / "app" / "main.py").resolve()
    assert editor.resolve_source("app/main.py", str(root)) == expected
    device = "/var/mobile/Containers/Data/Documents/pythonnative_dev/app/main.py"
    assert editor.resolve_source(device, str(root)) == expected


def test_paths_outside_the_project_never_resolve(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert editor.resolve_source("../secret.txt", str(root)) is None
    assert editor.resolve_source(str(tmp_path / "secret.txt"), str(root)) is None
    assert editor.resolve_source("", str(root)) is None


def test_editor_command_honors_pn_editor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "a b.py"
    monkeypatch.setenv("PN_EDITOR", "subl {file}:{line}")
    assert editor.editor_command(path, 7) == ["subl", f"{path}:7"]
    monkeypatch.setenv("PN_EDITOR", "myeditor --wait")
    assert editor.editor_command(path, 3) == ["myeditor", "--wait", f"{path}:3"]


def test_open_in_editor_spawns_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    launched: List[Any] = []
    monkeypatch.setenv("PN_EDITOR", "ed {file}:{line}")
    monkeypatch.setattr(editor.subprocess, "Popen", lambda command, **kw: launched.append(command))
    assert editor.open_in_editor("app/main.py", 1, str(root)) == str((root / "app" / "main.py").resolve())
    assert launched == [["ed", f"{(root / 'app' / 'main.py').resolve()}:1"]]
    assert editor.open_in_editor("nope.py", 1, str(root)) is None
