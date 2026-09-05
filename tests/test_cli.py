import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pytest

import pythonnative.cli.pn as pn_cli
from pythonnative.project.devices import Device


def run_pn(args: List[str], cwd: str, env: Optional[Dict[str, str]] = None) -> "subprocess.CompletedProcess[str]":
    cmd = [sys.executable, "-m", "pythonnative.cli.pn"] + args
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True, env=env)


def test_cli_version(tmp_path: Path) -> None:
    result = run_pn(["--version"], str(tmp_path))

    assert result.returncode == 0
    assert result.stdout.strip().startswith("pn ")


def test_cli_short_version_flag(tmp_path: Path) -> None:
    result = run_pn(["-V"], str(tmp_path))

    assert result.returncode == 0
    assert result.stdout.strip().startswith("pn ")


def test_cli_init_and_clean() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["init", "my_app"], tmpdir)
        assert result.returncode == 0, result.stderr
        project_dir = os.path.join(tmpdir, "my_app")
        assert os.path.isdir(os.path.join(project_dir, "app"))

        main_path = os.path.join(project_dir, "app", "main.py")
        assert os.path.isfile(main_path)
        content = Path(main_path).read_text(encoding="utf-8")
        assert "def App(" in content
        assert "Stack.Navigator" in content

        config_path = os.path.join(project_dir, "pythonnative.toml")
        assert os.path.isfile(config_path)
        toml_text = Path(config_path).read_text(encoding="utf-8")
        assert 'id = "com.example.my_app"' in toml_text
        assert os.path.isfile(os.path.join(project_dir, ".gitignore"))
        # The legacy JSON config and requirements.txt are no longer scaffolded.
        assert not os.path.exists(os.path.join(project_dir, "pythonnative.json"))

        # clean on empty build is a no-op
        result = run_pn(["clean"], tmpdir)
        assert result.returncode == 0, result.stderr

        os.makedirs(os.path.join(tmpdir, "build", "android"), exist_ok=True)
        result = run_pn(["clean"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert not os.path.exists(os.path.join(tmpdir, "build"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_init_scaffold_renders_and_navigates() -> None:
    """The generated app must actually run: mount, tap, open Detail, go back."""
    import importlib.util

    from pythonnative.testing import render

    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["init", "my_app"], tmpdir)
        assert result.returncode == 0, result.stderr
        main_path = Path(tmpdir, "my_app", "app", "main.py")
        spec = importlib.util.spec_from_file_location("pn_scaffold_main", main_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        screen = render(module.App())
        screen.press(screen.get_by_text("Tap me"))
        assert screen.get_by_text("Tapped 1 times")
        screen.press(screen.get_by_text("Open detail"))
        assert screen.get_by_text("Detail: count was 1")
        screen.press(screen.get_by_text("Back"))
        assert screen.get_by_text("Tapped 1 times")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_init_refuses_overwrite() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        assert run_pn(["init", "my_app"], tmpdir).returncode == 0
        result = run_pn(["init", "my_app"], tmpdir)
        assert result.returncode != 0
        assert "Refusing to overwrite" in result.stdout
        assert run_pn(["init", "my_app", "--force"], tmpdir).returncode == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_init_creates_named_directory(tmp_path: Path) -> None:
    result = run_pn(["init", "my_app"], str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "cd my_app" in result.stdout

    project_dir = os.path.join(str(tmp_path), "my_app")
    assert os.path.isfile(os.path.join(project_dir, "app", "main.py"))
    assert os.path.isfile(os.path.join(project_dir, "pythonnative.toml"))
    assert os.path.isfile(os.path.join(project_dir, ".gitignore"))
    toml_text = Path(os.path.join(project_dir, "pythonnative.toml")).read_text(encoding="utf-8")
    assert 'id = "com.example.my_app"' in toml_text
    # Nothing is scaffolded beside the project directory.
    assert os.listdir(str(tmp_path)) == ["my_app"]


def test_cli_init_without_name_uses_cwd(tmp_path: Path) -> None:
    project_dir = tmp_path / "widgets"
    project_dir.mkdir()

    result = run_pn(["init"], str(project_dir))
    assert result.returncode == 0, result.stderr
    assert "cd " not in result.stdout

    assert os.path.isfile(os.path.join(str(project_dir), "app", "main.py"))
    assert os.path.isfile(os.path.join(str(project_dir), ".gitignore"))
    toml_text = Path(os.path.join(str(project_dir), "pythonnative.toml")).read_text(encoding="utf-8")
    assert 'id = "com.example.widgets"' in toml_text
    assert 'name = "widgets"' in toml_text


def test_cli_init_refuses_non_empty_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "my_app"
    project_dir.mkdir()
    keeper = project_dir / "README.md"
    keeper.write_text("keep me\n", encoding="utf-8")

    result = run_pn(["init", "my_app"], str(tmp_path))
    assert result.returncode != 0
    assert "Refusing to overwrite" in result.stdout
    assert "non-empty directory" in result.stdout
    assert not os.path.exists(os.path.join(str(project_dir), "app"))
    assert keeper.read_text(encoding="utf-8") == "keep me\n"

    result = run_pn(["init", "my_app", "--force"], str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert os.path.isfile(os.path.join(str(project_dir), "app", "main.py"))
    # --force scaffolds over the directory; it doesn't empty it first.
    assert keeper.read_text(encoding="utf-8") == "keep me\n"


def test_cli_init_accepts_existing_empty_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "my_app"
    project_dir.mkdir()

    result = run_pn(["init", "my_app"], str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert os.path.isfile(os.path.join(str(project_dir), "app", "main.py"))
    assert os.path.isfile(os.path.join(str(project_dir), "pythonnative.toml"))


def test_cli_init_refuses_existing_file(tmp_path: Path) -> None:
    blocker = tmp_path / "my_app"
    blocker.write_text("not a project\n", encoding="utf-8")

    result = run_pn(["init", "my_app"], str(tmp_path))
    assert result.returncode != 0
    assert "Refusing to overwrite existing file" in result.stdout

    # --force can't turn a file into a directory, so it is refused too.
    result = run_pn(["init", "my_app", "--force"], str(tmp_path))
    assert result.returncode != 0
    assert "Refusing to overwrite existing file" in result.stdout
    assert blocker.read_text(encoding="utf-8") == "not a project\n"


@pytest.mark.parametrize("name", ["{absolute}", "nested/my_app", "my_app/", ".", "..", "../", "a/.."])
def test_cli_init_rejects_path_like_names(tmp_path: Path, name: str) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    result = run_pn(["init", name.format(absolute=str(tmp_path / "elsewhere"))], str(work_dir))
    assert result.returncode != 0
    assert "Refusing to" in result.stdout
    assert "project name" in result.stdout
    # Nothing was created in the working directory or anywhere above it.
    assert os.listdir(str(work_dir)) == []
    assert os.listdir(str(tmp_path)) == ["work"]


def test_cli_init_force_does_not_escape_to_parent(tmp_path: Path) -> None:
    parent_config = tmp_path / "pythonnative.toml"
    parent_config.write_text("# hand-written\n", encoding="utf-8")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    result = run_pn(["init", "..", "--force"], str(work_dir))
    assert result.returncode != 0
    assert "Refusing to" in result.stdout
    # --force does not lift the single-name rule, so the parent is untouched.
    assert parent_config.read_text(encoding="utf-8") == "# hand-written\n"
    assert not os.path.exists(os.path.join(str(tmp_path), "app"))
    assert not os.path.exists(os.path.join(str(tmp_path), ".gitignore"))
    assert os.listdir(str(work_dir)) == []


@pytest.mark.parametrize("extra_args", [[], ["--force"]])
@pytest.mark.parametrize("populated", [True, False])
def test_cli_init_rejects_symlinked_target(tmp_path: Path, populated: bool, extra_args: List[str]) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_config = outside / "pythonnative.toml"
    if populated:
        outside_config.write_text("# hand-written\n", encoding="utf-8")
    before = sorted(os.listdir(str(outside)))

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    os.symlink(str(outside), os.path.join(str(work_dir), "link"))

    result = run_pn(["init", "link"] + extra_args, str(work_dir))
    assert result.returncode != 0
    assert "Refusing to" in result.stdout
    # exists() and is_dir() follow symlinks, so the destination must stay untouched:
    # no new entries, and no rewrite of a config that was already there.
    assert sorted(os.listdir(str(outside))) == before
    if populated:
        assert outside_config.read_text(encoding="utf-8") == "# hand-written\n"
    assert os.listdir(str(work_dir)) == ["link"]


_ILLEGAL_NAMES = [
    pytest.param("MyApp", id="uppercase"),
    pytest.param("my app", id="space"),
    pytest.param('bad"name', id="quote"),
    pytest.param("9lives", id="leading-digit"),
    pytest.param("_leading", id="leading-underscore"),
    pytest.param("café", id="non-ascii"),
    pytest.param("", id="empty"),
    # `$` matches before a trailing newline, so `match` would let this through.
    pytest.param("app\n", id="trailing-newline"),
]


@pytest.mark.parametrize("name", _ILLEGAL_NAMES)
def test_cli_init_rejects_illegal_names(tmp_path: Path, name: str) -> None:
    result = run_pn(["init", name], str(tmp_path))

    assert result.returncode != 0
    assert "Invalid project name" in result.stdout
    assert "Try: " in result.stdout
    # Nothing is written, not even into the current directory.
    assert os.listdir(str(tmp_path)) == []


@pytest.mark.parametrize("name", _ILLEGAL_NAMES)
def test_cli_init_force_does_not_lift_name_validation(tmp_path: Path, name: str) -> None:
    result = run_pn(["init", name, "--force"], str(tmp_path))

    assert result.returncode != 0
    assert "Invalid project name" in result.stdout
    assert os.listdir(str(tmp_path)) == []


def test_cli_init_suggestion_is_itself_a_legal_name() -> None:
    # The suggestion is only useful if the user can paste it straight back.
    awkward = [
        "MyApp",
        "my app",
        'bad"name',
        "9lives",
        "_leading",
        "café",
        "",
        "___",
        "---",
        "123",
        "..",
        "a/b",
        "ÄÖÜ",
        "\t",
        "app\n",
        "app\n\n",
        "\napp",
        "\n",
        "\x00",
        "\x7f",
        "sp ace",
        "trailing_",
        "-lead",
        "mixed_-CASE-99",
        "🙂",
        "a" * 200,
    ]
    for name in awkward:
        assert pn_cli._NAME_RE.fullmatch(pn_cli._sanitize_name(name)), name


def test_cli_init_suggestion_is_stable_for_legal_names() -> None:
    for name in ["my_app", "my-app", "a", "a1", "hello-world_2"]:
        assert pn_cli._sanitize_name(name) == name


def test_cli_init_without_name_accepts_a_cwd_that_fails_the_pattern(tmp_path: Path) -> None:
    # Validation covers the typed name only. A directory named MyProject is
    # extremely ordinary, and `pn init` there must keep working.
    project_dir = tmp_path / "MyProject"
    project_dir.mkdir()

    result = run_pn(["init"], str(project_dir))

    assert result.returncode == 0, result.stdout
    toml_text = (project_dir / "pythonnative.toml").read_text(encoding="utf-8")
    assert 'name = "MyProject"' in toml_text
    assert 'id = "com.example.myproject"' in toml_text


def test_cli_run_help_lists_flags() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["run", "--help"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert "--no-logs" in result.stdout
        assert "--dev-server" in result.stdout
        assert "--prepare-only" in result.stdout
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_build_help_lists_debug() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["build", "--help"], tmpdir)
        assert result.returncode == 0, result.stderr
        assert "--debug" in result.stdout
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_run_rejects_unknown_flag() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["run", "android", "--does-not-exist"], tmpdir)
        assert result.returncode != 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_run_without_config_errors() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        result = run_pn(["run", "android"], tmpdir)
        assert result.returncode != 0
        assert "No pythonnative.toml" in (result.stdout + result.stderr)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# A default `pn init` scaffold sets only `app.id`, so both platforms resolve to
# the same string and a test built on it passes with the platform branch
# inverted. These per-platform overrides make the two diverge.
_APP_ID_TOML = """\
[app]
id = "com.example.base"
name = "over"

[ios]
bundle_id = "com.example.ios_override"

[android]
application_id = "com.example.android_override"
"""

_EXPECTED_APP_IDS = {
    "android": "com.example.android_override",
    "ios": "com.example.ios_override",
}


def _app_id_project(tmp_path: Path) -> str:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "pythonnative.toml").write_text(_APP_ID_TOML, encoding="utf-8")
    return str(project_dir)


@pytest.mark.parametrize("platform", ["android", "ios"])
def test_cli_app_id_resolves(tmp_path: Path, platform: str) -> None:
    project_dir = _app_id_project(tmp_path)

    result = run_pn(["app-id", platform], project_dir)

    assert result.returncode == 0, result.stderr
    # Unstripped, because scripts/run-e2e.sh captures this into a shell
    # variable: any extra line would corrupt APP_ID and only surface later
    # as a Maestro failure against a bundle id that doesn't exist.
    assert result.stdout == f"{_EXPECTED_APP_IDS[platform]}\n"
    assert result.stderr == ""


@pytest.mark.parametrize("platform", ["android", "ios"])
def test_cli_app_id_json(tmp_path: Path, platform: str) -> None:
    project_dir = _app_id_project(tmp_path)

    result = run_pn(["app-id", platform, "--json"], project_dir)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"platform": platform, "app_id": _EXPECTED_APP_IDS[platform]}
    assert result.stderr == ""


def test_cli_app_id_json_is_indented(tmp_path: Path) -> None:
    # json.loads is blind to formatting, so nothing else here would notice
    # indent=2 being dropped. Scripts consume the bytes, and the docstring
    # promises an additive-only contract, so pin the exact shape once.
    project_dir = _app_id_project(tmp_path)

    result = run_pn(["app-id", "android", "--json"], project_dir)

    assert result.stdout == ("{\n" '  "platform": "android",\n' '  "app_id": "com.example.android_override"\n' "}\n")


def test_cli_app_id_json_differs_per_platform(tmp_path: Path) -> None:
    # The pair, so a branch that ignored `platform` would fail even if each
    # single-platform assertion above were somehow satisfied.
    project_dir = _app_id_project(tmp_path)

    android = json.loads(run_pn(["app-id", "android", "--json"], project_dir).stdout)
    ios = json.loads(run_pn(["app-id", "ios", "--json"], project_dir).stdout)

    assert android["app_id"] != ios["app_id"]


def test_cli_app_id_json_keeps_errors_off_stdout(tmp_path: Path) -> None:
    # Without --json this same error goes to stdout, which is why the stream
    # is scoped rather than global.
    result = run_pn(["app-id", "android", "--json"], str(tmp_path))

    assert result.returncode == 1
    assert result.stdout == ""
    # Match the noun, not the sentence. A malformed config also exits 1 with
    # an error on stderr, so without this phrase the test passes for either.
    assert "No pythonnative.toml" in result.stderr


def test_cli_app_id_plain_error_stays_on_stdout(tmp_path: Path) -> None:
    # Pins the scoping: the default path is untouched by the stream change.
    result = run_pn(["app-id", "android"], str(tmp_path))

    assert result.returncode == 1
    assert "No pythonnative.toml" in result.stdout
    assert result.stderr == ""


def test_cli_app_id_json_flag_is_wired_through_argparse(tmp_path: Path) -> None:
    # Everything here goes through run_pn, so argparse is always exercised.
    # Confirmed rather than assumed: #22 shipped six in-process tests that
    # all passed with the add_argument deleted.
    result = run_pn(["app-id", "android", "--json"], str(tmp_path))

    assert result.returncode == 1, "expected the config error, not argparse exit 2"
    assert "unrecognized arguments" not in result.stderr


def test_cli_doctor_runs(tmp_path: Path) -> None:
    assert run_pn(["init", "my_app"], str(tmp_path)).returncode == 0
    result = run_pn(["doctor", "android"], str(tmp_path / "my_app"))
    assert "PythonNative doctor" in result.stdout
    # android-only doctor on a CI box without adb still produces warnings, not errors.
    assert result.returncode in (0, 1)


def test_cli_run_prepare_only_android_and_ios() -> None:
    tmpdir = tempfile.mkdtemp(prefix="pn_cli_test_")
    try:
        assert run_pn(["init", "my_app"], tmpdir).returncode == 0
        project_dir = os.path.join(tmpdir, "my_app")

        result = run_pn(["run", "android", "--prepare-only", "--no-logs"], project_dir)
        assert result.returncode == 0, result.stderr
        android_root = os.path.join(project_dir, "build", "android", "android_template")
        assert os.path.isdir(android_root)
        # Package relocated to the configured application id.
        relocated = os.path.join(
            android_root, "app", "src", "main", "java", "com", "example", "my_app", "ScreenFragment.kt"
        )
        assert os.path.isfile(relocated)
        assert not os.path.exists(
            os.path.join(android_root, "app", "src", "main", "java", "com", "pythonnative", "android_template")
        )
        # App identity written into the Gradle config.
        gradle = Path(os.path.join(android_root, "app", "build.gradle")).read_text(encoding="utf-8")
        assert "com.example.my_app" in gradle

        result = run_pn(["run", "ios", "--prepare-only", "--no-logs"], project_dir)
        assert result.returncode == 0, result.stderr
        ios_root = os.path.join(project_dir, "build", "ios", "ios_template")
        assert os.path.isdir(ios_root)
        info_plist = Path(os.path.join(ios_root, "ios_template", "Info.plist")).read_bytes()
        assert b"CFBundleDisplayName" in info_plist
        # Both package slices are staged; the build phase picks one per SDK.
        assert os.path.isdir(os.path.join(ios_root, "app_packages.iphoneos", "pythonnative"))
        assert os.path.isdir(os.path.join(ios_root, "app_packages.iphonesimulator", "pythonnative"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# pn deps
# ---------------------------------------------------------------------------


def _deps_project(tmp_path: Path, packages: str = '["httpx", "numpy"]') -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("import pythonnative as pn\n", encoding="utf-8")
    (tmp_path / "pythonnative.toml").write_text(
        '[app]\nid = "com.acme.deps"\nname = "deps"\npython_version = "3.13"\n'
        f"[requirements]\npackages = {packages}\n",
        encoding="utf-8",
    )
    return tmp_path


_NUMPY_IOS_WHEEL = "https://pypi.anaconda.org/beeware/simple/numpy/numpy-2.2.1-cp313-cp313-ios_13_0_arm64_iphoneos.whl"
_HTTPX_WHEEL = "https://files.pythonhosted.org/packages/x/httpx-0.27.0-py3-none-any.whl"


class _FakePipRunner:
    """Answers pip dry-run reports per target, failing where ``fail_when`` matches."""

    def __init__(self, fail_when: Callable[[List[str]], bool] = lambda _args: False) -> None:
        self.fail_when = fail_when
        self.commands: List[List[str]] = []

    def run(self, args, *, cwd=None, env=None, capture=False):  # type: ignore[no-untyped-def]
        from pythonnative.project.builder import CommandResult

        self.commands.append(list(args))
        if self.fail_when(list(args)):
            return CommandResult(1, "", "ERROR: No matching distribution found for numpy")
        report = {
            "install": [
                {"metadata": {"name": "httpx", "version": "0.27.0"}, "download_info": {"url": _HTTPX_WHEEL}},
                {"metadata": {"name": "numpy", "version": "2.2.1"}, "download_info": {"url": _NUMPY_IOS_WHEEL}},
            ]
        }
        return CommandResult(0, json.dumps(report), "")


def test_deps_command_reports_every_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_deps_project(tmp_path))
    runner = _FakePipRunner()
    monkeypatch.setattr(pn_cli.builder_mod, "SubprocessRunner", lambda: runner)
    monkeypatch.setattr(pn_cli.deps_mod, "host_simulator_arch", lambda: "arm64")

    pn_cli.deps_command(argparse.Namespace(platform=None, json=False, python=None))

    out = capsys.readouterr().out
    assert "iOS device (arm64, iOS 13.0+)" in out
    assert "iOS Simulator (arm64, iOS 13.0+)" in out
    assert "Android arm64-v8a (API 24+)" in out and "Android x86_64 (API 24+)" in out
    assert "[ok] numpy 2.2.1" in out and "(BeeWare)" in out
    assert "All 4 targets resolved." in out
    # One pip dry-run per target, each pinned to the target's tags, never
    # the host's, plus one unconstrained reference run for downgrade detection.
    target_cmds = [c for c in runner.commands if "--platform" in c]
    assert len(target_cmds) == 4 and len(runner.commands) == 5
    for cmd in target_cmds:
        assert "--dry-run" in cmd and "--only-binary=:all:" in cmd
        assert cmd[cmd.index("--python-version") + 1] == "3.13"
    android_cmds = [c for c in target_cmds if any(a.startswith("android_") for a in c)]
    assert len(android_cmds) == 2


def test_deps_command_platform_filter_and_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_deps_project(tmp_path))
    runner = _FakePipRunner()
    monkeypatch.setattr(pn_cli.builder_mod, "SubprocessRunner", lambda: runner)

    pn_cli.deps_command(argparse.Namespace(platform="android", json=True, python="/opt/python3.13"))

    data = json.loads(capsys.readouterr().out)
    assert data["python_version"] == "3.13"
    assert data["requirements"] == ["httpx", "numpy"]
    assert [t["platform"] for t in data["targets"]] == ["android", "android"]
    assert all(t["ok"] for t in data["targets"])
    assert data["targets"][0]["packages"][0]["name"] == "httpx"
    assert all(cmd[0] == "/opt/python3.13" for cmd in runner.commands)


def test_deps_command_exits_nonzero_when_a_target_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_deps_project(tmp_path))
    runner = _FakePipRunner(fail_when=lambda args: any("iphonesimulator" in a for a in args))
    monkeypatch.setattr(pn_cli.builder_mod, "SubprocessRunner", lambda: runner)

    with pytest.raises(SystemExit) as info:
        pn_cli.deps_command(argparse.Namespace(platform="ios", json=False, python=None))
    assert info.value.code == 1
    out = capsys.readouterr().out
    assert "[x] ERROR: No matching distribution found for numpy" in out
    assert "1 of 2 targets cannot be satisfied" in out


def test_deps_command_without_requirements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_deps_project(tmp_path, packages="[]"))
    runner = _FakePipRunner()
    monkeypatch.setattr(pn_cli.builder_mod, "SubprocessRunner", lambda: runner)

    pn_cli.deps_command(argparse.Namespace(platform=None, json=False, python=None))

    assert "nothing to resolve" in capsys.readouterr().out
    assert runner.commands == []


def test_cli_deps_help_lists_flags() -> None:
    result = run_pn(["deps", "--help"], os.getcwd())
    assert result.returncode == 0
    assert "--json" in result.stdout
    assert "--python" in result.stdout
    assert "android" in result.stdout and "ios" in result.stdout


# ---------------------------------------------------------------------------
# Pure helpers (no device required)
# ---------------------------------------------------------------------------


def test_booted_ios_udid_picks_first_booted_device(monkeypatch: pytest.MonkeyPatch) -> None:
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
    class _StubResult:
        stdout = '{"devices": {}}'

    monkeypatch.setattr(pn_cli.subprocess, "run", lambda *a, **kw: _StubResult())
    assert pn_cli._booted_ios_udid() is None


def test_booted_ios_udid_handles_xcrun_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("xcrun missing")

    monkeypatch.setattr(pn_cli.subprocess, "run", _raise)
    assert pn_cli._booted_ios_udid() is None


# `pn devices` tests run devices_command() in-process rather than through run_pn,
# because run_pn spawns a child interpreter that monkeypatch can't reach: it would
# re-import the real list_devices and shell out to adb/xcrun, making the result
# depend on whatever hardware the test machine has attached. The one run_pn test
# below empties PATH instead, so every list_* call hits FileNotFoundError.

# A naive `state == "booted"` readiness check disagrees with is_ready on two of
# these: the connected Android device (ready, not booted) and the shutdown
# simulator (ready, because simulators boot on demand).
_FAKE_DEVICES = [
    Device("android", "device", "R5CT12345XYZ", "Pixel 8 Pro", "", "connected"),
    Device("android", "device", "OFFLINE99", "Galaxy S24", "", "offline"),
    Device("ios", "simulator", "ABC-123", "iPhone 17 Pro", "iOS 26.4", "booted"),
    Device("ios", "simulator", "DEF-456", "iPad Pro 13-inch (M4)", "iOS 26.4", "shutdown"),
]

_NO_DEVICES_HINTS = (
    "No devices found.\n"
    "Android: start an emulator or connect a device with USB debugging enabled.\n"
    "iOS: open Xcode once to install Simulators, or plug in a device.\n"
)

_DEVICE_TABLE = (
    "  IDENTIFIER                               KIND       STATE      NAME\n"
    "  R5CT12345XYZ                             device     connected  Pixel 8 Pro\n"
    "  OFFLINE99                                device     offline    Galaxy S24\n"
    "  ABC-123                                  simulator  booted     iPhone 17 Pro (iOS 26.4)\n"
    "  DEF-456                                  simulator  shutdown   iPad Pro 13-inch (M4) (iOS 26.4)\n"
    "\n"
    "Target one with: pn run <platform> --device <identifier or name>\n"
)


def _fake_list_devices(
    devices: List[Device], calls: Optional[List[Optional[str]]] = None
) -> Callable[..., List[Device]]:
    """Stand in for list_devices, filtering by platform and recording the argument."""

    def _list(platform: Optional[str] = None) -> List[Device]:
        if calls is not None:
            calls.append(platform)
        return [device for device in devices if platform in (None, device.platform)]

    return _list


def test_devices_json_emits_parseable_array(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))

    # Returns rather than exiting, so a populated listing stays exit 0.
    pn_cli.devices_command(argparse.Namespace(platform=None, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert [entry["identifier"] for entry in payload] == [
        "R5CT12345XYZ",
        "OFFLINE99",
        "ABC-123",
        "DEF-456",
    ]
    for entry in payload:
        assert set(entry) == {
            "platform",
            "kind",
            "identifier",
            "name",
            "os_version",
            "state",
            "is_ready",
        }
    ready = {entry["identifier"]: entry["is_ready"] for entry in payload}
    assert ready == {"R5CT12345XYZ": True, "OFFLINE99": False, "ABC-123": True, "DEF-456": True}

    # The two entries a naive `state == "booted"` check would get wrong.
    by_id = {entry["identifier"]: entry for entry in payload}
    assert by_id["DEF-456"]["state"] == "shutdown" and by_id["DEF-456"]["is_ready"] is True
    assert by_id["R5CT12345XYZ"]["state"] == "connected" and by_id["R5CT12345XYZ"]["is_ready"] is True
    assert by_id["OFFLINE99"]["kind"] == "device" and by_id["OFFLINE99"]["is_ready"] is False


def test_devices_json_empty_prints_array_and_hints_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices([]))

    # No SystemExit: an empty result is exit 0 under --json, unlike the table.
    pn_cli.devices_command(argparse.Namespace(platform=None, json=True))

    captured = capsys.readouterr()
    assert captured.out == "[]\n"
    assert json.loads(captured.out) == []
    assert captured.err == _NO_DEVICES_HINTS


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("android", ["R5CT12345XYZ", "OFFLINE99"]), ("ios", ["ABC-123", "DEF-456"])],
)
def test_devices_json_respects_platform_filter(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    platform: str,
    expected: List[str],
) -> None:
    calls: List[Optional[str]] = []
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES, calls))

    pn_cli.devices_command(argparse.Namespace(platform=platform, json=True))

    assert calls == [platform]
    payload = json.loads(capsys.readouterr().out)
    assert {entry["platform"] for entry in payload} == {platform}
    assert [entry["identifier"] for entry in payload] == expected


