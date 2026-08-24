"""Cross-platform key/value persistence (``AsyncStorage``).

Mirrors React Native's ``AsyncStorage`` API but with native ``async``
coroutines and a JSON convenience layer. Values are persisted using
the platform-appropriate key/value store:

- **iOS**: ``NSUserDefaults`` (standard user defaults).
- **Android**: ``SharedPreferences`` (file ``"pn_async_storage"``).
- **Desktop / tests**: an in-memory dict optionally backed by a JSON
  file under
  [`FileSystem.app_dir`][pythonnative.native_modules.file_system.FileSystem.app_dir]
  for inter-run persistence during local development.

All operations are coroutines so they don't block the framework loop;
the underlying native calls are dispatched via
:func:`asyncio.to_thread`.

Example:
    ```python
    import pythonnative as pn


    async def remember_user(user):
        await pn.AsyncStorage.set_json("current_user", user.to_dict())


    async def restore_session():
        user_dict = await pn.AsyncStorage.get_json("current_user")
        if user_dict is None:
            return None
        return User.from_dict(user_dict)
    ```
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Callable, List, Optional, Tuple, TypeVar

from .utils import IS_ANDROID, IS_IOS

T = TypeVar("T")

# ======================================================================
# Backend selection
# ======================================================================


_DEFAULTS_SUITE = "pn_async_storage"


# Cache the NSUserDefaults class lookup. rubicon.objc's
# ``ObjCClass("NSUserDefaults")`` walks the ObjC runtime metadata which
# takes hundreds of milliseconds on first call; resolving once at module
# import keeps every later get/set/delete in the sub-millisecond range.
_ios_defaults: Any = None


def _ios_get_defaults() -> Any:
    global _ios_defaults
    if _ios_defaults is None:
        from rubicon.objc import ObjCClass

        _ios_defaults = ObjCClass("NSUserDefaults").standardUserDefaults
    return _ios_defaults


def _ios_set(key: str, value: str) -> None:
    defaults = _ios_get_defaults()
    defaults.setObject_forKey_(value, key)
    # ``synchronize()`` is documented as unnecessary on modern iOS and
    # can block for seconds while it flushes to disk on a busy system;
    # NSUserDefaults already coalesces writes asynchronously.


def _ios_get(key: str) -> Optional[str]:
    defaults = _ios_get_defaults()
    val = defaults.stringForKey_(key)
    if val is None:
        return None
    try:
        return str(val)
    except Exception:
        return None


def _ios_delete(key: str) -> None:
    defaults = _ios_get_defaults()
    defaults.removeObjectForKey_(key)


def _ios_all_keys() -> List[str]:
    defaults = _ios_get_defaults()
    rep = defaults.dictionaryRepresentation()
    if rep is None:
        return []
    try:
        keys = rep.allKeys
        return [str(keys.objectAtIndex_(i)) for i in range(keys.count)]
    except Exception:
        return []


def _ios_clear() -> None:
    for key in _ios_all_keys():
        _ios_delete(key)


def _android_prefs() -> Any:
    from java import jclass

    from .utils import get_android_context

    Context = jclass("android.content.Context")
    ctx = get_android_context()
    return ctx.getSharedPreferences(_DEFAULTS_SUITE, Context.MODE_PRIVATE)


def _android_set(key: str, value: str) -> None:
    prefs = _android_prefs()
    editor = prefs.edit()
    editor.putString(key, value)
    editor.apply()


def _android_get(key: str) -> Optional[str]:
    prefs = _android_prefs()
    if not prefs.contains(key):
        return None
    try:
        return str(prefs.getString(key, None))
    except Exception:
        return None


def _android_delete(key: str) -> None:
    prefs = _android_prefs()
    editor = prefs.edit()
    editor.remove(key)
    editor.apply()


def _android_all_keys() -> List[str]:
    prefs = _android_prefs()
    all_map = prefs.getAll()
    keys = all_map.keySet()
    it = keys.iterator()
    out: List[str] = []
    while it.hasNext():
        out.append(str(it.next()))
    return out


def _android_clear() -> None:
    prefs = _android_prefs()
    editor = prefs.edit()
    editor.clear()
    editor.apply()


# ======================================================================
# Desktop / test backend
# ======================================================================


_desktop_lock = threading.Lock()
_desktop_store: dict = {}
_desktop_loaded = False


def _desktop_path() -> Optional[str]:
    # Tests can opt out of disk persistence by leaving the env var unset.
    base = os.environ.get("PN_STORAGE_DIR")
    if not base:
        return None
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        return None
    return os.path.join(base, "pn_async_storage.json")


def _desktop_load() -> None:
    global _desktop_loaded
    if _desktop_loaded:
        return
    _desktop_loaded = True
    path = _desktop_path()
    if path is None or not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _desktop_store.update({str(k): str(v) for k, v in data.items()})
    except OSError:
        return
    except json.JSONDecodeError:
        return


def _desktop_persist() -> None:
    path = _desktop_path()
    if path is None:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_desktop_store, f)
    except OSError:
        pass


def _desktop_set(key: str, value: str) -> None:
    with _desktop_lock:
        _desktop_load()
        _desktop_store[key] = value
        _desktop_persist()


def _desktop_get(key: str) -> Optional[str]:
    with _desktop_lock:
        _desktop_load()
        return _desktop_store.get(key)


def _desktop_delete(key: str) -> None:
    with _desktop_lock:
        _desktop_load()
        _desktop_store.pop(key, None)
        _desktop_persist()


def _desktop_all_keys() -> List[str]:
    with _desktop_lock:
        _desktop_load()
        return list(_desktop_store.keys())


def _desktop_clear() -> None:
    with _desktop_lock:
        _desktop_store.clear()
        _desktop_persist()


# ======================================================================
# Public API
# ======================================================================


class AsyncStorage:
    """Async key/value persistence layered on platform-native stores.

    Every method is a coroutine that returns when the underlying
    native operation completes. Strings round-trip directly via
    [`get`][pythonnative.storage.AsyncStorage.get] /
    [`set`][pythonnative.storage.AsyncStorage.set]; richer values can
    use [`get_json`][pythonnative.storage.AsyncStorage.get_json] /
    [`set_json`][pythonnative.storage.AsyncStorage.set_json] which
    add a JSON encode/decode step.
    """

    @staticmethod
    async def get(key: str) -> Optional[str]:
        """Return the string stored at ``key``, or ``None`` if missing."""
        if IS_IOS:
            return await asyncio.to_thread(_ios_get, key)
        if IS_ANDROID:
            return await asyncio.to_thread(_android_get, key)
        return await asyncio.to_thread(_desktop_get, key)

    @staticmethod
    async def set(key: str, value: str) -> None:
        """Persist ``value`` under ``key``.

        ``value`` must be a ``str``. For non-string values, use
        [`set_json`][pythonnative.storage.AsyncStorage.set_json].
        """
        if not isinstance(value, str):
            raise TypeError("AsyncStorage.set requires a str value; use set_json for richer types")
        if IS_IOS:
            await asyncio.to_thread(_ios_set, key, value)
        elif IS_ANDROID:
            await asyncio.to_thread(_android_set, key, value)
        else:
            await asyncio.to_thread(_desktop_set, key, value)

    @staticmethod
    async def delete(key: str) -> None:
        """Remove the entry at ``key`` if present (no-op otherwise)."""
        if IS_IOS:
            await asyncio.to_thread(_ios_delete, key)
        elif IS_ANDROID:
            await asyncio.to_thread(_android_delete, key)
        else:
            await asyncio.to_thread(_desktop_delete, key)

    @staticmethod
    async def all_keys() -> List[str]:
        """Return every persisted key (order is platform-dependent)."""
        if IS_IOS:
            return await asyncio.to_thread(_ios_all_keys)
        if IS_ANDROID:
            return await asyncio.to_thread(_android_all_keys)
        return await asyncio.to_thread(_desktop_all_keys)

    @staticmethod
    async def clear() -> None:
        """Remove every entry written through ``AsyncStorage``."""
        if IS_IOS:
            await asyncio.to_thread(_ios_clear)
        elif IS_ANDROID:
            await asyncio.to_thread(_android_clear)
        else:
            await asyncio.to_thread(_desktop_clear)

    @staticmethod
    async def get_json(key: str) -> Any:
        """Return the JSON-decoded value stored at ``key``, or ``None``.

        If the stored value isn't valid JSON, returns ``None`` rather
        than raising; assume the entry was written by another
        process or an older version of the app.
        """
        raw = await AsyncStorage.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    async def set_json(key: str, value: Any) -> None:
        """JSON-encode ``value`` and persist it under ``key``."""
        await AsyncStorage.set(key, json.dumps(value, default=str))


def use_persisted_state(
    key: str,
    initial: T,
) -> Tuple[T, Callable[[Any], None]]:
    """Persisted [`use_state`][pythonnative.hooks.use_state] variant.

    Backed by [`AsyncStorage`][pythonnative.storage.AsyncStorage]:
    behaves like ``use_state`` but loads the prior value (if any) on
    mount and persists every subsequent update. Until the load
    completes the value is ``initial``, the same fallback React
    Native users get with ``AsyncStorage.getItem``.

    The setter accepts either a value or a ``current -> new``
    callable, matching
    [`use_state`][pythonnative.use_state]. Writes are
    fire-and-forget; failures are silently absorbed (storage is
    best-effort by design).

    Args:
        key: Storage key. Pass a stable, namespaced string
            (e.g. ``"settings.theme"``).
        initial: Value used before the first load completes.

    Returns:
        ``(value, setter)``, same shape as
        [`use_state`][pythonnative.use_state].

    Example:
        ```python
        import pythonnative as pn


        @pn.component
        def ThemeToggle():
            theme, set_theme = pn.use_persisted_state("settings.theme", "light")
            return pn.Button(
                f"Theme: {theme}",
                on_press=lambda: set_theme("dark" if theme == "light" else "light"),
            )
        ```
    """
    from .hooks import use_callback, use_effect, use_ref, use_state
    from .runtime import run_async

    state, set_state = use_state(initial)
    loaded = use_ref(False)

    async def _load() -> None:
        stored = await AsyncStorage.get_json(key)
        if stored is not None:
            set_state(stored)
        loaded.current = True

    use_effect(_load, [key])

    def setter(value_or_updater: Any) -> None:
        def _reducer(current: Any) -> Any:
            new_value = value_or_updater(current) if callable(value_or_updater) else value_or_updater
            if loaded.current is True:
                run_async(AsyncStorage.set_json(key, new_value))
            return new_value

        set_state(_reducer)

    stable_setter = use_callback(setter, [key])
    return state, stable_setter


__all__ = ["AsyncStorage", "use_persisted_state"]
