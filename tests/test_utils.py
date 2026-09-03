"""Tests for pythonnative.utils platform detection."""

import os
import sys

import pytest

from pythonnative.utils import IS_ANDROID, IS_IOS, _detect_ios


class TestIosDetection:
    """``_detect_ios()`` should key off explicit signals only, not on the
    presence of optional packages.
    """

    def test_detects_via_pn_platform_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "ios")
        assert _detect_ios() is True

    def test_other_pn_platform_values_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "desktop")
        monkeypatch.delenv("HOME", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        assert _detect_ios() is False

    def test_detects_via_sys_platform_ios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        monkeypatch.setattr(sys, "platform", "ios")
        assert _detect_ios() is True

    def test_core_simulator_home_alone_is_not_ios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A macOS process whose HOME happens to point into a Simulator
        # container (e.g. a host tool spawned by simctl) is still macOS;
        # the embedded runtime reports sys.platform == "ios" itself.
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setenv(
            "HOME",
            "/Users/x/Library/Developer/CoreSimulator/Devices/ABCD/data",
        )
        assert _detect_ios() is False

    def test_plain_macos_is_not_ios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setenv("HOME", "/Users/owen")
        assert _detect_ios() is False

    def test_plain_linux_is_not_ios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("HOME", "/home/runner")
        assert _detect_ios() is False


class TestPlatformFlagsConsistency:
    def test_both_flags_are_bools(self) -> None:
        assert isinstance(IS_ANDROID, bool)
        assert isinstance(IS_IOS, bool)

    def test_flags_are_mutually_exclusive(self) -> None:
        # A single Python process is never simultaneously Android and iOS.
        assert not (IS_ANDROID and IS_IOS)

    def test_ci_environment_is_neither(self) -> None:
        """The test suite runs on Linux/macOS hosts, so both flags are False."""
        # This is more of a smoke check of the import-time detection: if
        # this ever starts being True on CI, someone has accidentally made
        # platform detection overeager on non-device hosts.
        if os.environ.get("PN_PLATFORM") == "ios":
            pytest.skip("Running under PN_PLATFORM=ios; flags correctly reflect that.")
        assert IS_ANDROID is False
        assert IS_IOS is False