@pytest.mark.parametrize("devices", [[], _FAKE_DEVICES], ids=["empty", "populated"])
def test_devices_json_keeps_human_text_off_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], devices: List[Device]
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(devices))

    pn_cli.devices_command(argparse.Namespace(platform=None, json=True))

    out = capsys.readouterr().out
    json.loads(out)
    # Every non-JSON source the table mode prints: the three hints, the column
    # header, each aligned row, and the trailer.
    for hint in _NO_DEVICES_HINTS.splitlines():
        assert hint not in out
    assert "IDENTIFIER" not in out
    assert "Target one with:" not in out
    for device in devices:
        assert device.format() not in out


def test_devices_human_output_unchanged_when_empty(tmp_path: Path) -> None:
    # An empty PATH makes adb/xcrun unresolvable, so every list_* call returns [].
    env = {**os.environ, "PATH": str(tmp_path)}
    result = run_pn(["devices"], str(tmp_path), env=env)

    assert result.returncode == 1
    assert result.stdout == _NO_DEVICES_HINTS
    assert result.stderr == ""


def test_devices_human_output_unchanged_when_populated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))

    pn_cli.devices_command(argparse.Namespace(platform=None, json=False))

    captured = capsys.readouterr()
    assert captured.out == _DEVICE_TABLE
    assert captured.err == ""


