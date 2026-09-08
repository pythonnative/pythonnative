import sys
from pathlib import Path

from pytest import MonkeyPatch

from pythonnative.project import doctor
from pythonnative.project.config import AppConfig, render_default_toml


def _init(tmp_path: Path) -> None:
    (tmp_path / "pythonnative.toml").write_text(
        render_default_toml(name="demo", app_id="com.example.demo"), encoding="utf-8"
    )


def test_config_check_missing(tmp_path: Path) -> None:
    config, results = doctor.check_config(tmp_path)
    assert config is None
    assert results[0].level == doctor.ERROR
    assert "pythonnative.toml" in results[0].name


def test_config_check_ok(tmp_path: Path) -> None:
    _init(tmp_path)
    config, results = doctor.check_config(tmp_path)
    assert config is not None
    assert results[0].level == doctor.OK


def test_run_doctor_reports_missing_config(tmp_path: Path) -> None:
    results = doctor.run_doctor(tmp_path)
    assert doctor.worst_level(results) == doctor.ERROR
    assert any(r.name == "pythonnative.toml" and r.level == doctor.ERROR for r in results)


def test_run_doctor_platform_filter(tmp_path: Path) -> None:
    _init(tmp_path)
    android_only = doctor.run_doctor(tmp_path, platform="android")
    names = " ".join(r.name for r in android_only)
    assert "adb" in names
    assert "Xcode" not in names


def test_common_checks_present(tmp_path: Path) -> None:
    results = doctor.check_common()
    names = [r.name for r in results]
    assert any("Python" in n for n in names)
    assert any("Pillow" in n for n in names)
    # The browser preview needs nothing beyond the standard library.
    assert not any("Tkinter" in n for n in names)


def _config_with(tmp_path: Path, extra: str = "") -> AppConfig:
    (tmp_path / "pythonnative.toml").write_text(
        '[app]\nid = "com.example.demo"\nname = "demo"\npython_version = "3.14"\n' + extra,
        encoding="utf-8",
    )
    return AppConfig.load(tmp_path)


def test_build_python_for_prefers_running_interpreter() -> None:
    host = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert doctor.build_python_for(host) == sys.executable


def test_build_python_for_searches_path(monkeypatch: MonkeyPatch) -> None:
    host = f"{sys.version_info.major}.{sys.version_info.minor}"
    other = "3.14" if host != "3.14" else "3.13"
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/opt/bin/{name}" if name == f"python{other}" else None)
    assert doctor.build_python_for(other) == f"/opt/bin/python{other}"
    assert doctor.build_python_for("3.99") is None


def test_common_check_reports_matching_build_python(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "build_python_for", lambda v: f"/opt/bin/python{v}")
    result = next(r for r in doctor.check_common(_config_with(tmp_path)) if r.name.startswith("Build Python"))
    assert result.level == doctor.OK
    assert result.name == "Build Python 3.14 (matches app.python_version)"
    assert result.detail == "/opt/bin/python3.14"


def test_common_check_missing_build_python_is_info_without_requirements(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor, "build_python_for", lambda v: None)
    results = doctor.check_common(_config_with(tmp_path))
    result = next(r for r in results if r.name.startswith("Build Python"))
    assert result.level == doctor.INFO
    assert "uv python install 3.14" in result.detail
    assert not any(r.name == "Requirements" for r in results)


def test_common_check_missing_build_python_warns_with_requirements(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "build_python_for", lambda v: None)
    results = doctor.check_common(_config_with(tmp_path, '[requirements]\npackages = ["numpy"]\n'))
    build = next(r for r in results if r.name.startswith("Build Python"))
    assert build.level == doctor.WARN
    reqs = next(r for r in results if r.name == "Requirements")
    assert reqs.level == doctor.INFO
    assert "1 package(s)" in reqs.detail and "pn deps" in reqs.detail


def test_worst_level() -> None:
    assert doctor.worst_level([]) == doctor.OK
    warn = [doctor.CheckResult("a", doctor.OK), doctor.CheckResult("b", doctor.WARN)]
    assert doctor.worst_level(warn) == doctor.WARN
    err = warn + [doctor.CheckResult("c", doctor.ERROR)]
    assert doctor.worst_level(err) == doctor.ERROR


def test_check_result_format() -> None:
    line = doctor.CheckResult("Thing", doctor.OK, "all good").format()
    assert "Thing" in line
    assert "all good" in line
