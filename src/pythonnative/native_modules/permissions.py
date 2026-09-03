"""Runtime permission checks and requests.

[`Permissions`][pythonnative.Permissions] normalizes the very different
iOS and Android permission models behind two calls, both served by the
native ``Permissions`` module:

- ``check(permission)``: synchronous, returns a status string without
  prompting.
- ``request(permission)``: a coroutine that shows the system prompt
  (if needed) and resolves to the resulting status.

Statuses are ``"granted"``, ``"denied"``, ``"blocked"`` (denied with
"don't ask again" / Settings required), or ``"undetermined"``.

Supported ``permission`` names: ``"camera"``, ``"microphone"``,
``"location"``, ``"photos"``, ``"notifications"``, ``"contacts"``.
Unknown names resolve to ``"undetermined"``.
"""

from __future__ import annotations

from .registry import native_module

PermissionStatus = str
PermissionName = str

GRANTED = "granted"
DENIED = "denied"
BLOCKED = "blocked"
UNDETERMINED = "undetermined"

_STATUSES = (GRANTED, DENIED, BLOCKED, UNDETERMINED)

PERMISSION_NAMES = ("camera", "microphone", "location", "photos", "notifications", "contacts")
"""Permission names understood by every platform."""


def _coerce(value: object) -> PermissionStatus:
    status = str(value) if value is not None else UNDETERMINED
    return status if status in _STATUSES else UNDETERMINED


class Permissions:
    """Runtime permission interface."""

    @staticmethod
    def check(permission: PermissionName) -> PermissionStatus:
        """Return the current status of ``permission`` without prompting."""
        try:
            return _coerce(native_module("Permissions").call("check", permission=permission))
        except Exception:
            return UNDETERMINED

    @staticmethod
    async def request(permission: PermissionName) -> PermissionStatus:
        """Prompt for ``permission`` (if needed) and return the result."""
        try:
            return _coerce(await native_module("Permissions").call_async("request", permission=permission))
        except Exception:
            return UNDETERMINED