def test_devices_json_flag_is_wired_through_argparse(tmp_path: Path) -> None:
    # The other JSON tests call devices_command() directly, so only this one
    # proves the subparser actually accepts --json and routes it through.
    env = {**os.environ, "PATH": str(tmp_path)}
    result = run_pn(["devices", "--json"], str(tmp_path), env=env)

    assert result.returncode == 0
    assert json.loads(result.stdout) == []
    assert result.stdout == "[]\n"
    assert result.stderr == _NO_DEVICES_HINTS


def test_devices_json_serializes_awkward_field_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Quotes, a newline, non-ASCII, and the two empty-string defaults all survive
    # the round trip today; nothing pinned them before.
    awkward = Device("android", "device", "SER!@#123", 'M\u00e1laga "Pixel"\nLab', "", "")
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices([awkward]))

    pn_cli.devices_command(argparse.Namespace(platform=None, json=True))

    (entry,) = json.loads(capsys.readouterr().out)
    assert entry == {
        "platform": "android",
        "kind": "device",
        "identifier": "SER!@#123",
        "name": 'M\u00e1laga "Pixel"\nLab',
        "os_version": "",
        "state": "",
        "is_ready": False,
    }


class _FakeCompletedProc:
    """Stand-in for subprocess.Popen that returns immediately from wait()."""

    def wait(self) -> int:
        return 0


