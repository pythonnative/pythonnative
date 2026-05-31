"""Haptic feedback and raw vibration.

Two interfaces live here:

- [`Haptics`][pythonnative.Haptics] — semantic, iOS-style feedback
  (impact / notification / selection) backed by
  ``UIFeedbackGenerator`` on iOS and ``VibrationEffect`` patterns on
  Android.
- [`Vibration`][pythonnative.Vibration] — a blunt "buzz for N
  milliseconds" interface for cases where you want an explicit
  duration.

Every method is synchronous and best-effort: on a device that lacks a
Taptic Engine / vibrator, or on desktop, calls are silent no-ops rather
than errors.
"""

from __future__ import annotations

from typing import Any, Optional

from ..utils import IS_ANDROID, IS_IOS

ImpactStyle = str  # "light" | "medium" | "heavy" | "soft" | "rigid"
NotificationType = str  # "success" | "warning" | "error"

_IOS_IMPACT_STYLE = {"light": 0, "medium": 1, "heavy": 2, "soft": 4, "rigid": 5}
_IOS_NOTIFICATION_TYPE = {"success": 0, "warning": 1, "error": 2}

# Approximate Android fallback durations (ms) per semantic feedback.
_ANDROID_IMPACT_MS = {"light": 10, "medium": 20, "heavy": 40, "soft": 15, "rigid": 30}
_ANDROID_NOTIFICATION_MS = {"success": 30, "warning": 50, "error": 70}


class Haptics:
    """Semantic haptic feedback (synchronous, best-effort)."""

    @staticmethod
    def impact(style: ImpactStyle = "medium") -> None:
        """Play a physical "impact" tap of the given ``style``."""
        if IS_IOS:
            _ios_impact(style)
        elif IS_ANDROID:
            _android_buzz(_ANDROID_IMPACT_MS.get(style, 20))

    @staticmethod
    def notification(type_: NotificationType = "success") -> None:
        """Play a success / warning / error notification pattern."""
        if IS_IOS:
            _ios_notification(type_)
        elif IS_ANDROID:
            _android_buzz(_ANDROID_NOTIFICATION_MS.get(type_, 30))

    @staticmethod
    def selection() -> None:
        """Play the light "selection changed" tick."""
        if IS_IOS:
            _ios_selection()
        elif IS_ANDROID:
            _android_buzz(8)


class Vibration:
    """Raw vibration control (synchronous, best-effort)."""

    @staticmethod
    def vibrate(duration_ms: int = 400) -> None:
        """Vibrate for ``duration_ms`` milliseconds."""
        if IS_ANDROID:
            _android_buzz(int(duration_ms))
        elif IS_IOS:
            # iOS has no arbitrary-duration API; approximate with a
            # heavy impact for short buzzes and the legacy AudioServices
            # vibration for longer ones.
            if duration_ms >= 200:
                _ios_legacy_vibrate()
            else:
                _ios_impact("heavy")

    @staticmethod
    def cancel() -> None:
        """Cancel an in-progress vibration (Android only)."""
        if IS_ANDROID:
            vibrator = _android_vibrator()
            if vibrator is not None:
                try:
                    vibrator.cancel()
                except Exception:
                    pass


# ======================================================================
# iOS
# ======================================================================


def _ios_impact(style: str) -> None:
    try:
        from rubicon.objc import ObjCClass

        generator = ObjCClass("UIImpactFeedbackGenerator").alloc().initWithStyle_(_IOS_IMPACT_STYLE.get(style, 1))
        generator.prepare()
        generator.impactOccurred()
    except Exception:
        pass


def _ios_notification(type_: str) -> None:
    try:
        from rubicon.objc import ObjCClass

        generator = ObjCClass("UINotificationFeedbackGenerator").alloc().init()
        generator.prepare()
        generator.notificationOccurred_(_IOS_NOTIFICATION_TYPE.get(type_, 0))
    except Exception:
        pass


def _ios_selection() -> None:
    try:
        from rubicon.objc import ObjCClass

        generator = ObjCClass("UISelectionFeedbackGenerator").alloc().init()
        generator.prepare()
        generator.selectionChanged()
    except Exception:
        pass


def _ios_legacy_vibrate() -> None:
    try:
        from ctypes import CDLL, util

        audio = CDLL(util.find_library("AudioToolbox"))
        audio.AudioServicesPlaySystemSound(4095)  # kSystemSoundID_Vibrate
    except Exception:
        pass


# ======================================================================
# Android
# ======================================================================


def _android_vibrator() -> Optional[Any]:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Build = jclass("android.os.Build")
        if Build.VERSION.SDK_INT >= 31:
            VibratorManager = jclass("android.os.VibratorManager")
            Context = jclass("android.content.Context")
            manager = ctx.getSystemService(Context.VIBRATOR_MANAGER_SERVICE)
            VibratorManager  # referenced for clarity
            return manager.getDefaultVibrator()
        Context = jclass("android.content.Context")
        return ctx.getSystemService(Context.VIBRATOR_SERVICE)
    except Exception:
        return None


def _android_buzz(duration_ms: int) -> None:
    vibrator = _android_vibrator()
    if vibrator is None:
        return
    try:
        from java import jclass

        Build = jclass("android.os.Build")
        if Build.VERSION.SDK_INT >= 26:
            VibrationEffect = jclass("android.os.VibrationEffect")
            effect = VibrationEffect.createOneShot(int(duration_ms), VibrationEffect.DEFAULT_AMPLITUDE)
            vibrator.vibrate(effect)
        else:
            vibrator.vibrate(int(duration_ms))
    except Exception:
        pass
