from pathlib import Path
from typing import List, Optional, Sequence

import pytest

from pythonnative.project import builder as builder_mod
from pythonnative.project.builder import Builder, BuildError, CommandResult, CommandRunner, stage_template
from pythonnative.project.config import AppConfig


class RecordingRunner(CommandRunner):
    """Records commands and simulates Gradle artifact outputs."""

    def __init__(self) -> None:
        self.commands: List[List[str]] = []

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture: bool = False,
    ) -> CommandResult:
        self.commands.append(list(args))
        if cwd and any("assembleRelease" in a for a in args):
            apk = Path(cwd) / "app" / "build" / "outputs" / "apk" / "release"
            apk.mkdir(parents=True, exist_ok=True)
            (apk / "app-release-unsigned.apk").write_bytes(b"apk")
        if cwd and any("bundleRelease" in a for a in args):
            aab = Path(cwd) / "app" / "build" / "outputs" / "bundle" / "release"
            aab.mkdir(parents=True, exist_ok=True)
            (aab / "app-release.aab").write_bytes(b"aab")
        if cwd and any("assembleDebug" in a for a in args):
            apk = Path(cwd) / "app" / "build" / "outputs" / "apk" / "debug"
            apk.mkdir(parents=True, exist_ok=True)
            (apk / "app-debug.apk").write_bytes(b"apk")
        return CommandResult(0)


def _project(tmp_path: Path, toml: str) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("import pythonnative as pn\n", encoding="utf-8")
    (tmp_path / "pythonnative.toml").write_text(toml, encoding="utf-8")
    return tmp_path


_TOML = """
[app]
id = "com.acme.cool"
name = "cool"
display_name = "Cool App"
version = "3.0.0"
build = 5
python_version = "3.11"
[android]
min_sdk = 24
target_sdk = 34
"""


def test_stage_template_copies_android(tmp_path: Path) -> None:
    staged = stage_template("android_template", tmp_path)
    assert staged.is_dir()
    assert (staged / "app" / "build.gradle").is_file()
    assert (staged / "gradlew").is_file()


def test_stage_template_unknown_raises(tmp_path: Path) -> None:
    with pytest.raises(BuildError):
        stage_template("does_not_exist", tmp_path)


def test_prepare_android_integration(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML)
    cfg = AppConfig.load(root)
    prepared = Builder(cfg, runner=RecordingRunner(), log=lambda _m: None).prepare("android")

    assert prepared.app_id == "com.acme.cool"
    relocated = prepared.project_dir / "app" / "src" / "main" / "java" / "com" / "acme" / "cool"
    assert (relocated / "MainActivity.kt").is_file()
    assert "versionCode 5" in (prepared.project_dir / "app" / "build.gradle").read_text()
    staged_app = prepared.project_dir / "app" / "src" / "main" / "python" / "app" / "main.py"
    assert staged_app.is_file()
    # The bundled library excludes the heavy templates directory.
    lib = prepared.project_dir / "app" / "src" / "main" / "python" / "pythonnative"
    assert (lib / "__init__.py").is_file()
    assert not (lib / "templates").exists()


def test_prepare_ios_integration(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML)
    cfg = AppConfig.load(root)
    prepared = Builder(cfg, runner=RecordingRunner(), log=lambda _m: None).prepare("ios")

    assert prepared.app_id == "com.acme.cool"
    import plistlib

    plist = plistlib.loads(prepared.ios.info_plist.read_bytes())
    assert plist["CFBundleDisplayName"] == "Cool App"
    assert (prepared.build_dir / "python" / "app" / "main.py").is_file()


def test_prepare_unknown_platform(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML)
    cfg = AppConfig.load(root)
    with pytest.raises(BuildError):
        Builder(cfg, runner=RecordingRunner(), log=lambda _m: None).prepare("windows")


def test_build_android_release_artifacts(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML)
    cfg = AppConfig.load(root)
    runner = RecordingRunner()
    builder = Builder(cfg, runner=runner, log=lambda _m: None)
    prepared = builder.prepare("android")
    artifacts = builder.build_android(prepared, debug=False)

    names = {p.name for p in artifacts.paths}
    assert "app-release-unsigned.apk" in names
    assert "app-release.aab" in names
    assert any("assembleRelease" in cmd for cmd in runner.commands)
    assert any("bundleRelease" in cmd for cmd in runner.commands)


def test_build_android_debug_artifacts(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML)
    cfg = AppConfig.load(root)
    runner = RecordingRunner()
    builder = Builder(cfg, runner=runner, log=lambda _m: None)
    prepared = builder.prepare("android")
    artifacts = builder.build_android(prepared, debug=True)
    assert any(p.name == "app-debug.apk" for p in artifacts.paths)


def test_build_failure_raises(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML)
    cfg = AppConfig.load(root)

    class FailingRunner(CommandRunner):
        def run(
            self,
            args: Sequence[str],
            *,
            cwd: Optional[Path] = None,
            env: Optional[dict] = None,
            capture: bool = False,
        ) -> CommandResult:
            return CommandResult(1)

    builder = Builder(cfg, runner=FailingRunner(), log=lambda _m: None)
    prepared = builder.prepare("android")
    with pytest.raises(BuildError):
        builder.install_android_debug(prepared)


def test_config_has_android_signing(tmp_path: Path) -> None:
    root = _project(tmp_path, _TOML + '\n[android.signing]\nkeystore = "r.keystore"\nkey_alias = "k"\n')
    cfg = AppConfig.load(root)
    assert builder_mod.config_has_android_signing(cfg) is True