def test_logs_command_android_sets_android_serial_for_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))
    monkeypatch.delenv("ANDROID_SERIAL", raising=False)
    monkeypatch.setattr(pn_cli, "_start_android_log_stream", lambda: _FakeCompletedProc())

    pn_cli.logs_command(argparse.Namespace(platform="android", device="Pixel"))

    # pop() rather than a plain lookup: monkeypatch.delenv() on a variable that
    # was never set has nothing to restore, so the value the command exported
    # would otherwise leak into the rest of the session.
    assert os.environ.pop("ANDROID_SERIAL") == "R5CT12345XYZ"


def test_logs_command_android_no_device_leaves_android_serial_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))
    monkeypatch.delenv("ANDROID_SERIAL", raising=False)
    monkeypatch.setattr(pn_cli, "_start_android_log_stream", lambda: _FakeCompletedProc())

    pn_cli.logs_command(argparse.Namespace(platform="android", device=None))

    assert "ANDROID_SERIAL" not in os.environ


def test_logs_command_ios_passes_resolved_udid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))
    monkeypatch.setattr(
        pn_cli, "_load_config_or_exit", lambda project_dir=None: argparse.Namespace(bundle_id="com.example.app")
    )
    captured: Dict[str, Optional[str]] = {}

    def _fake_start_ios_log_stream(bundle_id: str, *, udid: Optional[str] = None) -> _FakeCompletedProc:
        captured["bundle_id"] = bundle_id
        captured["udid"] = udid
        return _FakeCompletedProc()

    monkeypatch.setattr(pn_cli, "_start_ios_log_stream", _fake_start_ios_log_stream)

    pn_cli.logs_command(argparse.Namespace(platform="ios", device="iPhone 17"))

    assert captured == {"bundle_id": "com.example.app", "udid": "ABC-123"}


