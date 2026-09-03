"""Biometric authentication (Face ID / Touch ID / fingerprint).

[`Biometrics`][pythonnative.Biometrics] gates an action behind the
device's biometric hardware via ``LAContext`` (iOS) and
``BiometricPrompt`` (Android), both implemented in the native
``Biometrics`` module.

``is_available`` is synchronous (a capability lookup); ``authenticate``
is a coroutine that presents the system prompt and resolves to ``True``
on success or ``False`` when the user fails or cancels the prompt.

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
    """Biometric authentication interface.

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` when biometric auth can be attempted (enrolled hardware; ``False`` on desktop)."""
        return bool(native_module("Biometrics").call("is_available"))

    @staticmethod
    async def authenticate(reason: str = "Authenticate") -> bool:
        """Present the biometric prompt; resolve ``True`` on success, ``False`` on failure or cancel."""
        return bool(await native_module("Biometrics").call_async("authenticate", reason=reason))
