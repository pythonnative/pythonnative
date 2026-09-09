"""Canonical service interfaces shared by built-ins and extensions."""

# Protocol members are schema declarations. User-facing service docstrings live
# on the public facades in native_modules, rather than duplicating that API here.
# ruff: noqa: D101, D102
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Protocol

from .schema import ModuleSchema, register_schema


class DeviceService(Protocol):
    def info(self) -> Dict[str, Any]: ...


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
    def check(self, permission: str) -> str: ...

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


def install_services() -> None:
    """Register the canonical interfaces without constructing service objects."""
    register_schema(ModuleSchema.from_protocol("Device", DeviceService))
    register_schema(ModuleSchema.from_protocol("AppState", AppStateService))
    register_schema(ModuleSchema.from_protocol("Storage", StorageService))
    register_schema(ModuleSchema.from_protocol("SecureStore", SecureStoreService))
    register_schema(ModuleSchema.from_protocol("Clipboard", ClipboardService))
    register_schema(ModuleSchema.from_protocol("Alert", AlertService))
    register_schema(ModuleSchema.from_protocol("Share", ShareService))
    register_schema(ModuleSchema.from_protocol("Linking", LinkingService))
    register_schema(ModuleSchema.from_protocol("Haptics", HapticsService))
    register_schema(ModuleSchema.from_protocol("Battery", BatteryService))
    register_schema(ModuleSchema.from_protocol("NetInfo", NetInfoService))
    register_schema(ModuleSchema.from_protocol("Permissions", PermissionsService))
    register_schema(ModuleSchema.from_protocol("Notifications", NotificationsService))
    register_schema(ModuleSchema.from_protocol("Camera", CameraService))
    register_schema(ModuleSchema.from_protocol("Location", LocationService))
    register_schema(ModuleSchema.from_protocol("Biometrics", BiometricsService))