def test_logs_command_ios_no_device_falls_back_to_booted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))
    monkeypatch.setattr(
        pn_cli, "_load_config_or_exit", lambda project_dir=None: argparse.Namespace(bundle_id="com.example.app")
    )
    captured: Dict[str, Optional[str]] = {}

    def _fake_start_ios_log_stream(bundle_id: str, *, udid: Optional[str] = None) -> _FakeCompletedProc:
        captured["udid"] = udid
        return _FakeCompletedProc()

    monkeypatch.setattr(pn_cli, "_start_ios_log_stream", _fake_start_ios_log_stream)

    pn_cli.logs_command(argparse.Namespace(platform="ios", device=None))

    assert captured["udid"] is None


def test_logs_command_ios_physical_device_prints_console_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    physical = Device("ios", "device", "PHYS-1", "Owen's iPhone", "iOS 26.4", "connected")
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices([physical]))

    with pytest.raises(SystemExit) as exc_info:
        pn_cli.logs_command(argparse.Namespace(platform="ios", device="Owen's iPhone"))

    assert exc_info.value.code == 1
    assert "Console.app" in capsys.readouterr().out


def test_logs_command_ios_no_simulator_prints_console_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Without --device and with no booted simulator, the user may well be
    # holding a physical device, so the Console.app pointer must still print.
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))
    monkeypatch.setattr(
        pn_cli, "_load_config_or_exit", lambda project_dir=None: argparse.Namespace(bundle_id="com.example.app")
    )
    monkeypatch.setattr(pn_cli, "_start_ios_log_stream", lambda bundle_id, *, udid=None: None)

    with pytest.raises(SystemExit) as exc_info:
        pn_cli.logs_command(argparse.Namespace(platform="ios", device=None))

    assert exc_info.value.code == 1
    assert "Console.app" in capsys.readouterr().out


