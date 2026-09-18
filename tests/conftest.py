"""Repository test configuration.

Per-test framework isolation (closing the headless loop, clearing the
event registry, the default query client, and recorded warnings) and the
``pn_clock`` fixture come from ``pythonnative.testing.pytest_plugin``,
which pytest loads through the package's ``pytest11`` entry point. This
file only checks that the installed package carries that entry point.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    if not config.pluginmanager.hasplugin("pythonnative"):
        raise pytest.UsageError(
            "The pythonnative pytest plugin is not registered; the installed package predates its "
            "pytest11 entry point. Run `uv sync --group dev` (or `uv pip install -e .`) and retry."
        )
