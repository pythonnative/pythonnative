"""Biometric authentication (Face ID / Touch ID / fingerprint).

[`Biometrics`][pythonnative.Biometrics] gates an action behind the
device's biometric hardware via ``LAContext`` (iOS) and
``BiometricPrompt`` (Android), both implemented in the native
``Biometrics`` module.

``is_available`` is synchronous; ``authenticate`` is a coroutine that
presents the system prompt and resolves to ``True`` on success or
``False`` on failure / cancellation.

Example:
    ```python
    import pythonnative as pn

    async def unlock():
        if await pn.Biometrics.authenticate("Unlock your vault"):
            show_secrets()
    ```
"""

from __future__ import annotations

from .registry import native_module


class Biometrics:
    """Biometric authentication interface."""

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` when biometric auth can be attempted."""
        try:
            return bool(native_module("Biometrics").call("is_available"))
        except Exception:
            return False

    @staticmethod
    async def authenticate(reason: str = "Authenticate") -> bool:
        """Present the biometric prompt; resolve ``True`` on success."""
        try:
            return bool(await native_module("Biometrics").call_async("authenticate", reason=reason))
        except Exception:
            return False