def test_logs_command_bad_device_query_exits_with_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pn_cli.devices_mod, "list_devices", _fake_list_devices(_FAKE_DEVICES))

    with pytest.raises(SystemExit) as exc_info:
        pn_cli.logs_command(argparse.Namespace(platform="android", device="nope"))

    assert exc_info.value.code == 1
    assert "no android device matches 'nope'" in capsys.readouterr().out


def test_logs_device_flag_is_wired_through_argparse(tmp_path: Path) -> None:
    # The tests above call logs_command() directly; this one proves the
    # subparser actually accepts --device and routes it through.
    env = {**os.environ, "PATH": str(tmp_path)}
    result = run_pn(["logs", "android", "--device", "nope"], str(tmp_path), env=env)

    assert result.returncode == 1
    assert "no android device matches 'nope'" in result.stdout


# ======================================================================
# run: dev server discovery and native fingerprints
# ======================================================================


def test_dev_server_url_for_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    import pythonnative.devserver as devserver

    monkeypatch.setattr(devserver, "lan_addresses", lambda: ["192.168.1.20"])
    sim = Device(platform="ios", identifier="SIM", name="iPhone", kind="simulator", state="Booted")
    phone = Device(platform="ios", identifier="PHONE", name="iPhone", kind="device", state="connected")

    assert pn_cli._dev_server_url_for("ios", None, 8765) == "ws://localhost:8765/ws?role=client"
    assert pn_cli._dev_server_url_for("ios", sim, 8765) == "ws://localhost:8765/ws?role=client"
    assert pn_cli._dev_server_url_for("android", None, 9000) == "ws://localhost:9000/ws?role=client"
    assert pn_cli._dev_server_url_for("ios", phone, 8765) == "ws://192.168.1.20:8765/ws?role=client"


