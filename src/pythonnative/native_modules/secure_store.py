"""Encrypted key/value storage for secrets (tokens, credentials).

[`SecureStore`][pythonnative.SecureStore] persists small string values
in the iOS Keychain and Android ``EncryptedSharedPreferences`` (the
native ``SecureStore`` module), the right place for auth tokens and
other secrets that [`AsyncStorage`][pythonnative.AsyncStorage] (plain,
unencrypted) should never hold.

Both backing stores complete on the calling thread, so every method is
synchronous. Reads return ``Optional[str]``; writes return nothing and
raise on failure. Off device the module falls back to an in-process dict
so code paths stay exercisable without a device Keychain.

Example:
    ```python
    import pythonnative as pn

    pn.SecureStore.set_item("token", "abc123")
    token = pn.SecureStore.get_item("token")
    ```
"""

from __future__ import annotations

from typing import Optional

from .registry import native_module


class SecureStore:
    """Encrypted secret storage (synchronous).

    Raises:
        NativeModuleError: If the Keychain / EncryptedSharedPreferences
            operation fails (for example a Keychain entitlement problem).
    """

    @staticmethod
    def set_item(key: str, value: str) -> None:
        """Store ``value`` under ``key``, replacing any previous value."""
        native_module("SecureStore").call("set_item", key=key, value=value)

    @staticmethod
    def get_item(key: str) -> Optional[str]:
        """Return the value for ``key``, or ``None`` if absent."""
        value = native_module("SecureStore").call("get_item", key=key)
        return None if value is None else str(value)

    @staticmethod
    def delete_item(key: str) -> bool:
        """Delete ``key``. Returns ``True`` if it existed, ``False`` if there was nothing to delete."""
        return bool(native_module("SecureStore").call("delete_item", key=key))
