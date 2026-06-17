"""Cross-platform permission/capability catalog.

PythonNative apps declare the device capabilities they need in a single,
platform-agnostic ``[permissions]`` table in ``pythonnative.toml``:

```toml
[permissions]
camera = "Scan receipts with your camera."
location_when_in_use = "Show nearby stores."
notifications = true
face_id = "Unlock the app with Face ID."
```

This module maps each high-level capability to the concrete native
artifacts it requires:

- iOS: one or more ``Info.plist`` *usage description* keys (the strings
  shown in the system permission prompt), plus optional
  ``UIBackgroundModes`` entries.
- Android: one or more ``<uses-permission>`` entries in
  ``AndroidManifest.xml``.

A capability's value may be either a string (used verbatim as the iOS
usage description) or ``true`` (use the capability's
[`default_reason`][pythonnative.project.permissions.Capability]). A value
of ``false`` disables the capability, useful for switching one off
without deleting the line.

The catalog is the single source of truth shared by the iOS and Android
configurators and by ``pn doctor``; adding a capability here is all that
is required to make it declarable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple, Union

PermissionValue = Union[bool, str]
"""Type of a value in the ``[permissions]`` table: a reason string or a bool."""


@dataclass(frozen=True)
class Capability:
    """A declarable device capability and its native requirements.

    Attributes:
        key: The capability name as written in ``[permissions]``
            (e.g., ``"camera"``).
        summary: Human-readable description, shown by ``pn doctor`` and
            the docs.
        ios_usage_keys: ``Info.plist`` keys that receive the usage
            description string (e.g., ``"NSCameraUsageDescription"``).
        android_permissions: Fully-qualified Android permission names
            (e.g., ``"android.permission.CAMERA"``).
        ios_background_modes: ``UIBackgroundModes`` values to add
            (e.g., ``"location"``).
        default_reason: Fallback usage description used when the
            capability is declared as ``true`` instead of a string.
        needs_reason: Whether iOS requires a usage description for this
            capability. When ``False`` (e.g., notifications), declaring
            the capability as ``true`` is sufficient and no string is
            needed.
    """

    key: str
    summary: str
    ios_usage_keys: Tuple[str, ...] = ()
    android_permissions: Tuple[str, ...] = ()
    ios_background_modes: Tuple[str, ...] = ()
    default_reason: str = ""
    needs_reason: bool = True


def _cap(*args: object, **kwargs: object) -> Capability:
    return Capability(*args, **kwargs)  # type: ignore[arg-type]


# ======================================================================
# The catalog
# ======================================================================

CAPABILITIES: Dict[str, Capability] = {
    c.key: c
    for c in [
        Capability(
            key="camera",
            summary="Capture photos and video with the device camera.",
            ios_usage_keys=("NSCameraUsageDescription",),
            android_permissions=("android.permission.CAMERA",),
            default_reason="This app uses the camera.",
        ),
        Capability(
            key="microphone",
            summary="Record audio from the microphone.",
            ios_usage_keys=("NSMicrophoneUsageDescription",),
            android_permissions=("android.permission.RECORD_AUDIO",),
            default_reason="This app uses the microphone.",
        ),
        Capability(
            key="photo_library",
            summary="Read photos and videos from the photo library.",
            ios_usage_keys=("NSPhotoLibraryUsageDescription",),
            android_permissions=(
                "android.permission.READ_MEDIA_IMAGES",
                "android.permission.READ_MEDIA_VIDEO",
            ),
            default_reason="This app accesses your photo library.",
        ),
        Capability(
            key="photo_library_add",
            summary="Save photos and videos to the photo library.",
            ios_usage_keys=("NSPhotoLibraryAddUsageDescription",),
            android_permissions=(),
            default_reason="This app saves photos to your library.",
        ),
        Capability(
            key="location_when_in_use",
            summary="Access location while the app is in the foreground.",
            ios_usage_keys=("NSLocationWhenInUseUsageDescription",),
            android_permissions=(
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.ACCESS_COARSE_LOCATION",
            ),
            default_reason="This app uses your location.",
        ),
        Capability(
            key="location_always",
            summary="Access location in the foreground and background.",
            ios_usage_keys=(
                "NSLocationAlwaysAndWhenInUseUsageDescription",
                "NSLocationWhenInUseUsageDescription",
            ),
            android_permissions=(
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.ACCESS_COARSE_LOCATION",
                "android.permission.ACCESS_BACKGROUND_LOCATION",
            ),
            ios_background_modes=("location",),
            default_reason="This app uses your location, even in the background.",
        ),
        Capability(
            key="contacts",
            summary="Read the device address book.",
            ios_usage_keys=("NSContactsUsageDescription",),
            android_permissions=("android.permission.READ_CONTACTS",),
            default_reason="This app accesses your contacts.",
        ),
        Capability(
            key="calendars",
            summary="Read and write calendar events.",
            ios_usage_keys=("NSCalendarsUsageDescription",),
            android_permissions=(
                "android.permission.READ_CALENDAR",
                "android.permission.WRITE_CALENDAR",
            ),
            default_reason="This app accesses your calendar.",
        ),
        Capability(
            key="reminders",
            summary="Read and write reminders (iOS only).",
            ios_usage_keys=("NSRemindersUsageDescription",),
            android_permissions=(),
            default_reason="This app accesses your reminders.",
        ),
        Capability(
            key="motion",
            summary="Access motion and fitness / activity data.",
            ios_usage_keys=("NSMotionUsageDescription",),
            android_permissions=("android.permission.ACTIVITY_RECOGNITION",),
            default_reason="This app uses motion and fitness data.",
        ),
        Capability(
            key="face_id",
            summary="Authenticate with Face ID / biometrics.",
            ios_usage_keys=("NSFaceIDUsageDescription",),
            android_permissions=("android.permission.USE_BIOMETRIC",),
            default_reason="This app uses Face ID to authenticate you.",
        ),
        Capability(
            key="bluetooth",
            summary="Communicate with nearby Bluetooth devices.",
            ios_usage_keys=("NSBluetoothAlwaysUsageDescription",),
            android_permissions=(
                "android.permission.BLUETOOTH_CONNECT",
                "android.permission.BLUETOOTH_SCAN",
            ),
            default_reason="This app connects to Bluetooth devices.",
        ),
        Capability(
            key="speech_recognition",
            summary="Perform speech recognition (iOS only).",
            ios_usage_keys=("NSSpeechRecognitionUsageDescription",),
            android_permissions=(),
            default_reason="This app uses speech recognition.",
        ),
        Capability(
            key="notifications",
            summary="Show local and push notifications.",
            ios_usage_keys=(),
            android_permissions=("android.permission.POST_NOTIFICATIONS",),
            needs_reason=False,
        ),
        Capability(
            key="vibration",
            summary="Trigger haptic feedback / vibration.",
            ios_usage_keys=(),
            android_permissions=("android.permission.VIBRATE",),
            needs_reason=False,
        ),
        Capability(
            key="background_audio",
            summary="Continue playing audio in the background (iOS).",
            ios_usage_keys=(),
            ios_background_modes=("audio",),
            android_permissions=("android.permission.FOREGROUND_SERVICE",),
            needs_reason=False,
        ),
        Capability(
            key="background_fetch",
            summary="Perform periodic background fetches (iOS).",
            ios_usage_keys=(),
            ios_background_modes=("fetch",),
            android_permissions=(),
            needs_reason=False,
        ),
    ]
}
"""Mapping of capability key → [`Capability`][pythonnative.project.permissions.Capability]."""


# Permissions every app gets, regardless of declared capabilities. Both are
# "normal" (install-time) Android permissions that never prompt the user, and
# nearly every PythonNative app needs the network (``fetch``, ``use_query``,
# ``NetInfo``, remote images).
BASE_ANDROID_PERMISSIONS: Tuple[str, ...] = (
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
)
"""Android permissions added to every app (network access)."""


@dataclass
class ResolvedPermissions:
    """The native permission artifacts for a resolved capability set.

    Attributes:
        ios_usage_descriptions: ``Info.plist`` usage-description keys
            mapped to their reason strings.
        ios_background_modes: Ordered, de-duplicated ``UIBackgroundModes``
            values.
        android_permissions: Ordered, de-duplicated Android permission
            names (including the always-on base set).
    """

    ios_usage_descriptions: Dict[str, str] = field(default_factory=dict)
    ios_background_modes: List[str] = field(default_factory=list)
    android_permissions: List[str] = field(default_factory=list)


def unknown_capabilities(keys: object) -> List[str]:
    """Return any declared capability keys that aren't in the catalog.

    Args:
        keys: An iterable of capability key strings.

    Returns:
        The subset of ``keys`` not present in
        [`CAPABILITIES`][pythonnative.project.permissions.CAPABILITIES],
        in input order.
    """
    result: List[str] = []
    for key in keys:
        if key not in CAPABILITIES:
            result.append(str(key))
    return result


def resolve_permissions(
    permissions: Mapping[str, PermissionValue],
    *,
    extra_android_permissions: object = (),
) -> ResolvedPermissions:
    """Resolve a declared capability map into native permission artifacts.

    Args:
        permissions: The ``[permissions]`` table, capability key to a
            reason string or boolean. ``false``/``None`` values are
            skipped (capability disabled).
        extra_android_permissions: Additional raw Android permission
            names (e.g., from ``[android].permissions``) to append.

    Returns:
        A [`ResolvedPermissions`][pythonnative.project.permissions.ResolvedPermissions]
        with iOS usage descriptions, iOS background modes, and the full
        ordered Android permission list (base set first).

    Raises:
        ValueError: If an unknown capability key is present. Validate
            earlier with
            [`unknown_capabilities`][pythonnative.project.permissions.unknown_capabilities]
            for a friendlier error.
    """
    resolved = ResolvedPermissions()
    android: List[str] = list(BASE_ANDROID_PERMISSIONS)
    background: List[str] = []

    for key, value in permissions.items():
        if key not in CAPABILITIES:
            raise ValueError(f"Unknown capability: {key!r}")
        if value is False or value is None:
            continue
        cap = CAPABILITIES[key]
        reason = value if isinstance(value, str) and value.strip() else cap.default_reason
        for plist_key in cap.ios_usage_keys:
            # First declaration wins for a shared key (e.g. location_*).
            resolved.ios_usage_descriptions.setdefault(plist_key, reason)
        for mode in cap.ios_background_modes:
            if mode not in background:
                background.append(mode)
        for perm in cap.android_permissions:
            if perm not in android:
                android.append(perm)

    for perm in extra_android_permissions:
        if perm and perm not in android:
            android.append(str(perm))

    resolved.ios_background_modes = background
    resolved.android_permissions = android
    return resolved


def describe_catalog() -> str:
    """Return a multi-line, human-readable listing of all capabilities.

    Used by ``pn doctor`` / docs tooling to show what can be declared.
    """
    lines: List[str] = []
    for key in sorted(CAPABILITIES):
        cap = CAPABILITIES[key]
        lines.append(f"  {key:<22} {cap.summary}")
    return "\n".join(lines)
