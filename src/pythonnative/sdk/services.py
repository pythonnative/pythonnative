"""Canonical service interfaces shared by built-ins and extensions."""

# Protocol members are schema declarations. User-facing service docstrings live
# on the public facades in native_modules, rather than duplicating that API here.
# ruff: noqa: D101, D102
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Protocol

from ..assets import AssetManifest
from ..native_modules.images import ImageSize
from .schema import ModuleSchema, register_schema


class DeviceService(Protocol):
    """Static device and application facts.

    ``info`` returns ``platform``, ``os_version``, ``model``,
    ``manufacturer``, ``is_simulator``, ``is_tablet``, ``app_name``,
    ``app_version``, ``build_number``, ``bundle_id``, ``scale``,
    ``font_scale``, and ``locale`` on every platform. Natives also return
    ``app_dir`` (the writable data directory ``FileSystem`` resolves
    against), which the Python ``DeviceInfo`` record doesn't expose.
    """

    def info(self) -> Dict[str, Any]: ...


class AccessibilityInfoService(Protocol):
    """Screen-reader and reduce-motion state, announcements, and focus.

    The ``change`` event carries ``{"screen_reader": bool, "reduce_motion": bool}``.
    """

    def is_screen_reader_enabled(self) -> bool: ...

    def is_reduce_motion_enabled(self) -> bool: ...

    def announce(self, message: str) -> None: ...

    def set_accessibility_focus(self, tag: int) -> None: ...


class KeyboardService(Protocol):
    """On-screen keyboard state.

    The ``change`` event carries ``{"height": float, "visible": bool, "duration_ms": float}``.
    """

    def dismiss(self) -> None: ...

    def is_visible(self) -> bool: ...


class LocalizationService(Protocol):
    """User locales and time zone.

    ``get_locales`` returns records with ``language_tag``, ``language_code``,
    ``region_code``, and ``is_rtl``, preferred locale first. The ``change``
    event carries ``{"locales": [...], "timezone": str}``.
    """

    def get_locales(self) -> List[Dict[str, Any]]: ...

    def get_timezone(self) -> str: ...


class AppStateService(Protocol):
    def current_state(self) -> str: ...


