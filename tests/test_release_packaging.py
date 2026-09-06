"""Distribution validation and partial-upload recovery regressions."""

import importlib.util
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_script("check-distributions")
assets = load_script("release-assets")
VERSION = "0.40.0"
METADATA = f"Metadata-Version: 2.4\nName: pythonnative\nVersion: {VERSION}\n"
PLATFORMS = [
    "manylinux_2_28_x86_64",
    "manylinux_2_28_aarch64",
    "macosx_11_0_x86_64",
    "macosx_11_0_arm64",
    "win_amd64",
]


def wheel_files(python: str, platform: str) -> dict[str, bytes]:
    suffix = "pyd" if platform == "win_amd64" else "so"
    return {
        **dict.fromkeys(checker.PACKAGE_FILES, b"resource"),
        f"pythonnative/_yoga.{python}.{suffix}": b"native library",
        f"pythonnative-{VERSION}.dist-info/METADATA": METADATA.encode(),
        f"pythonnative-{VERSION}.dist-info/WHEEL": (
            f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: {python}-{python}-{platform}\n".encode()
        ),
    }


def write_wheel(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


@pytest.fixture
def distributions(tmp_path: Path) -> Path:
    for python in ("cp313", "cp314"):
        for platform in PLATFORMS:
            write_wheel(
                tmp_path / f"pythonnative-{VERSION}-{python}-{python}-{platform}.whl",
                wheel_files(python, platform),
            )
    source_files = {
        **dict.fromkeys(("src/" + name for name in checker.PACKAGE_FILES), b"source"),
        "setup.py": b"build configuration",
        "tests/test_layout.py": b"layout tests",
        "PKG-INFO": METADATA.encode(),
        "pyproject.toml": f'[project]\nversion = "{VERSION}"\n'.encode(),
    }
    with tarfile.open(tmp_path / f"pythonnative-{VERSION}.tar.gz", "w:gz") as archive:
        for name, data in source_files.items():
            info = tarfile.TarInfo(f"pythonnative-{VERSION}/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return tmp_path


def test_complete_distribution_matrix(distributions: Path) -> None:
    checker.check_distributions(distributions, VERSION)


def test_original_linux_wheel_rejection(distributions: Path) -> None:
    path = next(distributions.glob("*cp314-cp314-manylinux_2_28_x86_64.whl"))
    path.rename(path.with_name(path.name.replace("manylinux_2_28", "linux")))
    with pytest.raises(ValueError, match="Unsupported release platform tag: linux_x86_64"):
        checker.check_distributions(distributions, VERSION)


@pytest.mark.parametrize("pattern", ["*cp313-cp313-win_amd64.whl", "*.tar.gz"])
def test_missing_artifact_blocks_publish(distributions: Path, pattern: str) -> None:
    next(distributions.glob(pattern)).unlink()
    with pytest.raises(ValueError, match="Incomplete release"):
        checker.check_distributions(distributions, VERSION)


@pytest.mark.parametrize("damage", ["version", "tags", "pure", "extension", "resource"])
def test_bad_wheel_contents_block_publish(distributions: Path, damage: str) -> None:
    path = next(distributions.glob("*cp313-cp313-win_amd64.whl"))
    files = wheel_files("cp313", "win_amd64")
    metadata = f"pythonnative-{VERSION}.dist-info/METADATA"
    wheel = f"pythonnative-{VERSION}.dist-info/WHEEL"
    if damage == "version":
        files[metadata] = files[metadata].replace(b"0.40.0", b"0.39.0")
    elif damage == "tags":
        files[wheel] = files[wheel].replace(b"win_amd64", b"linux_x86_64")
    elif damage == "pure":
        files[wheel] = files[wheel].replace(b"false", b"true")
    elif damage == "extension":
        del files["pythonnative/_yoga.cp313.pyd"]
    else:
        del files["pythonnative/native/yoga/yoga/Yoga.h"]
    write_wheel(path, files)
    with pytest.raises(ValueError):
        checker.check_distributions(distributions, VERSION)


@pytest.mark.parametrize("platform", ["linux_x86_64", "any", "manylinux_2_39_x86_64", "macosx_15_0_arm64"])
def test_incompatible_platforms(platform: str) -> None:
    with pytest.raises(ValueError, match="Unsupported release platform"):
        checker.platform_family(platform)


def test_recovery_reuses_original_bytes_after_partial_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "pythonnative-0.40.0-cp313-cp313-win_amd64.whl"
    second = tmp_path / "pythonnative-0.40.0.tar.gz"
    first.write_bytes(b"original wheel")
    second.write_bytes(b"original source")
    remote: dict[str, bytes] = {}
    fail_upload = True

    def gh(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command[:2] == ["gh", "release"]
        action = command[2]
        if action == "view":
            return subprocess.CompletedProcess(command, 0, json.dumps({"assets": [{"name": n} for n in remote]}))
        if action == "upload":
            path = Path(command[4])
            if fail_upload and path == second:
                raise subprocess.CalledProcessError(1, command)
            assert path.name not in remote, "Recovery must never overwrite a published asset"
            remote[path.name] = path.read_bytes()
        elif action == "download":
            name = command[command.index("--pattern") + 1]
            (Path(command[command.index("--dir") + 1]) / name).write_bytes(remote[name])
        else:
            pytest.fail(f"Unexpected gh command: {command}")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(assets.subprocess, "run", gh)
    with pytest.raises(subprocess.CalledProcessError):
        assets.sync_assets("v0.40.0", tmp_path)
    assert remote == {first.name: b"original wheel"}
    first.write_bytes(b"rebuilt wheel with a different timestamp")
    fail_upload = False
    assets.sync_assets("v0.40.0", tmp_path)
    assert first.read_bytes() == b"original wheel"
    assert remote[second.name] == b"original source"
    assets.sync_assets("v0.40.0", tmp_path)
    assert first.read_bytes() == b"original wheel"
