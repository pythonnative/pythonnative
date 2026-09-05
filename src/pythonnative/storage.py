"""Cross-platform key/value persistence (``AsyncStorage``).

Mirrors React Native's ``AsyncStorage`` API but with native ``async``
coroutines and a JSON convenience layer. Values are persisted by the
native ``Storage`` module:

- **iOS**: ``NSUserDefaults`` (standard user defaults).
- **Android**: ``SharedPreferences`` (file ``"pn_async_storage"``).
- **Browser preview / tests**: an in-memory dict optionally backed by a JSON
  file under ``PN_STORAGE_DIR`` for inter-run persistence during local
  development (see
  [`FallbackStorage`][pythonnative.native_modules.fallback.FallbackStorage]).

Every operation is a coroutine. The platform stores answer in
microseconds, so calls complete inline on the framework loop without
a thread hop.

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

import json
from typing import Any, Callable, List, Optional, Tuple, TypeVar

from .native_modules.registry import NativeModule, native_module

T = TypeVar("T")


def _storage() -> NativeModule:
    return native_module("Storage")


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
        value = _storage().call("get", key=key)
        return None if value is None else str(value)

    @staticmethod
    async def set(key: str, value: str) -> None:
        """Persist ``value`` under ``key``.

        ``value`` must be a ``str``. For non-string values, use
        [`set_json`][pythonnative.storage.AsyncStorage.set_json].
        """
        if not isinstance(value, str):
            raise TypeError("AsyncStorage.set requires a str value; use set_json for richer types")
        _storage().call("set", key=key, value=value)

    @staticmethod
    async def delete(key: str) -> None:
        """Remove the entry at ``key`` if present (no-op otherwise)."""
        _storage().call("delete", key=key)

    @staticmethod
    async def all_keys() -> List[str]:
        """Return every persisted key (order is platform-dependent)."""
        keys = _storage().call("all_keys")
        return [str(k) for k in keys] if isinstance(keys, list) else []

    @staticmethod
    async def clear() -> None:
        """Remove every entry written through ``AsyncStorage``."""
        _storage().call("clear")

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
