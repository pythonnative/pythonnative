"""Locks select exact target wheels and reject silent changes."""

from dataclasses import replace
from pathlib import Path

import pytest

from pythonnative.project import deps, lockfile
from pythonnative.project.config import AppConfig


def config(tmp_path: Path) -> AppConfig:
    (tmp_path / "app").mkdir()
    (tmp_path / "pythonnative.toml").write_text(
        '[app]\nid="dev.example.lock"\nname="lock"\npython_version="3.13"\n'
        '[requirements]\npackages=["example"]\n[android]\nabi_filters=["x86_64", "arm64-v8a"]\n'
    )
    return AppConfig.load(tmp_path)


def package(digest: str = "a" * 64, version: str = "1.2") -> deps.ResolvedPackage:
    return deps.ResolvedPackage("example", version, "example.whl", "https://example.test/example.whl", digest)


def test_lock_merges_targets_and_requires_every_selected_hash(tmp_path: Path) -> None:
    app = config(tmp_path)
    targets = deps.android_targets(app)
    lockfile.write(app, [deps.Resolution(target=targets[0], packages=[package()])])
    with pytest.raises(deps.DependencyError, match="has no"):
        lockfile.requirements(app, targets)
    lockfile.write(app, [deps.Resolution(target=targets[1], packages=[package("b" * 64)])])
    pinned = lockfile.requirements(app, targets)
    assert "example==1.2" in pinned
    assert "--hash=sha256:" + "a" * 64 in pinned
    assert "--hash=sha256:" + "b" * 64 in pinned
    with pytest.raises(deps.DependencyError, match="doesn't match"):
        lockfile.read(replace(app, requirements=["example>=2"]))


def test_lock_rejects_missing_hashes_and_differing_abi_versions(tmp_path: Path) -> None:
    app = config(tmp_path)
    targets = deps.android_targets(app)
    with pytest.raises(deps.DependencyError, match="SHA-256"):
        lockfile.write(app, [deps.Resolution(target=targets[0], packages=[package("")])])
    lockfile.write(
        app,
        [
            deps.Resolution(target=targets[0], packages=[package()]),
            deps.Resolution(target=targets[1], packages=[package(version="2.0")]),
        ],
    )
    with pytest.raises(deps.DependencyError, match="different versions"):
        lockfile.requirements(app, targets)
