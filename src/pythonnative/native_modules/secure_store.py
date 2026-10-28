"""Encrypted key/value storage for secrets (tokens, credentials).

[`SecureStore`][pythonnative.SecureStore] persists small string values
in the iOS Keychain and Android ``EncryptedSharedPreferences`` (the
native ``SecureStore`` module), the right place for auth tokens and
other secrets that [`AsyncStorage`][pythonnative.AsyncStorage] (plain,
unencrypted) should never hold.

Both backing stores complete on the calling thread, so every method is
synchronous. Reads return ``Optional[str]``; writes and deletes return
nothing and raise
[`NativeModuleError`][pythonnative.native_modules.NativeModuleError]
when the native store reports failure. Off device the module falls back to an in-process dict
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

from .registry import NativeModuleError, native_module


class SecureStore:
    """Encrypted secret storage (synchronous).

    Raises:
        NativeModuleError: If the Keychain / EncryptedSharedPreferences
            operation fails (for example a Keychain entitlement problem),
            including when the native side reports ``False`` for a write
            or a delete instead of raising.
    """

    @staticmethod
    def set_item(key: str, value: str) -> None:
        """Store ``value`` under ``key``, replacing any previous value.

        Raises:
            NativeModuleError: If the store refused the write (the native
                module returned ``False``).
        """
        if not native_module("SecureStore").call("set_item", key=key, value=value):
            raise NativeModuleError("SecureStore", "set_item", f"could not store {key!r}", code="write_failed")

    @staticmethod
    def get_item(key: str) -> Optional[str]:
        """Return the value for ``key``, or ``None`` if absent."""
        value = native_module("SecureStore").call("get_item", key=key)
        return None if value is None else str(value)

    @staticmethod
    def delete_item(key: str) -> None:
        """Delete ``key``; deleting a key that isn't stored is not an error.

        Raises:
            NativeModuleError: If the store refused the delete (the native
                module returned ``False``).
        """
        if not native_module("SecureStore").call("delete_item", key=key):
            raise NativeModuleError("SecureStore", "delete_item", f"could not delete {key!r}", code="delete_failed")
