"""Pure-Python fallbacks for the built-in native modules.

On iOS and Android every module in this package is implemented in
Swift and Kotlin (``PythonNativeKit`` and the ``pythonnative`` Gradle
module). Off device the same module names resolve to the plain Python
classes below, which keep the API usable without a device: in-memory
buffers, ``"unknown"`` states, and no-op feedback. Unit tests use them
directly; the browser preview implements a handful of modules in the
page (``Alert``, ``Clipboard``, ``Device``, ...) and routes the rest
here.

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


def _host_language_tag() -> str:
    """Return the host's preferred locale as a BCP 47 tag (``LANG``, else ``en-US``)."""
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key, "")
        tag = value.split(".")[0].split("@")[0].replace("_", "-")
        if tag and tag not in ("C", "POSIX"):
            return tag
    return "en-US"


class FallbackDevice:
    """Static device information for the host machine.

    Returns the documented ``DeviceInfo`` keys plus ``app_dir`` and
    ``cache_dir``, which the native modules also return and
    ``FileSystem`` reads.
    """

    def info(self) -> Dict[str, Any]:
        home = os.path.expanduser("~")
        app_dir = os.path.join(home, ".pythonnative_data")
        return {
            "platform": "test",
            "os_version": _platform.release(),
            "model": _platform.machine(),
            "manufacturer": sys.platform,
            "is_simulator": False,
            "is_tablet": False,
            "app_name": "PythonNative",
            "app_version": "0.0.0",
            "build_number": "0",
            "bundle_id": "com.pythonnative.preview",
            "scale": 1.0,
            "font_scale": 1.0,
            "locale": _host_language_tag(),
            "app_dir": app_dir,
            "cache_dir": os.path.join(app_dir, "cache"),
        }


class FallbackAccessibilityInfo:
    """No screen reader, no reduce motion; announcements and focus are no-ops."""

    def is_screen_reader_enabled(self) -> bool:
        return False

    def is_reduce_motion_enabled(self) -> bool:
        return False

    def announce(self, message: str) -> None:
        del message

    def set_accessibility_focus(self, tag: int) -> None:
        del tag


class FallbackWebViews:
    """No page runs off device: ``eval_js`` answers the empty string."""

    def eval_js(self, tag: int, script: str) -> str:
        del tag, script
        return ""


class FallbackKeyboard:
    """No keyboard off device: ``dismiss`` is a no-op and ``is_visible`` is ``False``."""

    def dismiss(self) -> None:
        pass

    def is_visible(self) -> bool:
        return False


_RTL_LANGUAGES = frozenset({"ar", "fa", "he", "iw", "ur", "ps", "sd", "ug", "yi", "dv", "ku", "ckb"})


class FallbackLocalization:
    """The host's ``LANG`` as the only locale and ``UTC`` as the time zone."""

    def get_locales(self) -> List[Dict[str, Any]]:
        tag = _host_language_tag()
        parts = tag.split("-")
        language = parts[0].lower()
        region = next((part.upper() for part in parts[1:] if len(part) == 2 and part.isalpha()), "")
        return [
            {
                "language_tag": tag,
                "language_code": language,
                "region_code": region,
                "is_rtl": language in _RTL_LANGUAGES,
            }
        ]

    def get_timezone(self) -> str:
        return "UTC"


class FallbackAppState:
    def current_state(self) -> str:
        return "active"


# ======================================================================
# Storage
# ======================================================================


class FallbackStorage:
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


