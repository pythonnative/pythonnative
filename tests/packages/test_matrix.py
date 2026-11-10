"""PyPI package compatibility matrix.

Resolves every package in ``matrix.toml`` for every device target with
the real pip (network required) and checks the outcome against the
manifest's expectations. Skipped unless ``PN_PACKAGE_MATRIX=1`` is set,
because it talks to PyPI, BeeWare's index, and Chaquopy's index and
takes a minute or two; ``.github/workflows/packages.yml`` runs it on a
schedule and whenever the resolver or the manifest changes.

Run locally:

    PN_PACKAGE_MATRIX=1 uv run pytest tests/packages -q

The manifest-shape tests at the bottom always run.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pytest

from pythonnative.project import deps
from pythonnative.project.builder import CommandResult, CommandRunner
from pythonnative.project.config import AppConfig

MATRIX_PATH = Path(__file__).with_name("matrix.toml")
RUN_MATRIX = os.environ.get("PN_PACKAGE_MATRIX") == "1"


def load_matrix() -> dict:
    """Parse ``matrix.toml``."""
    with open(MATRIX_PATH, "rb") as handle:
        return tomllib.load(handle)


MATRIX = load_matrix()
PACKAGES: List[dict] = MATRIX["package"]


class _PipRunner(CommandRunner):
    """The real thing: runs pip and captures its output."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture: bool = False,
    ) -> CommandResult:
        proc = subprocess.run(list(args), cwd=cwd, env=env, capture_output=True, text=True)
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def _config(tmp_path: Path, requirement: str) -> AppConfig:
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "pythonnative.toml").write_text(
        f'[app]\nid = "com.pythonnative.matrix"\nname = "matrix"\npython_version = "{MATRIX["python_version"]}"\n'
        f'[requirements]\npackages = ["{requirement}"]\n',
        encoding="utf-8",
    )
    return AppConfig.load(tmp_path)


def _targets(config: AppConfig) -> List[deps.Target]:
    # Both Simulator architectures: a developer on an Intel Mac and one
    # on Apple silicon must both be able to `pn run ios`.
    return [
        *deps.ios_targets(config, sdks=("iphoneos",)),
        *deps.ios_targets(config, sdks=("iphonesimulator",), simulator_arch="arm64"),
        *deps.ios_targets(config, sdks=("iphonesimulator",), simulator_arch="x86_64"),
        *deps.android_targets(config),
    ]


def _expected(entry: dict, target: deps.Target) -> bool:
    return bool(entry[target.platform])


_ids = [entry["name"] for entry in PACKAGES]


@pytest.mark.network
@pytest.mark.skipif(not RUN_MATRIX, reason="set PN_PACKAGE_MATRIX=1 to resolve the matrix against live indexes")
@pytest.mark.parametrize("entry", PACKAGES, ids=_ids)
def test_package_resolves_as_expected(entry: dict, tmp_path: Path) -> None:
    config = _config(tmp_path, entry["name"])
    runner = _PipRunner()
    resolutions = deps.resolve_all(config, _targets(config), runner=runner)
    problems: List[str] = []
    for res in resolutions:
        expected = _expected(entry, res.target)
        if res.ok != expected:
            state = "resolved" if res.ok else f"failed ({res.error})"
            problems.append(f"{res.target.label}: expected {'success' if expected else 'failure'}, {state}")
            continue
        if not res.ok:
            continue
        expect_downgrade = res.target.platform in entry.get("downgrade", [])
        if entry["kind"] == "pure" and res.binary_packages and not expect_downgrade:
            names = ", ".join(pkg.filename for pkg in res.binary_packages)
            problems.append(f"{res.target.label}: declared pure but pulled binary wheels: {names}")
        if entry["kind"] == "binary" and not res.binary_packages:
            problems.append(f"{res.target.label}: declared binary but every wheel was pure")
        # A listed downgrade must still be there (when the index catches
        # up, the manifest and the guide should say so). The reverse is
        # not asserted: indexes lag PyPI by a release here and there all
        # the time, and that churn belongs in `pn deps` output and the
        # generated table, not in a failing test.
        top = _top_level(res, entry["name"])
        if top is None:
            problems.append(f"{res.target.label}: {entry['name']} missing from pip's report")
        elif expect_downgrade and not top.downgraded:
            problems.append(f"{res.target.label}: expected an older release to be selected, got {top.version}")
    assert not problems, "\n".join(problems)


def _top_level(res: deps.Resolution, requirement: str) -> Optional[deps.ResolvedPackage]:
    name = deps._canonical(re.split(r"[<>=!~\[;]", requirement, maxsplit=1)[0].strip())
    return next((pkg for pkg in res.packages if deps._canonical(pkg.name) == name), None)


# -- Manifest shape (always runs) ---------------------------------------


def test_matrix_python_version_is_supported() -> None:
    from pythonnative.project.config import SUPPORTED_PYTHON_VERSIONS

    assert MATRIX["python_version"] in SUPPORTED_PYTHON_VERSIONS


def test_matrix_entries_are_well_formed() -> None:
    seen: Dict[str, int] = {}
    for entry in PACKAGES:
        assert set(entry) <= {"name", "kind", "ios", "android", "note", "downgrade"}, entry
        assert entry["kind"] in ("pure", "binary"), entry
        assert isinstance(entry["ios"], bool) and isinstance(entry["android"], bool), entry
        assert set(entry.get("downgrade", [])) <= {"ios", "android"}, entry
        assert (
            entry["kind"] == "binary" or entry["ios"] and entry["android"]
        ), f"{entry['name']}: a pure-Python package resolves everywhere; if it does not, it is not pure"
        seen[entry["name"]] = seen.get(entry["name"], 0) + 1
    duplicates = [name for name, count in seen.items() if count > 1]
    assert not duplicates, duplicates


def test_matrix_covers_the_e2e_suite_requirements() -> None:
    """The packages exercised on device in CI must be in the matrix too."""
    e2e = Path(__file__).resolve().parents[2] / "examples" / "e2e-suite" / "pythonnative.toml"
    with open(e2e, "rb") as handle:
        required = tomllib.load(handle)["requirements"]["packages"]
    names = {entry["name"] for entry in PACKAGES}
    assert set(required) <= names, set(required) - names
