"""Tests for pythonnative.utils platform detection."""

import os
import sys

import pytest

from pythonnative import utils
from pythonnative.utils import IS_ANDROID, IS_DESKTOP, IS_IOS, _detect_desktop, _detect_ios


class TestIosDetection:
    """``_detect_ios()`` should key off explicit signals only, not on the
    presence of optional packages.
    """

    def test_detects_via_pn_platform_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "ios")
        assert _detect_ios() is True

    def test_other_pn_platform_values_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "web")
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


class TestDesktopDetection:
    """``_detect_desktop()`` keys off ``PN_PLATFORM=desktop`` and nothing else.

    Unlike Android and iOS there is no host-level signal to fall back on: the
    desktop backend only ever runs because ``pn preview`` asked for it.
    """

    def test_detects_via_pn_platform_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "desktop")
        assert _detect_desktop() is True

    def test_unset_pn_platform_is_not_desktop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        assert _detect_desktop() is False

    def test_empty_pn_platform_is_not_desktop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "")
        assert _detect_desktop() is False

    def test_other_pn_platform_values_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "ios")
        assert _detect_desktop() is False

    def test_host_platform_alone_is_not_desktop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running on a laptop is not enough; only the explicit env var counts."""
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        assert _detect_desktop() is False


def _redetect(
    monkeypatch: pytest.MonkeyPatch,
    *,
    android: bool,
    ios: bool,
    desktop: bool,
) -> None:
    """Re-run platform detection with each individual detector forced.

    ``_ensure_platform_detection()`` only computes a flag whose global is still
    ``None``, and all three were filled in at import time, so the caches are
    cleared first. ``monkeypatch`` restores both the caches and the real
    detectors when the test ends.
    """
    monkeypatch.setattr(utils, "_is_android", None)
    monkeypatch.setattr(utils, "_is_ios", None)
    monkeypatch.setattr(utils, "_is_desktop", None)
    monkeypatch.setattr(utils, "_detect_android", lambda: android)
    monkeypatch.setattr(utils, "_detect_ios", lambda: ios)
    monkeypatch.setattr(utils, "_detect_desktop", lambda: desktop)
    utils._ensure_platform_detection()


class TestPlatformFlagPrecedence:
    """Android beats iOS beats desktop, so at most one flag is ever ``True``."""

    def test_desktop_wins_when_no_device_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=False, ios=False, desktop=True)
        assert utils._get_is_desktop() is True
        assert utils._get_is_android() is False
        assert utils._get_is_ios() is False

    def test_android_suppresses_desktop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stale ``PN_PLATFORM=desktop`` must not fire on an Android device."""
        _redetect(monkeypatch, android=True, ios=False, desktop=True)
        assert utils._get_is_android() is True
        assert utils._get_is_desktop() is False

    def test_ios_suppresses_desktop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=False, ios=True, desktop=True)
        assert utils._get_is_ios() is True
        assert utils._get_is_desktop() is False

    def test_android_suppresses_ios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=True, ios=True, desktop=False)
        assert utils._get_is_android() is True
        assert utils._get_is_ios() is False

    def test_no_signal_leaves_every_flag_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=False, ios=False, desktop=False)
        assert utils._get_is_android() is False
        assert utils._get_is_ios() is False
        assert utils._get_is_desktop() is False

    @pytest.mark.parametrize("android", [False, True])
    @pytest.mark.parametrize("ios", [False, True])
    @pytest.mark.parametrize("desktop", [False, True])
    def test_at_most_one_flag_is_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
        android: bool,
        ios: bool,
        desktop: bool,
    ) -> None:
        """No combination of raw signals can light up two flags at once."""
        _redetect(monkeypatch, android=android, ios=ios, desktop=desktop)
        flags = [utils._get_is_android(), utils._get_is_ios(), utils._get_is_desktop()]
        assert sum(flags) <= 1


class TestPlatformFlagsConsistency:
    def test_all_flags_are_bools(self) -> None:
        assert isinstance(IS_ANDROID, bool)
        assert isinstance(IS_IOS, bool)
        assert isinstance(IS_DESKTOP, bool)

    def test_flags_are_mutually_exclusive(self) -> None:
        # A single Python process is never simultaneously Android, iOS and desktop.
        assert sum([IS_ANDROID, IS_IOS, IS_DESKTOP]) <= 1

    def test_ci_environment_is_neither(self) -> None:
        """The test suite runs on Linux/macOS hosts, so all flags are False."""
        # This is more of a smoke check of the import-time detection: if
        # this ever starts being True on CI, someone has accidentally made
        # platform detection overeager on non-device hosts.
        if os.environ.get("PN_PLATFORM") in {"ios", "android", "desktop"}:
            pytest.skip("Running under an explicit PN_PLATFORM; flags correctly reflect that.")
        assert IS_ANDROID is False
        assert IS_IOS is False
        assert IS_DESKTOP is False
