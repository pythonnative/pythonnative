"""Encrypted key/value storage for secrets (tokens, credentials).

[`SecureStore`][pythonnative.SecureStore] persists small string values
in the iOS Keychain and Android ``EncryptedSharedPreferences``, the
right place for auth tokens and other secrets that
[`AsyncStorage`][pythonnative.AsyncStorage] (plain, unencrypted) should
never hold.

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

from typing import Dict, Optional

from ..utils import IS_ANDROID, IS_IOS

_SERVICE = "com.pythonnative.securestore"
_desktop_store: Dict[str, str] = {}


class SecureStore:
    """Encrypted secret storage (synchronous)."""

    @staticmethod
    def set_item(key: str, value: str) -> bool:
        """Store ``value`` under ``key``. Returns ``True`` on success."""
        if IS_IOS:
            return _ios_set(key, value)
        if IS_ANDROID:
            return _android_set(key, value)
        _desktop_store[key] = value
        return True

    @staticmethod
    def get_item(key: str) -> Optional[str]:
        """Return the value for ``key``, or ``None`` if absent."""
        if IS_IOS:
            return _ios_get(key)
        if IS_ANDROID:
            return _android_get(key)
        return _desktop_store.get(key)

    @staticmethod
    def delete_item(key: str) -> bool:
        """Delete ``key``. Returns ``True`` if it existed and was removed."""
        if IS_IOS:
            return _ios_delete(key)
        if IS_ANDROID:
            return _android_delete(key)
        return _desktop_store.pop(key, None) is not None


# ======================================================================
# iOS: Security framework (Keychain)
# ======================================================================


def _ios_query(key: str) -> Dict[str, object]:
    from rubicon.objc import ObjCClass

    NSDictionary = ObjCClass("NSMutableDictionary")
    query = NSDictionary.alloc().init()
    query.setObject_forKey_("genp", "class")  # kSecClassGenericPassword shorthand
    query.setObject_forKey_(_SERVICE, "svce")
    query.setObject_forKey_(key, "acct")
    return query


def _ios_set(key: str, value: str) -> bool:
    try:
        from ctypes import CDLL, util

        from rubicon.objc import ObjCClass

        sec = CDLL(util.find_library("Security"))
        query = _ios_query(key)
        sec.SecItemDelete(query.ptr)
        data = ObjCClass("NSString").stringWithString_(value).dataUsingEncoding_(4)  # UTF-8
        query.setObject_forKey_(data, "v_Data")
        status = sec.SecItemAdd(query.ptr, None)
        return status == 0
    except Exception:
        return False


def _ios_get(key: str) -> Optional[str]:
    try:
        from ctypes import CDLL, byref, c_void_p, util

        from rubicon.objc import ObjCClass

        sec = CDLL(util.find_library("Security"))
        query = _ios_query(key)
        query.setObject_forKey_(True, "r_Data")
        query.setObject_forKey_("m_Limit_One", "m_Limit")
        result = c_void_p(0)
        status = sec.SecItemCopyMatching(query.ptr, byref(result))
        if status != 0 or not result.value:
            return None
        data = ObjCClass("NSData").alloc()  # placeholder to keep import used
        del data
        ns = ObjCClass("NSString").alloc().initWithData_encoding_(result, 4)
        return str(ns) if ns is not None else None
    except Exception:
        return None


def _ios_delete(key: str) -> bool:
    try:
        from ctypes import CDLL, util

        sec = CDLL(util.find_library("Security"))
        return sec.SecItemDelete(_ios_query(key).ptr) == 0
    except Exception:
        return False


# ======================================================================
# Android: EncryptedSharedPreferences
# ======================================================================


def _android_prefs() -> Optional[object]:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        MasterKey = jclass("androidx.security.crypto.MasterKey")
        Builder = jclass("androidx.security.crypto.MasterKey$Builder")
        EncryptedSharedPreferences = jclass("androidx.security.crypto.EncryptedSharedPreferences")
        KeyScheme = jclass("androidx.security.crypto.EncryptedSharedPreferences$PrefKeyEncryptionScheme")
        ValueScheme = jclass("androidx.security.crypto.EncryptedSharedPreferences$PrefValueEncryptionScheme")
        master = Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        return EncryptedSharedPreferences.create(
            ctx,
            _SERVICE,
            master,
            KeyScheme.AES256_SIV,
            ValueScheme.AES256_GCM,
        )
    except Exception:
        return None


def _android_set(key: str, value: str) -> bool:
    prefs = _android_prefs()
    if prefs is None:
        return False
    try:
        editor = prefs.edit()
        editor.putString(key, value)
        return bool(editor.commit())
    except Exception:
        return False


def _android_get(key: str) -> Optional[str]:
    prefs = _android_prefs()
    if prefs is None:
        return None
    try:
        value = prefs.getString(key, None)
        return str(value) if value is not None else None
    except Exception:
        return None


def _android_delete(key: str) -> bool:
    prefs = _android_prefs()
    if prefs is None:
        return False
    try:
        if not prefs.contains(key):
            return False
        editor = prefs.edit()
        editor.remove(key)
        return bool(editor.commit())
    except Exception:
        return False
