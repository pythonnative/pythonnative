"""Biometric authentication (Face ID / Touch ID / fingerprint).

[`Biometrics`][pythonnative.Biometrics] gates an action behind the
device's biometric hardware via ``LAContext`` (iOS) and
``BiometricPrompt`` (Android).

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

import asyncio
from typing import Any, Callable, Dict

from ..runtime import resolve_future
from ..utils import IS_ANDROID, IS_IOS

_pending: Dict[int, Any] = {}


class Biometrics:
    """Biometric authentication interface."""

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` when biometric auth can be attempted."""
        if IS_IOS:
            return _ios_available()
        if IS_ANDROID:
            return _android_available()
        return False

    @staticmethod
    async def authenticate(reason: str = "Authenticate") -> bool:
        """Present the biometric prompt; resolve ``True`` on success."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()

        def _done(ok: bool) -> None:
            resolve_future(future, ok)

        if IS_IOS:
            _ios_authenticate(reason, _done)
        elif IS_ANDROID:
            _android_authenticate(reason, _done)
        else:
            _done(False)

        return await future


# ======================================================================
# iOS: LAContext
# ======================================================================


def _ios_context() -> Any:
    from rubicon.objc import ObjCClass

    return ObjCClass("LAContext").alloc().init()


def _ios_available() -> bool:
    try:
        # LAPolicyDeviceOwnerAuthenticationWithBiometrics == 1
        return bool(_ios_context().canEvaluatePolicy_error_(1, None))
    except Exception:
        return False


def _ios_authenticate(reason: str, on_done: Callable[[bool], None]) -> None:
    try:
        from rubicon.objc import Block, ObjCClass

        context = _ios_context()
        token = id(context)
        _pending[token] = context

        def _reply(success: bool, error: Any) -> None:
            del error
            _pending.pop(token, None)
            try:
                on_done(bool(success))
            except Exception:
                pass

        context.evaluatePolicy_localizedReason_reply_(1, reason, Block(_reply, None, bool, ObjCClass("NSError")))
    except Exception:
        on_done(False)


# ======================================================================
# Android: BiometricPrompt
# ======================================================================


def _android_available() -> bool:
    try:
        from java import jclass

        from ..utils import get_android_context

        BiometricManager = jclass("androidx.biometric.BiometricManager")
        manager = BiometricManager.from_(get_android_context())
        Authenticators = jclass("androidx.biometric.BiometricManager$Authenticators")
        result = manager.canAuthenticate(Authenticators.BIOMETRIC_WEAK)
        return result == BiometricManager.BIOMETRIC_SUCCESS
    except Exception:
        return False


def _android_authenticate(reason: str, on_done: Callable[[bool], None]) -> None:
    try:
        from java import dynamic_proxy, jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        FragmentActivity = jclass("androidx.fragment.app.FragmentActivity")
        if not FragmentActivity.isInstance(ctx):
            on_done(False)
            return

        BiometricPrompt = jclass("androidx.biometric.BiometricPrompt")
        ContextCompat = jclass("androidx.core.content.ContextCompat")
        executor = ContextCompat.getMainExecutor(ctx)

        class _Callback(dynamic_proxy(BiometricPrompt.AuthenticationCallback)):  # type: ignore[misc]
            def onAuthenticationSucceeded(self, result: Any) -> None:  # noqa: N802, ARG002
                on_done(True)

            def onAuthenticationError(self, code: int, message: Any) -> None:  # noqa: N802, ARG002
                on_done(False)

            def onAuthenticationFailed(self) -> None:  # noqa: N802
                # Fired on a non-matching attempt; the prompt stays up,
                # so don't resolve yet.
                pass

        prompt = BiometricPrompt(ctx, executor, _Callback())
        Builder = jclass("androidx.biometric.BiometricPrompt$PromptInfo$Builder")
        info = Builder().setTitle(reason).setNegativeButtonText("Cancel").build()
        prompt.authenticate(info)
    except Exception:
        on_done(False)