def test_running_dev_server_returns_none_when_nothing_listens() -> None:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert pn_cli._running_dev_server(free_port) is None


def test_run_reuses_artifact_when_fingerprint_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unchanged native fingerprint plus a live dev server skips the toolchain."""
    from pythonnative.project import builder as builder_mod
    from pythonnative.project import fingerprint as fingerprint_mod
    from pythonnative.project.config import AppConfig, render_default_toml

    (tmp_path / "pythonnative.toml").write_text(render_default_toml(name="demo", app_id="com.example.demo"))
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("App = None\n")
    monkeypatch.chdir(tmp_path)
    config = AppConfig.load(tmp_path)
    builder = builder_mod.Builder(config, log=lambda *_: None)
    fingerprint = pn_cli._native_fingerprint(
        builder.config, "ios", builder, ios_sdks=("iphonesimulator",), dev_client=False
    )
    artifact = tmp_path / "Demo.app"
    artifact.mkdir()
    fingerprint_mod.write_stamp(tmp_path / "build" / "ios", fingerprint, artifact=artifact)

    prepared_calls: List[str] = []

    def fake_prepare(self: object, platform: str, **kw: object) -> None:
        prepared_calls.append(platform)

    monkeypatch.setattr(builder_mod.Builder, "prepare", fake_prepare)
    monkeypatch.setattr(pn_cli, "_running_dev_server", lambda port: {"port": port})
    launched: Dict[str, object] = {}

    def fake_sim(builder: object, prepared: object, *, artifact: object, **kw: object) -> object:
        launched.update(prepared=prepared, artifact=artifact, server_url=kw["server_url"])
        return artifact

    monkeypatch.setattr(pn_cli, "_run_ios_simulator", fake_sim)

    args = argparse.Namespace(platform="ios", device=None, no_logs=True, rebuild=False, dev_client=False)
    pn_cli.run_project(args)

    assert prepared_calls == [], "native toolchain must not run for an unchanged fingerprint"
    assert launched["prepared"] is None
    assert launched["artifact"] == artifact
    assert launched["server_url"] == "ws://localhost:8765/ws?role=client"


def test_run_rebuilds_without_a_dev_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without `pn start` the bundled sources are all the app has, so it must be rebuilt."""
    from pythonnative.project import builder as builder_mod
    from pythonnative.project import fingerprint as fingerprint_mod
    from pythonnative.project.config import AppConfig, render_default_toml

    (tmp_path / "pythonnative.toml").write_text(render_default_toml(name="demo", app_id="com.example.demo"))
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("App = None\n")
    monkeypatch.chdir(tmp_path)
    config = AppConfig.load(tmp_path)
    builder = builder_mod.Builder(config, log=lambda *_: None)
    fingerprint = pn_cli._native_fingerprint(
        builder.config, "ios", builder, ios_sdks=("iphonesimulator",), dev_client=False
    )
    artifact = tmp_path / "Demo.app"
    artifact.mkdir()
    fingerprint_mod.write_stamp(tmp_path / "build" / "ios", fingerprint, artifact=artifact)

    prepared = builder_mod.PreparedProject(
        platform="ios", build_dir=tmp_path / "build" / "ios", project_dir=tmp_path, app_id="x"
    )
    monkeypatch.setattr(builder_mod.Builder, "prepare", lambda self, platform, **kw: prepared)
    monkeypatch.setattr(pn_cli, "_running_dev_server", lambda port: None)
    seen: Dict[str, object] = {}

    def fake_sim(builder: object, prepared_arg: object, *, artifact: object, **kw: object) -> object:
        seen.update(prepared=prepared_arg, server_url=kw["server_url"])
        return artifact

    monkeypatch.setattr(pn_cli, "_run_ios_simulator", fake_sim)
    pn_cli.run_project(argparse.Namespace(platform="ios", device=None, no_logs=True, rebuild=False, dev_client=False))

    assert seen["prepared"] is prepared
    assert seen["server_url"] is None


def test_start_help_lists_dev_server_flags(tmp_path: Path) -> None:
    result = run_pn(["start", "--help"], str(tmp_path))
    assert result.returncode == 0
    assert "--port" in result.stdout
    assert "--open" in result.stdout
    result = run_pn(["run", "--help"], str(tmp_path))
    assert "--dev-client" in result.stdout
    assert "--rebuild" in result.stdout
    assert "--hot-reload" not in result.stdout