class StorageService(Protocol):
    def get(self, key: str) -> Optional[str]: ...

    def set(self, key: str, value: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def all_keys(self) -> List[str]: ...

    def clear(self) -> None: ...


class SecureStoreService(Protocol):
    def set_item(self, key: str, value: str) -> bool: ...

    def get_item(self, key: str) -> Optional[str]: ...

    def delete_item(self, key: str) -> bool: ...

    def clear(self) -> None: ...


class ClipboardService(Protocol):
    def set_string(self, text: str) -> None: ...

    def get_string(self) -> str: ...


class AlertService(Protocol):
    def show(self, title: str, message: Optional[str], buttons: List[Dict[str, Any]], style: str) -> None: ...

    async def present(self, title: str, message: Optional[str], buttons: List[Dict[str, Any]], style: str) -> int: ...


class ShareService(Protocol):
    async def share(
        self, message: Optional[str] = None, url: Optional[str] = None, title: Optional[str] = None
    ) -> bool: ...


class LinkingService(Protocol):
    def open_url(self, url: str) -> bool: ...

    def can_open_url(self, url: str) -> bool: ...

    def open_settings(self) -> bool: ...


class HapticsService(Protocol):
    def impact(self, style: str = "medium") -> None: ...

    def notification(self, type: str = "success") -> None: ...

    def selection(self) -> None: ...

    def vibrate(self, duration_ms: int = 400) -> None: ...

    def cancel(self) -> None: ...


class BatteryService(Protocol):
    def get_level(self) -> float: ...

    def get_state(self) -> str: ...


class NetInfoService(Protocol):
    def fetch(self) -> Optional[Dict[str, Any]]: ...


class PermissionsService(Protocol):
    async def check(self, permission: str) -> str: ...

    async def request(self, permission: str) -> str: ...


class NotificationsService(Protocol):
    async def request_permission(self) -> bool: ...

    async def schedule(
        self, title: str, body: str = "", delay_seconds: float = 0, identifier: str = "default"
    ) -> bool: ...

    async def cancel(self, identifier: str = "default") -> None: ...

    async def get_device_token(self) -> Optional[str]: ...


class CameraService(Protocol):
    async def take_photo(self, *, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]: ...

    async def pick_from_gallery(self, *, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]: ...


class LocationService(Protocol):
    async def get_current(
        self, *, accuracy: Literal["balanced", "high"] = "balanced", timeout: float = 10.0
    ) -> Optional[Dict[str, float]]: ...


class BiometricsService(Protocol):
    def is_available(self) -> bool: ...

    async def authenticate(self, reason: str = "Authenticate") -> bool: ...


class AssetsService(Protocol):
    """Bundled-asset access: the dev overlay manifest, raw reads, existence checks."""

    def configure(self, overlay: Optional[str], manifest: AssetManifest) -> None: ...

    def read(self, path: str) -> Optional[str]: ...

    def exists(self, path: str) -> bool: ...


class WebViewsService(Protocol):
    """Asynchronous questions for a mounted ``WebView``, addressed by view tag."""

    async def eval_js(self, tag: int, script: str) -> str: ...


class ImagesService(Protocol):
    """Image pipeline helpers that don't belong on the ``Image`` element."""

    async def get_size(self, uri: str) -> ImageSize: ...

    async def prefetch(self, uri: str) -> bool: ...

    def clear_cache(self) -> None: ...


def install_services() -> None:
    """Register the canonical interfaces without constructing service objects."""
    register_schema(ModuleSchema.from_protocol("Device", DeviceService))
    register_schema(
        ModuleSchema.from_protocol("AccessibilityInfo", AccessibilityInfoService, events={"change": Dict[str, Any]})
    )
    register_schema(ModuleSchema.from_protocol("Keyboard", KeyboardService, events={"change": Dict[str, Any]}))
    register_schema(ModuleSchema.from_protocol("Localization", LocalizationService, events={"change": Dict[str, Any]}))
    register_schema(ModuleSchema.from_protocol("AppState", AppStateService, events={"change": str}))
    register_schema(ModuleSchema.from_protocol("Storage", StorageService))
    register_schema(ModuleSchema.from_protocol("SecureStore", SecureStoreService))
    register_schema(ModuleSchema.from_protocol("Clipboard", ClipboardService))
    register_schema(ModuleSchema.from_protocol("Alert", AlertService))
    register_schema(ModuleSchema.from_protocol("Share", ShareService))
    register_schema(ModuleSchema.from_protocol("Linking", LinkingService, events={"url": str}))
    register_schema(ModuleSchema.from_protocol("Haptics", HapticsService))
    register_schema(ModuleSchema.from_protocol("Battery", BatteryService, events={"change": Dict[str, Any]}))
    register_schema(ModuleSchema.from_protocol("NetInfo", NetInfoService, events={"change": Dict[str, Any]}))
    register_schema(ModuleSchema.from_protocol("Permissions", PermissionsService))
    notifications = ModuleSchema.from_protocol("Notifications", NotificationsService)
    notifications.methods["get_device_token"]["platforms"] = ["ios"]
    register_schema(notifications)
    register_schema(ModuleSchema.from_protocol("Camera", CameraService))
    register_schema(ModuleSchema.from_protocol("Location", LocationService))
    register_schema(ModuleSchema.from_protocol("Biometrics", BiometricsService))
    register_schema(ModuleSchema.from_protocol("Assets", AssetsService))
    register_schema(ModuleSchema.from_protocol("Images", ImagesService))
    register_schema(ModuleSchema.from_protocol("WebViews", WebViewsService))
