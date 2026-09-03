"""Off-device implementations of the built-in native modules.

On iOS and Android every module in this package is implemented in
Swift and Kotlin (``PythonNativeKit`` and the ``pythonnative`` Gradle
module). Off device (``pn preview``, unit tests) the same module names
resolve to the plain Python classes below, which keep the API usable
without a device: in-memory buffers, ``"unknown"`` states, and no-op
feedback.

Each class has the same method names and argument shapes as its native
counterpart, so a facade in this package never branches on platform.
Apps and tests may swap any of these with
[`register_python_module`][pythonnative.native_modules.registry.register_python_module].
"""

from __future__ import annotations

import json
import os
import platform as _platform
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

__all__ = ["default_implementation"]


# ======================================================================
# Device / host information
# ======================================================================


class DesktopDevice:
    """Static device information for the desktop preview."""

    def info(self) -> Dict[str, Any]:
        home = os.path.expanduser("~")
        app_dir = os.path.join(home, ".pythonnative_data")
        return {
            "platform": "desktop",
            "os": sys.platform,
            "os_version": _platform.release(),
            "model": _platform.machine(),
            "app_dir": app_dir,
            "cache_dir": os.path.join(app_dir, "cache"),
            "temp_dir": os.path.join(app_dir, "tmp"),
            "locale": os.environ.get("LANG", "en_US").split(".")[0],
            "app_version": "0.0.0",
            "build_number": "0",
            "bundle_id": "com.pythonnative.preview",
            "python_version": _platform.python_version(),
        }


class DesktopAppState:
    def current_state(self) -> str:
        return "active"


# ======================================================================
# Storage
# ======================================================================


class DesktopStorage:
    """Dict-backed ``AsyncStorage`` with optional JSON persistence.

    Set ``PN_STORAGE_DIR`` to persist between runs (``pn preview`` does
    this); leave it unset in tests for a purely in-memory store.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: Dict[str, str] = {}
        self._loaded = False

    def _path(self) -> Optional[str]:
        base = os.environ.get("PN_STORAGE_DIR")
        if not base:
            return None
        try:
            os.makedirs(base, exist_ok=True)
        except OSError:
            return None
        return os.path.join(base, "pn_async_storage.json")

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = self._path()
        if path is None or not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, dict):
            self._store.update({str(k): str(v) for k, v in data.items()})

    def _persist(self) -> None:
        path = self._path()
        if path is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._store, f)
        except OSError:
            pass

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._load()
            return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._load()
            self._store[key] = value
            self._persist()

    def delete(self, key: str) -> None:
        with self._lock:
            self._load()
            self._store.pop(key, None)
            self._persist()

    def all_keys(self) -> List[str]:
        with self._lock:
            self._load()
            return list(self._store.keys())

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._persist()

    def _reset(self) -> None:
        """Forget everything, including the on-disk snapshot (tests)."""
        with self._lock:
            self._store.clear()
            self._loaded = False


class DesktopSecureStore:
    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def set_item(self, key: str, value: str) -> bool:
        self._store[key] = value
        return True

    def get_item(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete_item(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def clear(self) -> None:
        self._store.clear()


class DesktopClipboard:
    def __init__(self) -> None:
        self._buffer = ""

    def set_string(self, text: str) -> None:
        self._buffer = "" if text is None else str(text)

    def get_string(self) -> str:
        return self._buffer


# ======================================================================
# System integration
# ======================================================================


class DesktopAlert:
    """Records alerts and answers with scripted responses.

    The log and response queue live on
    [`Alert`][pythonnative.alerts.Alert] (``Alert._test_log`` and
    ``Alert.set_test_response``) so tests have one place to look.
    """

    @staticmethod
    def _record(title: str, message: Optional[str], buttons: List[Dict[str, Any]], style: str) -> Any:
        from ..alerts import Alert

        Alert._test_log.append({"title": title, "message": message, "buttons": list(buttons), "style": style})
        return Alert

    def show(self, title: str, message: Optional[str], buttons: List[Dict[str, Any]], style: str) -> None:
        self._record(title, message, buttons, style)

    def present(self, title: str, message: Optional[str], buttons: List[Dict[str, Any]], style: str) -> int:
        return int(self._record(title, message, buttons, style)._next_test_response())


class DesktopShare:
    def share(self, message: Optional[str] = None, url: Optional[str] = None, title: Optional[str] = None) -> bool:
        del message, url, title
        return False


class DesktopLinking:
    def open_url(self, url: str) -> bool:
        del url
        return False

    def can_open_url(self, url: str) -> bool:
        del url
        return False

    def open_settings(self) -> bool:
        return False


class DesktopHaptics:
    def impact(self, style: str = "medium") -> None:
        del style

    def notification(self, type: str = "success") -> None:  # noqa: A002 - wire name
        del type

    def selection(self) -> None:
        pass

    def vibrate(self, duration_ms: int = 400) -> None:
        del duration_ms

    def cancel(self) -> None:
        pass


class DesktopBattery:
    def get_level(self) -> float:
        return -1.0

    def get_state(self) -> str:
        return "unknown"


class DesktopNetInfo:
    def fetch(self) -> Optional[Dict[str, Any]]:
        # ``None`` means "no fresh reading"; the facade keeps whatever
        # snapshot was last dispatched (tests push those directly).
        return None


class DesktopPermissions:
    def check(self, permission: str) -> str:
        del permission
        return "undetermined"

    def request(self, permission: str) -> str:
        del permission
        return "undetermined"


class DesktopNotifications:
    def request_permission(self) -> bool:
        return False

    def schedule(self, title: str, body: str = "", delay_seconds: float = 0, identifier: str = "default") -> bool:
        del title, body, delay_seconds, identifier
        return False

    def cancel(self, identifier: str = "default") -> None:
        del identifier

    def get_device_token(self) -> Optional[str]:
        return None


class DesktopCamera:
    def take_photo(self) -> Optional[str]:
        return None

    def pick_from_gallery(self) -> Optional[str]:
        return None


class DesktopLocation:
    def get_current(self) -> Optional[Dict[str, float]]:
        return None


class DesktopBiometrics:
    def is_available(self) -> bool:
        return False

    def authenticate(self, reason: str = "Authenticate") -> bool:
        del reason
        return False


_DEFAULTS: Dict[str, Callable[[], Any]] = {
    "Device": DesktopDevice,
    "AppState": DesktopAppState,
    "Storage": DesktopStorage,
    "SecureStore": DesktopSecureStore,
    "Clipboard": DesktopClipboard,
    "Alert": DesktopAlert,
    "Share": DesktopShare,
    "Linking": DesktopLinking,
    "Haptics": DesktopHaptics,
    "Battery": DesktopBattery,
    "NetInfo": DesktopNetInfo,
    "Permissions": DesktopPermissions,
    "Notifications": DesktopNotifications,
    "Camera": DesktopCamera,
    "Location": DesktopLocation,
    "Biometrics": DesktopBiometrics,
}


def default_implementation(name: str) -> Optional[Callable[[], Any]]:
    """Return the factory for the built-in desktop implementation of ``name``."""
    return _DEFAULTS.get(name)
