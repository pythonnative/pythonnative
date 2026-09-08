"""Reject incomplete or incorrectly tagged release artifacts before publishing."""

from __future__ import annotations

import argparse
import re
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.tags import parse_tag
from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.version import Version

PYTHONS = {"cp313", "cp314"}
PLATFORMS = {"linux_x86_64", "linux_aarch64", "macos_x86_64", "macos_arm64", "win_amd64"}
PACKAGE_FILES = {
    "pythonnative/py.typed",
    "pythonnative/native/yoga/python.cpp",
    "pythonnative/native/yoga/yoga/Yoga.h",
    "pythonnative/native/yoga/yoga/YGNode.cpp",
    "pythonnative/native/ios/Package.swift",
    "pythonnative/templates/android_template/gradlew",
    "pythonnative/devserver/static/yoga/binaries/yoga-wasm-base64-esm.js",
}


def platform_family(platform: str) -> str:
    """Map portable wheel tags to the host targets in the release matrix."""
    match = re.fullmatch(r"manylinux_2_(\d+)_(x86_64|aarch64)", platform)
    if match and int(match[1]) <= 28:
        return f"linux_{match[2]}"
    match = re.fullmatch(r"macosx_(\d+)_(\d+)_(x86_64|arm64)", platform)
    if match and (int(match[1]), int(match[2])) <= (11, 0):
        return f"macos_{match[3]}"
    if platform == "win_amd64":
        return platform
    raise ValueError(f"Unsupported release platform tag: {platform}")


def check_metadata(data: bytes, version: Version) -> None:
    """Require archive metadata to agree with the selected release."""
    metadata = BytesParser().parsebytes(data)
    if canonicalize_name(metadata.get("Name", "")) != "pythonnative":
        raise ValueError("Distribution metadata has the wrong project name")
    if metadata.get("Version") != str(version):
        raise ValueError("Distribution metadata has the wrong version")


def check_distributions(directory: Path, expected_version: str) -> None:
    """Validate the full wheel matrix and its single source distribution."""
    version = Version(expected_version)
    expected = {(python, platform) for python in PYTHONS for platform in PLATFORMS}
    seen: set[tuple[str, str]] = set()
    sdists = 0
    for path in sorted(directory.iterdir()):
        if path.name.endswith(".whl"):
            name, wheel_version, build, tags = parse_wheel_filename(path.name)
            if name != "pythonnative" or wheel_version != version or build:
                raise ValueError(f"Unexpected wheel name/version/build: {path.name}")
            targets = set()
            for tag in tags:
                if tag.interpreter not in PYTHONS or tag.abi != tag.interpreter:
                    raise ValueError(f"Unsupported Python/ABI tag: {tag}")
                targets.add((tag.interpreter, platform_family(tag.platform)))
            if len(targets) != 1 or targets & seen:
                raise ValueError(f"Duplicate or ambiguous wheel target: {path.name}")
            seen.update(targets)
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                metadata_path = f"pythonnative-{version}.dist-info/METADATA"
                check_metadata(archive.read(metadata_path), version)
                wheel = BytesParser().parsebytes(archive.read(metadata_path.replace("METADATA", "WHEEL")))
                archive_tags = set().union(*(parse_tag(tag) for tag in wheel.get_all("Tag", [])))
                if wheel.get("Root-Is-Purelib") != "false" or archive_tags != tags:
                    raise ValueError(f"Wheel metadata disagrees with binary platform tags: {path.name}")
                suffix = ".pyd" if next(iter(targets))[1] == "win_amd64" else ".so"
                if not any(n.startswith("pythonnative/_yoga.") and n.endswith(suffix) for n in names):
                    raise ValueError(f"Missing compiled Yoga extension: {path.name}")
                missing = PACKAGE_FILES - names
                if missing:
                    raise ValueError(f"Missing package resources in {path.name}: {sorted(missing)}")
        elif path.name.endswith(".tar.gz"):
            name, sdist_version = parse_sdist_filename(path.name)
            if name != "pythonnative" or sdist_version != version:
                raise ValueError(f"Unexpected source distribution: {path.name}")
            sdists += 1
            with tarfile.open(path) as archive:
                prefix = f"pythonnative-{version}/"
                names = set(archive.getnames())
                required = {prefix + "src/" + name for name in PACKAGE_FILES}
                required |= {prefix + "setup.py", prefix + "tests/test_layout.py"}
                if missing := required - names:
                    raise ValueError(f"Incomplete source distribution: {sorted(missing)}")
                metadata_file = archive.extractfile(prefix + "PKG-INFO")
                project_file = archive.extractfile(prefix + "pyproject.toml")
                if metadata_file is None or project_file is None:
                    raise ValueError("Source distribution is missing package metadata")
                check_metadata(metadata_file.read(), version)
                if tomllib.loads(project_file.read().decode())["project"]["version"] != str(version):
                    raise ValueError("Source version disagrees with release version")
        else:
            raise ValueError(f"Unexpected release artifact: {path.name}")
    if sdists != 1 or seen != expected:
        raise ValueError(f"Incomplete release: {sdists} sdists; missing wheel targets: {sorted(expected - seen)}")


def main() -> None:
    """Validate release artifacts selected by the workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    check_distributions(args.directory, args.version)
    print(f"Validated {len(PYTHONS) * len(PLATFORMS)} wheels and one sdist for {args.version}")


if __name__ == "__main__":
    main()
