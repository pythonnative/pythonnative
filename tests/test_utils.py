"""Tests for pythonnative.utils platform detection."""

import os
import sys

import pytest

from pythonnative import utils
from pythonnative.utils import IS_ANDROID, IS_IOS, IS_WEB, _detect_ios, _detect_web


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


class TestWebDetection:
    """``_detect_web()`` keys off ``PN_PLATFORM=web`` and nothing else.

    Unlike Android and iOS, there is no host-level signal to fall back on: the
    browser preview runs because ``pn preview`` or ``pn start`` asked for it.
    """

    def test_detects_via_pn_platform_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "web")
        assert _detect_web() is True

    def test_unset_pn_platform_is_not_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        assert _detect_web() is False

    def test_empty_pn_platform_is_not_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PN_PLATFORM", "")
        assert _detect_web() is False

    @pytest.mark.parametrize("platform", ["ios", "android", "desktop"])
    def test_other_pn_platform_values_ignored(self, monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
        monkeypatch.setenv("PN_PLATFORM", platform)
        assert _detect_web() is False

    def test_host_platform_alone_is_not_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running on a laptop is not enough; only the explicit env var counts."""
        monkeypatch.delenv("PN_PLATFORM", raising=False)
        monkeypatch.setattr(sys, "platform", "darwin")
        assert _detect_web() is False


def _redetect(
    monkeypatch: pytest.MonkeyPatch,
    *,
    android: bool,
    ios: bool,
    web: bool,
) -> None:
    """Re-run platform detection with each individual detector forced.

    ``_ensure_platform_detection()`` only computes a flag whose global is still
    ``None``, and all three were filled in at import time, so the caches are
    cleared first. ``monkeypatch`` restores both the caches and the real
    detectors when the test ends.
    """
    monkeypatch.setattr(utils, "_is_android", None)
    monkeypatch.setattr(utils, "_is_ios", None)
    monkeypatch.setattr(utils, "_is_web", None)
    monkeypatch.setattr(utils, "_detect_android", lambda: android)
    monkeypatch.setattr(utils, "_detect_ios", lambda: ios)
    monkeypatch.setattr(utils, "_detect_web", lambda: web)
    utils._ensure_platform_detection()


class TestPlatformFlagPrecedence:
    """Android beats iOS beats web, so at most one flag is ever ``True``."""

    def test_web_wins_when_no_device_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=False, ios=False, web=True)
        assert utils._get_is_web() is True
        assert utils._get_is_android() is False
        assert utils._get_is_ios() is False

    def test_android_suppresses_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stale ``PN_PLATFORM=web`` must not fire on an Android device."""
        _redetect(monkeypatch, android=True, ios=False, web=True)
        assert utils._get_is_android() is True
        assert utils._get_is_web() is False

    def test_ios_suppresses_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=False, ios=True, web=True)
        assert utils._get_is_ios() is True
        assert utils._get_is_web() is False

    def test_android_suppresses_ios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=True, ios=True, web=False)
        assert utils._get_is_android() is True
        assert utils._get_is_ios() is False

    def test_no_signal_leaves_every_flag_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _redetect(monkeypatch, android=False, ios=False, web=False)
        assert utils._get_is_android() is False
        assert utils._get_is_ios() is False
        assert utils._get_is_web() is False

    @pytest.mark.parametrize("android", [False, True])
    @pytest.mark.parametrize("ios", [False, True])
    @pytest.mark.parametrize("web", [False, True])
    def test_at_most_one_flag_is_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
        android: bool,
        ios: bool,
        web: bool,
    ) -> None:
        """No combination of raw signals can light up two flags at once."""
        _redetect(monkeypatch, android=android, ios=ios, web=web)
        flags = [utils._get_is_android(), utils._get_is_ios(), utils._get_is_web()]
        assert sum(flags) <= 1


class TestPlatformFlagsConsistency:
    def test_all_flags_are_bools(self) -> None:
        assert isinstance(IS_ANDROID, bool)
        assert isinstance(IS_IOS, bool)
        assert isinstance(IS_WEB, bool)

    def test_flags_are_mutually_exclusive(self) -> None:
        # A single Python process is never simultaneously Android, iOS, and web.
        assert sum([IS_ANDROID, IS_IOS, IS_WEB]) <= 1

    def test_ci_environment_has_no_platform(self) -> None:
        """The test suite runs on Linux/macOS hosts, so all flags are False."""
        # This is more of a smoke check of the import-time detection: if
        # this ever starts being True on CI, someone has accidentally made
        # platform detection overeager on non-device hosts.
        if os.environ.get("PN_PLATFORM") in {"ios", "web"}:
            pytest.skip("Running under an explicit PN_PLATFORM; flags correctly reflect that.")
        assert IS_ANDROID is False
        assert IS_IOS is False
        assert IS_WEB is False
