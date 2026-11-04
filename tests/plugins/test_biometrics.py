"""Tests for the ``biometrics`` capability's facade and manifest."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pythonnative
from pythonnative.biometrics import Biometrics
from pythonnative.project.plugins import load_plugin


def test_manifest_loads_and_requires_its_permission() -> None:
    plugin = load_plugin(Path(pythonnative.__file__).parent / "biometrics" / "native")
    assert plugin.requires_permissions == ("face_id",)
    assert plugin.maven_dependencies == ("androidx.biometric:biometric:1.1.0",)


def test_fallback_answers_no() -> None:
    assert Biometrics.is_available() is False
    assert asyncio.run(Biometrics.authenticate("Unlock")) is False
