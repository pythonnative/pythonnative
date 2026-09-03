"""Encrypted key/value storage for secrets (tokens, credentials).

[`SecureStore`][pythonnative.SecureStore] persists small string values
in the iOS Keychain and Android ``EncryptedSharedPreferences`` (the
native ``SecureStore`` module), the right place for auth tokens and
other secrets that [`AsyncStorage`][pythonnative.AsyncStorage] (plain,
unencrypted) should never hold.

All methods are synchronous and return a ``bool`` (writes/deletes) or
``Optional[str]`` (reads). On desktop the module falls back to an
in-process dict so code paths stay exercisable without a device
Keychain.

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
    """Encrypted secret storage (synchronous)."""

    @staticmethod
    def set_item(key: str, value: str) -> bool:
        """Store ``value`` under ``key``. Returns ``True`` on success."""
        try:
            return bool(native_module("SecureStore").call("set_item", key=key, value=value))
        except Exception:
            return False

    @staticmethod
    def get_item(key: str) -> Optional[str]:
        """Return the value for ``key``, or ``None`` if absent."""
        try:
            value = native_module("SecureStore").call("get_item", key=key)
        except Exception:
            return None
        return None if value is None else str(value)

    @staticmethod
    def delete_item(key: str) -> bool:
        """Delete ``key``. Returns ``True`` if it existed and was removed."""
        try:
            return bool(native_module("SecureStore").call("delete_item", key=key))
        except Exception:
            return False
