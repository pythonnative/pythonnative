import json
from pathlib import Path
from typing import List, Optional, Sequence

import pytest

from pythonnative.project import deps
from pythonnative.project.builder import CommandResult, CommandRunner
from pythonnative.project.config import AppConfig


def _config(tmp_path: Path, extra: str = "") -> AppConfig:
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "pythonnative.toml").write_text(
        '[app]\nid = "com.acme.deps"\nname = "deps"\npython_version = "3.13"\n'
        '[requirements]\npackages = ["httpx", "numpy>=2"]\n' + extra,
        encoding="utf-8",
    )
    return AppConfig.load(tmp_path)


class ScriptedRunner(CommandRunner):
    """Returns a canned result per call and records what pip was asked."""

    def __init__(self, results: Sequence[CommandResult]) -> None:
        self.results = list(results)
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
        return self.results.pop(0) if self.results else CommandResult(0, "{}")


# -- Targets -----------------------------------------------------------


def test_ios_targets_cover_device_and_simulator(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    targets = deps.ios_targets(cfg, simulator_arch="arm64")
    assert [(t.sdk, t.arch) for t in targets] == [("iphoneos", "arm64"), ("iphonesimulator", "arm64")]
    assert all(t.python_version == "3.13" and t.os_version == "13.0" for t in targets)
    assert targets[0].slice_name == "app_packages.iphoneos"
    assert targets[0].abi_tag == "cp313"
    assert "iOS device" in targets[0].label and "iOS Simulator" in targets[1].label


def test_ios_targets_use_host_simulator_arch_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "host_simulator_arch", lambda: "x86_64")
    cfg = _config(tmp_path)
    (sim,) = deps.ios_targets(cfg, sdks=("iphonesimulator",))
    assert sim.arch == "x86_64"
    assert sim.platform_tags[0] == "ios_13_0_x86_64_iphonesimulator"


