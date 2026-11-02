"""Biometric authentication (Face ID, Touch ID, and fingerprint).

Enable it in ``pythonnative.toml``. On iOS, ``face_id`` supplies the reason the
system prompt shows:

```toml
[plugins]
use = ["biometrics"]

[permissions]
face_id = "Unlock your vault."
```

[`Biometrics`][pythonnative.biometrics.Biometrics] gates an action behind the
device's biometric hardware through ``LAContext`` (iOS) and ``BiometricPrompt``
(Android).

Example:
    ```python
    from pythonnative.biometrics import Biometrics

    async def unlock():
        if await Biometrics.authenticate("Unlock your vault"):
            show_secrets()
    ```
"""

from __future__ import annotations

from typing import Protocol

from ..native_modules.registry import native_module
from ..sdk.plugin import plugin_module

__all__ = ["Biometrics"]


class _BiometricsService(Protocol):
    def is_available(self) -> bool: ...

    async def authenticate(self, reason: str = "Authenticate") -> bool: ...


class _Fallback:
    def is_available(self) -> bool:
        return False

    def authenticate(self, reason: str = "Authenticate") -> bool:
        del reason
        return False


plugin_module("Biometrics", _BiometricsService, plugin="biometrics", fallback=_Fallback)


class Biometrics:
    """Biometric authentication interface.

    Raises:
        NativeModuleError: If the native module fails, or with the code
            ``plugin_not_enabled`` when ``biometrics`` isn't in the build.
    """

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` when biometric auth can be attempted (enrolled hardware; ``False`` off device)."""
        return bool(native_module("Biometrics").call("is_available"))

    @staticmethod
    async def authenticate(reason: str = "Authenticate") -> bool:
        """Present the biometric prompt; resolve ``True`` on success, ``False`` on failure or cancel."""
        return bool(await native_module("Biometrics").call_async("authenticate", reason=reason))
