import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

import pytest

import pythonnative.cli.pn as pn_cli
import pythonnative.hot_reload as hot_reload_module


def run_pn(args: List[str], cwd: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "pythonnative.cli.pn"] + args
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def test_cli_init_and_clean() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        # init
        result = run_pn(["init", "MyApp"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert os.path.isdir(os.path.join(tmpdir, "app"))
        # scaffolded entrypoint
        main_path = os.path.join(tmpdir, "app", "main.py")
        assert os.path.isfile(main_path)
        with open(main_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "def App(" in content
        assert "Stack.Navigator" in content
        assert "pn.run" not in content
        assert os.path.isfile(os.path.join(tmpdir, "pythonnative.json"))
        assert os.path.isfile(os.path.join(tmpdir, "requirements.txt"))
        assert os.path.isfile(os.path.join(tmpdir, ".gitignore"))

        # clean (on empty build should be no-op)
        result = run_pn(["clean"], tmpdir)
        assert result.returncode == 0, result.stderr

        # create build dir and ensure clean removes it
        os.makedirs(os.path.join(tmpdir, "build", "android"), exist_ok=True)
        result = run_pn(["clean"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert not os.path.exists(os.path.join(tmpdir, "build"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_run_help_lists_logging_flags() -> None:
    """`pn run --help` should advertise both --no-logs and --hot-reload."""
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["run", "--help"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert "--no-logs" in result.stdout
        assert "--hot-reload" in result.stdout
        assert "--prepare-only" in result.stdout
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_run_rejects_unknown_flag() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["run", "android", "--does-not-exist"], tmpdir)
        assert result.returncode != 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_run_prepare_only_android_and_ios() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        # init to create app scaffold
        result = run_pn(["init", "MyApp"], tmpdir)
        assert result.returncode == 0, result.stderr

        # prepare-only android, combined with --no-logs to verify both flags
        # coexist without launching any adb/simctl subprocess (prepare-only
        # returns before logcat would ever be spawned).
        result = run_pn(["run", "android", "--prepare-only", "--no-logs"], tmpdir)
        assert result.returncode == 0, result.stderr
        android_root = os.path.join(tmpdir, "build", "android", "android_template")
        assert os.path.isdir(android_root)
        # Ensure new Fragment-based navigation exists
        page_fragment = os.path.join(
            android_root,
            "app",
            "src",
            "main",
            "java",
            "com",
            "pythonnative",
            "android_template",
            "ScreenFragment.kt",
        )
        assert os.path.isfile(page_fragment)
        virtual_list_helper = os.path.join(
            android_root,
            "app",
            "src",
            "main",
            "java",
            "com",
            "pythonnative",
            "android_template",
            "PNVirtualListView.java",
        )
        assert os.path.isfile(virtual_list_helper)
        nav_graph = os.path.join(
            android_root,
            "app",
            "src",
            "main",
            "res",
            "navigation",
            "nav_graph.xml",
        )
        assert os.path.isfile(nav_graph)

        # prepare-only ios with --no-logs
        result = run_pn(["run", "ios", "--prepare-only", "--no-logs"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert os.path.isdir(os.path.join(tmpdir, "build", "ios", "ios_template"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_booted_ios_udid_picks_first_booted_device(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_booted_ios_udid` parses ``simctl list devices booted --json``."""
    sample_json = (
        '{"devices": {'
        '"com.apple.CoreSimulator.SimRuntime.iOS-26-4": ['
        '{"name": "iPhone 17 Pro", "state": "Booted", "udid": "abc-123"}'
        "]}}"
    )

    class _StubResult:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def _fake_run(cmd: List[str], **kwargs: object) -> _StubResult:
        assert cmd[:2] == ["xcrun", "simctl"]
        assert "booted" in cmd
        return _StubResult(sample_json)

    monkeypatch.setattr(pn_cli.subprocess, "run", _fake_run)
    assert pn_cli._booted_ios_udid() == "abc-123"


def test_booted_ios_udid_returns_none_when_no_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_booted_ios_udid` returns ``None`` when nothing is booted."""

    class _StubResult:
        stdout = '{"devices": {}}'

    monkeypatch.setattr(pn_cli.subprocess, "run", lambda *a, **kw: _StubResult())
    assert pn_cli._booted_ios_udid() is None


def test_booted_ios_udid_handles_xcrun_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_booted_ios_udid` returns ``None`` when ``xcrun`` isn't on PATH."""

    def _raise(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("xcrun missing")

    monkeypatch.setattr(pn_cli.subprocess, "run", _raise)
    assert pn_cli._booted_ios_udid() is None


def test_hot_reload_manifest_payload_maps_files_to_modules(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    changed = app_dir / "main.py"
    changed.write_text("print('hi')\n", encoding="utf-8")

    payload = pn_cli._hot_reload_manifest_payload([os.fspath(changed)], os.fspath(tmp_path), version="v1")

    assert payload == {
        "version": "v1",
        "files": ["app/main.py"],
        "modules": ["app.main"],
    }


def test_android_hot_reload_dest_points_to_overlay() -> None:
    assert pn_cli._android_hot_reload_dest("app/main.py") == os.path.join(
        "files",
        "pythonnative_dev",
        "app/main.py",
    )


def test_clear_ios_hot_reload_overlay_removes_stale_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay = tmp_path / "Documents" / "pythonnative_dev"
    overlay.mkdir(parents=True)
    (overlay / "reload.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(pn_cli, "_ios_data_container", lambda: os.fspath(tmp_path))

    assert pn_cli._clear_ios_hot_reload_overlay() is True
    assert not overlay.exists()


def test_run_hot_reload_imports_top_level_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    build_dir = tmp_path / "build"
    events: list[str] = []

    class FakeWatcher:
        def __init__(self, watch_dir: str, on_change: object, interval: float = 1.0) -> None:
            assert watch_dir == os.fspath(app_dir)

        def start(self) -> None:
            events.append("start")

        def stop(self) -> None:
            events.append("stop")

    def stop_loop(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(hot_reload_module, "FileWatcher", FakeWatcher)
    monkeypatch.setattr("time.sleep", stop_loop)

    pn_cli._run_hot_reload("ios", os.fspath(tmp_path), os.fspath(build_dir), show_logs=False)

    assert events == ["start", "stop"]
