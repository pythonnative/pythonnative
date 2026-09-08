"""Unit tests for the Platform module."""

from __future__ import annotations

from typing import Generator

import pytest

import pythonnative as pn
from pythonnative.platform import Platform, _set_platform_for_test, get_platform


@pytest.fixture(autouse=True)
def _reset_platform() -> Generator[None, None, None]:
    """Reset Platform after each test so suite order doesn't matter."""
    yield
    _set_platform_for_test(None)


def test_default_platform_is_test() -> None:
    assert Platform.OS == "test"
    assert Platform.is_test is True
    assert Platform.is_ios is False
    assert Platform.is_android is False


def test_get_platform_matches_os() -> None:
    assert get_platform() == Platform.OS


def test_get_platform_exported_from_package() -> None:
    assert pn.get_platform() == pn.Platform.OS


def test_version_string_present() -> None:
    assert isinstance(Platform.Version, str)
    assert len(Platform.Version) > 0


def test_select_picks_current_platform() -> None:
    _set_platform_for_test("ios")
    assert Platform.select({"ios": "A", "android": "B"}) == "A"
    _set_platform_for_test("android")
    assert Platform.select({"ios": "A", "android": "B"}) == "B"


def test_select_falls_back_to_native() -> None:
    _set_platform_for_test("ios")
    assert Platform.select({"native": "X", "default": "Y"}) == "X"
    _set_platform_for_test("test")
    # 'test' doesn't match 'native', so falls back to 'default'.
    assert Platform.select({"native": "X", "default": "Y"}) == "Y"


def test_select_default_then_explicit() -> None:
    _set_platform_for_test("test")
    assert Platform.select({"default": "D"}) == "D"
    assert Platform.select({}, default="E") == "E"
    assert Platform.select({}) is None


def test_set_platform_for_test_toggles_flags() -> None:
    _set_platform_for_test("ios")
    assert Platform.is_ios is True
    assert Platform.is_android is False
    _set_platform_for_test("android")
    assert Platform.is_ios is False
    assert Platform.is_android is True