class FallbackSecureStore:
    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def set_item(self, key: str, value: str) -> bool:
        self._store[key] = value
        return True

    def get_item(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete_item(self, key: str) -> bool:
        self._store.pop(key, None)
        return True

    def clear(self) -> None:
        self._store.clear()


class FallbackClipboard:
    def __init__(self) -> None:
        self._buffer = ""

    def set_string(self, text: str) -> None:
        self._buffer = "" if text is None else str(text)

    def get_string(self) -> str:
        return self._buffer


# ======================================================================
# System integration
# ======================================================================


class FallbackAlert:
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


class FallbackShare:
    def share(self, message: Optional[str] = None, url: Optional[str] = None, title: Optional[str] = None) -> bool:
        del message, url, title
        return False


class FallbackLinking:
    def open_url(self, url: str) -> bool:
        del url
        return False

    def can_open_url(self, url: str) -> bool:
        del url
        return False

    def open_settings(self) -> bool:
        return False


class FallbackHaptics:
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


class FallbackBattery:
    def get_level(self) -> float:
        return -1.0

    def get_state(self) -> str:
        return "unknown"


class FallbackNetInfo:
    def fetch(self) -> Optional[Dict[str, Any]]:
        # ``None`` means "no fresh reading"; the facade keeps whatever
        # snapshot was last dispatched (tests push those directly).
        return None


class FallbackPermissions:
    def check(self, permission: str) -> str:
        del permission
        return "undetermined"

    def request(self, permission: str) -> str:
        del permission
        return "undetermined"


class FallbackNotifications:
    def request_permission(self) -> bool:
        return False

    def schedule(self, title: str, body: str = "", delay_seconds: float = 0, identifier: str = "default") -> bool:
        del title, body, delay_seconds, identifier
        return False

    def cancel(self, identifier: str = "default") -> None:
        del identifier

    def get_device_token(self) -> Optional[str]:
        return None


class FallbackCamera:
    def take_photo(self, *, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]:
        return None

    def pick_from_gallery(self, *, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]:
        return None


class FallbackLocation:
    def get_current(self, *, accuracy: str = "balanced", timeout: float = 10.0) -> Optional[Dict[str, float]]:
        return None


class FallbackBiometrics:
    def is_available(self) -> bool:
        return False

    def authenticate(self, reason: str = "Authenticate") -> bool:
        del reason
        return False


# ======================================================================
# Assets and images
# ======================================================================


class FallbackAssets:
    """Read bundled assets from the checked-out ``app/assets/`` directory."""

    def __init__(self) -> None:
        self.overlay: Optional[str] = None
        self.manifest: Any = None

    def configure(self, overlay: Optional[str], manifest: Any) -> None:
        self.overlay = overlay
        self.manifest = manifest

    def _find(self, path: str) -> Optional[str]:
        from ..assets import assets_roots, normalize_path

        rel = normalize_path(path)
        roots = [self.overlay] if self.overlay else []
        roots += [str(root) for root in assets_roots()]
        for root in roots:
            candidate = os.path.join(root, *rel.split("/"))
            if os.path.isfile(candidate):
                return candidate
        return None

    def read(self, path: str) -> Optional[str]:
        import base64

        found = self._find(path)
        if found is None:
            raise FileNotFoundError(f"asset not found: {path}")
        with open(found, "rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")

    def exists(self, path: str) -> bool:
        return self._find(path) is not None


class FallbackImages:
    """Header-only image measurement for PNG, JPEG, GIF, WebP, and BMP."""

    def _bytes(self, uri: str) -> tuple[bytes, float]:
        import base64

        from ..assets import ASSET_SCHEME, Asset, split_variant

        if uri.startswith(ASSET_SCHEME):
            asset = Asset(uri)
            _, scale = split_variant(asset.path)
            return asset.read_bytes(), scale
        if uri.startswith("data:"):
            _, _, payload = uri.partition(",")
            return base64.b64decode(payload), 1.0
        if uri.startswith(("http://", "https://")):
            import urllib.request

            with urllib.request.urlopen(uri, timeout=10) as response:  # noqa: S310 - caller-supplied URL
                return response.read(), 1.0
        path = uri[len("file://") :] if uri.startswith("file://") else uri
        with open(path, "rb") as handle:
            return handle.read(), 1.0

    def get_size(self, uri: str) -> Dict[str, float]:
        data, scale = self._bytes(uri)
        size = image_dimensions(data)
        if size is None:
            raise ValueError("unsupported or corrupt image")
        return {"width": size[0] / scale, "height": size[1] / scale}

    def prefetch(self, uri: str) -> bool:
        try:
            self._bytes(uri)
        except Exception:
            return False
        return True

    def clear_cache(self) -> None:
        return None


def image_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    """Return ``(width, height)`` in pixels from an image file header, or ``None``."""
    import struct

    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return width, height
    if data[:2] == b"BM" and len(data) >= 26:
        width, height = struct.unpack("<ii", data[18:26])
        return abs(width), abs(height)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8 " and len(data) >= 30:
            width, height = struct.unpack("<HH", data[26:30])
            return width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L" and len(data) >= 25:
            bits = struct.unpack("<I", data[21:25])[0]
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b"VP8X" and len(data) >= 30:
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return width, height
        return None
    if data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                offset += 2
                continue
            length = struct.unpack(">H", data[offset + 2 : offset + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[offset + 5 : offset + 9])
                return width, height
            offset += 2 + length
        return None
    return None


_DEFAULTS: Dict[str, Callable[[], Any]] = {
    "Device": FallbackDevice,
    "AccessibilityInfo": FallbackAccessibilityInfo,
    "Keyboard": FallbackKeyboard,
    "Localization": FallbackLocalization,
    "AppState": FallbackAppState,
    "Storage": FallbackStorage,
    "SecureStore": FallbackSecureStore,
    "Clipboard": FallbackClipboard,
    "Alert": FallbackAlert,
    "Share": FallbackShare,
    "Linking": FallbackLinking,
    "Haptics": FallbackHaptics,
    "Battery": FallbackBattery,
    "NetInfo": FallbackNetInfo,
    "Permissions": FallbackPermissions,
    "Notifications": FallbackNotifications,
    "Camera": FallbackCamera,
    "Location": FallbackLocation,
    "Biometrics": FallbackBiometrics,
    "Assets": FallbackAssets,
    "Images": FallbackImages,
    "WebViews": FallbackWebViews,
}


def default_implementation(name: str) -> Optional[Callable[[], Any]]:
    """Return the factory for the built-in Python fallback implementation of ``name``."""
    return _DEFAULTS.get(name)
