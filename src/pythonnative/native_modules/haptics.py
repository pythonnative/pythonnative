"""Haptic feedback and raw vibration.

Two interfaces live here, both backed by the native ``Haptics`` module:

- [`Haptics`][pythonnative.Haptics]: semantic, iOS-style feedback
  (impact / notification / selection) backed by
  ``UIFeedbackGenerator`` on iOS and ``VibrationEffect`` patterns on
  Android.
- [`Vibration`][pythonnative.Vibration]: a blunt "buzz for N
  milliseconds" interface for cases where you want an explicit
  duration.

Every method is synchronous (the OS queues the effect and returns).
Missing hardware is not an error: on a device without a Taptic Engine
or vibrator, and off device the native module simply does nothing.
"""

from __future__ import annotations

from typing import Any

from .registry import native_module

ImpactStyle = str  # "light" | "medium" | "heavy" | "soft" | "rigid"
NotificationType = str  # "success" | "warning" | "error"


def _call(method: str, **args: Any) -> None:
    native_module("Haptics").call(method, **args)


class Haptics:
    """Semantic haptic feedback (synchronous).

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def impact(style: ImpactStyle = "medium") -> None:
        """Play a physical "impact" tap of the given ``style``."""
        _call("impact", style=style)

    @staticmethod
    def notification(type_: NotificationType = "success") -> None:
        """Play a success / warning / error notification pattern."""
        _call("notification", type=type_)

    @staticmethod
    def selection() -> None:
        """Play the light "selection changed" tick."""
        _call("selection")


class Vibration:
    """Raw vibration control (synchronous).

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def vibrate(duration_ms: int = 400) -> None:
        """Vibrate for ``duration_ms`` milliseconds.

        iOS has no arbitrary-duration API; the native module
        approximates short buzzes with a heavy impact and longer ones
        with the legacy system vibration sound.
        """
        _call("vibrate", duration_ms=int(duration_ms))

    @staticmethod
    def cancel() -> None:
        """Cancel an in-progress vibration (Android only)."""
        _call("cancel")
