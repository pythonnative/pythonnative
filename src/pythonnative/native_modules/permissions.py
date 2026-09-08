"""Runtime permission checks and requests.

[`Permissions`][pythonnative.Permissions] normalizes the very different
iOS and Android permission models behind two calls, both served by the
native ``Permissions`` module:

- ``check(permission)``: synchronous, returns a status without
  prompting.
- ``request(permission)``: a coroutine that shows the system prompt
  (if needed) and resolves to the resulting status.

Statuses are ``"granted"``, ``"denied"``, ``"blocked"`` (denied with
"don't ask again" / Settings required), or ``"undetermined"``.

Permission names are the same words you declare in the
``[permissions]`` table of ``pythonnative.toml``, so the string that
puts ``NSCameraUsageDescription`` in your Info.plist is the string you
pass here: ``"camera"``, ``"microphone"``, ``"photo_library"``,
``"location_when_in_use"``, ``"contacts"``, ``"notifications"``. The
full list is [`RUNTIME_PERMISSIONS`][pythonnative.native_modules.permissions.RUNTIME_PERMISSIONS];
capabilities that have no runtime prompt (``vibration``,
``background_fetch``, ...) are declared in the config only. A name
outside the list raises ``ValueError`` before anything reaches native.

Example:
    ```python
    import pythonnative as pn

    async def scan():
        if await pn.Permissions.request("camera") != "granted":
            return
        await pn.Camera.take_photo()
    ```
"""

from __future__ import annotations

from typing import Literal

from .registry import native_module

PermissionStatus = Literal["granted", "denied", "blocked", "undetermined"]
"""Outcome of a check or request."""

PermissionName = Literal[
    "camera",
    "microphone",
    "photo_library",
    "location_when_in_use",
    "contacts",
    "notifications",
]
"""A capability that has a runtime prompt; the same names as ``[permissions]`` in ``pythonnative.toml``."""

GRANTED: PermissionStatus = "granted"
DENIED: PermissionStatus = "denied"
BLOCKED: PermissionStatus = "blocked"
UNDETERMINED: PermissionStatus = "undetermined"

_STATUSES = (GRANTED, DENIED, BLOCKED, UNDETERMINED)

RUNTIME_PERMISSIONS = (
    "camera",
    "microphone",
    "photo_library",
    "location_when_in_use",
    "contacts",
    "notifications",
)
"""Every permission name ``check`` / ``request`` accept, in the ``[permissions]`` vocabulary."""


def _coerce(value: object) -> PermissionStatus:
    status = str(value) if value is not None else UNDETERMINED
    return status if status in _STATUSES else UNDETERMINED


def _validate(permission: str) -> str:
    if permission not in RUNTIME_PERMISSIONS:
        raise ValueError(
            f"Unknown permission {permission!r}. Use one of {', '.join(RUNTIME_PERMISSIONS)} "
            "(the same names as [permissions] in pythonnative.toml)."
        )
    return permission


class Permissions:
    """Runtime permission interface.

    Raises:
        ValueError: For a permission name outside
            [`RUNTIME_PERMISSIONS`][pythonnative.native_modules.permissions.RUNTIME_PERMISSIONS].
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def check(permission: PermissionName) -> PermissionStatus:
        """Return the current status of ``permission`` without prompting."""
        return _coerce(native_module("Permissions").call("check", permission=_validate(permission)))

    @staticmethod
    async def request(permission: PermissionName) -> PermissionStatus:
        """Prompt for ``permission`` (if needed) and return the result.

        Off device (``pn preview``, tests) the answer is always
        ``"undetermined"``: there is no prompt to show.
        """
        return _coerce(await native_module("Permissions").call_async("request", permission=_validate(permission)))