def test_ios_targets_reject_unknown_sdk(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        deps.ios_targets(_config(tmp_path), sdks=("watchos",))


def test_ios_platform_tags_walk_down_to_the_wheel_floor(tmp_path: Path) -> None:
    cfg = _config(tmp_path, '[ios]\ndeployment_target = "14.2"\n')
    (device,) = deps.ios_targets(cfg, sdks=("iphoneos",))
    tags = device.platform_tags
    assert tags[0] == "ios_14_2_arm64_iphoneos"
    assert tags[1] == "ios_14_1_arm64_iphoneos"
    assert "ios_13_0_arm64_iphoneos" in tags
    assert tags[-1] == "ios_12_0_arm64_iphoneos"
    assert "ios_11_9_arm64_iphoneos" not in tags


def test_android_targets_follow_abi_filters_and_min_sdk(tmp_path: Path) -> None:
    cfg = _config(tmp_path, '[android]\nmin_sdk = 26\nabi_filters = ["x86_64", "arm64-v8a"]\n')
    targets = deps.android_targets(cfg)
    assert [t.arch for t in targets] == ["x86_64", "arm64_v8a"]
    assert [t.abi for t in targets] == ["x86_64", "arm64-v8a"]
    assert targets[1].platform_tags[0] == "android_26_arm64_v8a"
    assert targets[1].platform_tags[-1] == f"android_{deps.MIN_ANDROID_WHEEL_API}_arm64_v8a"
    assert targets[1].label == "Android arm64-v8a (API 26+)"
    assert targets[0].index_urls == [deps.CHAQUOPY_INDEX_URL]


def test_targets_for_filters_by_platform(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert {t.platform for t in deps.targets_for(cfg)} == {"ios", "android"}
    assert all(t.platform == "ios" for t in deps.targets_for(cfg, "ios"))
    assert all(t.platform == "android" for t in deps.targets_for(cfg, "android"))


# -- pip arguments -----------------------------------------------------


def test_pip_base_args_select_the_target_not_the_host(tmp_path: Path) -> None:
    cfg = _config(tmp_path, 'extra_index_urls = ["https://wheels.example/simple"]\n')
    (device,) = deps.ios_targets(cfg, sdks=("iphoneos",))
    args = deps.pip_base_args(cfg, device, python="/py/bin/python3.13")

    assert args[:4] == ["/py/bin/python3.13", "-m", "pip", "install"]
    assert "--only-binary=:all:" in args
    assert args[args.index("--python-version") + 1] == "3.13"
    assert args[args.index("--abi") + 1] == "cp313"
    assert args[args.index("--implementation") + 1] == "cp"
    platforms = [args[i + 1] for i, a in enumerate(args) if a == "--platform"]
    assert platforms == device.platform_tags
    indexes = [args[i + 1] for i, a in enumerate(args) if a == "--extra-index-url"]
    assert indexes == [deps.BEEWARE_INDEX_URL, "https://wheels.example/simple"]


def test_report_and_install_args_append_requirements(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (android,) = deps.android_targets(cfg)[:1]
    report = deps.report_args(cfg, android)
    assert report[-2:] == ["httpx", "numpy>=2"]
    assert "--dry-run" in report and "--report" in report and report[report.index("--report") + 1] == "-"

    install = deps.install_args(cfg, android, tmp_path / "dest")
    assert install[install.index("--target") + 1] == str(tmp_path / "dest")
    assert "--dry-run" not in install
    assert install[-2:] == ["httpx", "numpy>=2"]


# -- Parsing -----------------------------------------------------------


_REPORT = json.dumps(
    {
        "install": [
            {
                "metadata": {"name": "numpy", "version": "2.2.1"},
                "download_info": {
                    "url": "https://pypi.anaconda.org/beeware/simple/numpy/numpy-2.2.1-cp313-cp313-ios_13_0_arm64_iphoneos.whl"
                },
            },
            {
                "metadata": {"name": "httpx", "version": "0.27.0"},
                "download_info": {"url": "https://files.pythonhosted.org/packages/x/httpx-0.27.0-py3-none-any.whl"},
            },
        ]
    }
)


def test_parse_report_classifies_wheels(tmp_path: Path) -> None:
    (device,) = deps.ios_targets(_config(tmp_path), sdks=("iphoneos",))
    res = deps.parse_report(_REPORT, device)
    assert res.ok
    assert [p.name for p in res.packages] == ["httpx", "numpy"]
    httpx, numpy = res.packages
    assert httpx.is_pure and httpx.platform_tag == "any" and httpx.source_label == "PyPI"
    assert not numpy.is_pure
    assert numpy.platform_tag == "ios_13_0_arm64_iphoneos"
    assert numpy.source_label == "BeeWare"
    assert res.binary_packages == [numpy]
    as_dict = res.to_dict()
    assert as_dict["ok"] is True and as_dict["packages"][1]["source"] == "BeeWare"


def test_parse_report_handles_empty_document(tmp_path: Path) -> None:
    (device,) = deps.ios_targets(_config(tmp_path), sdks=("iphoneos",))
    assert deps.parse_report("", device).packages == []


def test_parse_failure_extracts_missing_requirements() -> None:
    stderr = (
        "Looking in indexes: https://pypi.org/simple\n"
        "ERROR: Could not find a version that satisfies the requirement pandas (from versions: none)\n"
        "ERROR: No matching distribution found for pandas\n"
    )
    summary, missing = deps.parse_failure(stderr)
    assert missing == ["pandas"]
    assert summary.startswith("ERROR: Could not find a version")
    assert "Looking in indexes" not in summary


def test_parse_failure_without_error_lines_uses_last_line() -> None:
    summary, missing = deps.parse_failure("something odd happened\nlast line")
    assert summary == "last line" and missing == []


# -- resolve / install -------------------------------------------------


def test_resolve_returns_packages_on_success(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (device,) = deps.ios_targets(cfg, sdks=("iphoneos",))
    runner = ScriptedRunner([CommandResult(0, _REPORT)])
    res = deps.resolve(cfg, device, runner=runner)
    assert res.ok and len(res.packages) == 2
    assert runner.commands[0][-2:] == ["httpx", "numpy>=2"]


def test_resolve_reports_failure_instead_of_raising(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (device,) = deps.ios_targets(cfg, sdks=("iphoneos",))
    runner = ScriptedRunner([CommandResult(1, "", "ERROR: No matching distribution found for numpy>=2")])
    res = deps.resolve(cfg, device, runner=runner)
    assert not res.ok
    assert res.missing == ["numpy>=2"]
    assert "No matching distribution" in (res.error or "")


def test_resolve_skips_pip_without_requirements(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "pythonnative.toml").write_text('[app]\nid = "com.acme.none"\nname = "none"\n', encoding="utf-8")
    cfg = AppConfig.load(tmp_path)
    runner = ScriptedRunner([])
    for target in deps.targets_for(cfg):
        assert deps.resolve(cfg, target, runner=runner).ok
    assert runner.commands == []


def test_resolve_all_resolves_every_target(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    targets = deps.targets_for(cfg)
    runner = ScriptedRunner([CommandResult(0, _REPORT)] * len(targets))
    results = deps.resolve_all(cfg, targets, runner=runner, detect_downgrades=False)
    assert [r.target for r in results] == targets
    assert len(runner.commands) == len(targets)


_REFERENCE = json.dumps(
    {
        "install": [
            {"metadata": {"name": "numpy", "version": "2.2.1"}},
            {"metadata": {"name": "httpx", "version": "0.28.1"}},
        ]
    }
)


def test_resolve_all_marks_downgrades_against_an_unconstrained_resolution(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    targets = deps.ios_targets(cfg, sdks=("iphoneos",))
    runner = ScriptedRunner([CommandResult(0, _REPORT), CommandResult(0, _REFERENCE)])
    (res,) = deps.resolve_all(cfg, targets, runner=runner)

    # One resolution per target plus one reference call with no platform flags.
    assert len(runner.commands) == 2
    reference_cmd = runner.commands[1]
    assert "--platform" not in reference_cmd and "--only-binary=:all:" not in reference_cmd
    assert reference_cmd[-2:] == ["httpx", "numpy>=2"]

    httpx, numpy = res.packages
    assert httpx.downgraded and httpx.latest == "0.28.1"
    assert not numpy.downgraded and numpy.latest == ""
    assert res.downgraded_packages == [httpx]
    assert res.to_dict()["packages"][0]["latest"] == "0.28.1"


def test_resolve_all_skips_reference_when_nothing_resolved(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    targets = deps.ios_targets(cfg, sdks=("iphoneos",))
    runner = ScriptedRunner([CommandResult(1, "", "ERROR: No matching distribution found for numpy>=2")])
    (res,) = deps.resolve_all(cfg, targets, runner=runner)
    assert not res.ok
    assert len(runner.commands) == 1


def test_resolve_reference_returns_none_on_failure(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert deps.resolve_reference(cfg, runner=ScriptedRunner([CommandResult(1, "", "boom")])) is None
    assert deps.resolve_reference(cfg, runner=ScriptedRunner([CommandResult(0, "not json")])) is None
    assert deps.resolve_reference(cfg, runner=ScriptedRunner([CommandResult(0, _REFERENCE)])) == {
        "numpy": "2.2.1",
        "httpx": "0.28.1",
    }


def test_mark_downgrades_compares_release_numbers_only(tmp_path: Path) -> None:
    (device,) = deps.ios_targets(_config(tmp_path), sdks=("iphoneos",))
    packages = [
        deps.ResolvedPackage("Pydantic", "1.10.26", "pydantic-1.10.26-py3-none-any.whl"),
        deps.ResolvedPackage("numpy", "2.5.2", "numpy-2.5.2-cp313-cp313-ios_13_0_arm64_iphoneos.whl"),
        deps.ResolvedPackage("MarkupSafe", "3.0.3", "MarkupSafe-3.0.3-py3-none-any.whl"),
    ]
    res = deps.Resolution(target=device, packages=packages)
    deps.mark_downgrades([res], {"pydantic": "2.12.0", "numpy": "2.5.2.post1", "markupsafe": "3.0.3"})
    assert [pkg.latest for pkg in packages] == ["2.12.0", "", ""]


def test_install_raises_dependency_error_with_guidance(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (sim,) = deps.ios_targets(cfg, sdks=("iphonesimulator",), simulator_arch="arm64")
    runner = ScriptedRunner([CommandResult(1, "", "ERROR: No matching distribution found for numpy>=2")])
    with pytest.raises(deps.DependencyError) as info:
        deps.install(cfg, sim, tmp_path / "slice", runner=runner)
    message = str(info.value)
    assert "numpy>=2" in message
    assert "iOS Simulator" in message
    assert "pn deps" in message
    assert deps.BEEWARE_INDEX_URL in message
    assert (tmp_path / "slice").is_dir()


def test_install_android_guidance_mentions_chaquopy(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (android,) = deps.android_targets(cfg)[:1]
    message = deps.explain_failure(android, "ERROR: boom", ["pandas"])
    assert "pandas" in message and deps.CHAQUOPY_INDEX_URL in message and "PEP 738" in message


# -- Report formatting -------------------------------------------------


def test_format_report_lists_wheels_and_failures(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    device, sim = deps.ios_targets(cfg, simulator_arch="arm64")
    (android,) = deps.android_targets(cfg)[:1]
    ok = deps.parse_report(_REPORT, device)
    failed = deps.Resolution(
        target=sim, error="ERROR: No matching distribution found for numpy>=2", missing=["numpy>=2"]
    )
    preview = deps.parse_report(_REPORT, android)

    text = deps.format_report([ok, failed, preview], requirements=cfg.requirements)
    assert "[ok] httpx 0.27.0" in text and "pure Python" in text
    assert "binary wheel  ios_13_0_arm64_iphoneos  (BeeWare)" in text
    assert "[x] ERROR: No matching distribution found for numpy>=2" in text
    assert "(preview; Chaquopy resolves again inside the Gradle build)" in text
    assert "1 of 3 targets cannot be satisfied" in text
    assert "[!!]" not in text


def test_format_report_flags_downgrades(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (device,) = deps.ios_targets(cfg, sdks=("iphoneos",))
    res = deps.parse_report(_REPORT, device)
    deps.mark_downgrades([res], {"httpx": "0.28.1"})
    text = deps.format_report([res], requirements=cfg.requirements)
    assert "[!!] httpx 0.27.0" in text
    assert "older than the desktop resolution (0.28.1)" in text
    assert "Older release selected for: httpx" in text
    assert text.endswith("All 1 targets resolved.")


def test_format_report_all_ok(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (device,) = deps.ios_targets(cfg, sdks=("iphoneos",))
    text = deps.format_report([deps.parse_report(_REPORT, device)], requirements=cfg.requirements)
    assert text.endswith("All 1 targets resolved.")


def test_format_report_without_requirements() -> None:
    assert "nothing to resolve" in deps.format_report([], requirements=[])
