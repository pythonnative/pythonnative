"""Repository test configuration.

Per-test framework isolation (closing the headless loop, clearing the
event registry, the default query client, and recorded warnings) and the
``pn_clock`` fixture come from ``pythonnative.testing.pytest_plugin``,
which pytest loads through the package's ``pytest11`` entry point. This
file checks that the installed package carries that entry point and keeps
the dev server's per-user token out of the real home directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def _dev_token_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("pn-token")


@pytest.fixture(autouse=True)
def _isolated_dev_token(_dev_token_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point ``PN_DEV_TOKEN_FILE`` at a temporary file so tests never touch ``~/.pythonnative``."""
    monkeypatch.setenv("PN_DEV_TOKEN_FILE", str(_dev_token_dir / "dev-token"))
    monkeypatch.delenv("PN_DEV_TOKEN", raising=False)


def pytest_configure(config: pytest.Config) -> None:
    if not config.pluginmanager.hasplugin("pythonnative"):
        raise pytest.UsageError(
            "The pythonnative pytest plugin is not registered; the installed package predates its "
            "pytest11 entry point. Run `uv sync --group dev` (or `uv pip install -e .`) and retry."
        )
