"""Static device and application facts.

[`Device.info`][pythonnative.native_modules.device.Device.info] returns
one [`DeviceInfo`][pythonnative.DeviceInfo] record read from the native
``Device`` module (``UIDevice`` and the main bundle on iOS, ``Build`` and
``PackageManager`` on Android, ``navigator`` in the browser preview).
Everything in it is already known to the OS, so the call is synchronous.

The native module returns the record's keys plus ``app_dir``, the
writable data directory that
[`FileSystem`][pythonnative.FileSystem] resolves relative paths against.
``DeviceInfo`` doesn't expose it; use ``FileSystem.app_dir()``.

Example:
    ```python
    import pythonnative as pn

    info = pn.Device.info()
    if info.is_tablet:
        columns = 3
    print(f"{info.app_name} {info.app_version} ({info.build_number}) on {info.model}")
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .registry import native_module


@dataclass(frozen=True)
class DeviceInfo:
    """Facts about the device and the running application.

    Attributes:
        platform: ``"ios"``, ``"android"``, ``"web"`` (browser preview),
            or ``"test"`` (off device).
        os_version: OS version string (``"17.4"``, ``"14"``).
        model: Hardware model (``"iPhone"``, ``"Pixel 8"``).
        manufacturer: Hardware vendor (``"Apple"``, ``"Google"``).
        is_simulator: Running in the iOS Simulator or an Android emulator.
        is_tablet: The OS classifies the device as a tablet (iPad, or
            an Android device with a large smallest width).
        app_name: The display name of the app.
        app_version: The marketing version (``CFBundleShortVersionString``
            / ``versionName``).
        build_number: The build identifier (``CFBundleVersion`` /
            ``versionCode``), as a string.
        bundle_id: Bundle identifier / application id.
        scale: Physical pixels per layout unit.
        font_scale: The user's text-size multiplier.
        locale: The preferred locale as a BCP 47 language tag (``"en-US"``).
    """

    platform: str
    os_version: str
    model: str
    manufacturer: str
    is_simulator: bool
    is_tablet: bool = False
    app_name: str = ""
    app_version: str = ""
    build_number: str = ""
    bundle_id: str = ""
    scale: float = 1.0
    font_scale: float = 1.0
    locale: str = ""


def _text(info: Dict[str, Any], key: str, default: str = "") -> str:
    value = info.get(key)
    return default if value is None else str(value)


def _number(info: Dict[str, Any], key: str, default: float) -> float:
    value = info.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return default
    return float(value)


class Device:
    """Device information interface (synchronous).

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def info() -> DeviceInfo:
        """Return the device and app facts as a [`DeviceInfo`][pythonnative.DeviceInfo].

        Keys the native module leaves out fall back to ``""``, ``False``,
        or ``1.0``; keys it adds (``app_dir``) are ignored here.
        """
        raw = native_module("Device").call("info")
        info: Dict[str, Any] = raw if isinstance(raw, dict) else {}
        return DeviceInfo(
            platform=_text(info, "platform", "unknown"),
            os_version=_text(info, "os_version"),
            model=_text(info, "model"),
            manufacturer=_text(info, "manufacturer"),
            is_simulator=bool(info.get("is_simulator", False)),
            is_tablet=bool(info.get("is_tablet", False)),
            app_name=_text(info, "app_name"),
            app_version=_text(info, "app_version"),
            build_number=_text(info, "build_number"),
            bundle_id=_text(info, "bundle_id"),
            scale=_number(info, "scale", 1.0),
            font_scale=_number(info, "font_scale", 1.0),
            locale=_text(info, "locale"),
        )
