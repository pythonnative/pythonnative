from pathlib import Path

from pythonnative.project import doctor
from pythonnative.project.config import render_default_toml


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
