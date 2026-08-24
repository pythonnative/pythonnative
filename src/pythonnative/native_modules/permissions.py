"""Runtime permission checks and requests.

[`Permissions`][pythonnative.Permissions] normalizes the very different
iOS and Android permission models behind two calls:

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

import asyncio
from typing import Any, Callable, Dict

from ..runtime import resolve_future
from ..utils import IS_ANDROID, IS_IOS

PermissionStatus = str
PermissionName = str

GRANTED = "granted"
DENIED = "denied"
BLOCKED = "blocked"
UNDETERMINED = "undetermined"

# PythonNative permission name -> Android manifest permission string.
_ANDROID_PERMS: Dict[str, str] = {
    "camera": "android.permission.CAMERA",
    "microphone": "android.permission.RECORD_AUDIO",
    "location": "android.permission.ACCESS_FINE_LOCATION",
    "contacts": "android.permission.READ_CONTACTS",
    "notifications": "android.permission.POST_NOTIFICATIONS",
    "photos": "android.permission.READ_MEDIA_IMAGES",
}


class Permissions:
    """Runtime permission interface."""

    @staticmethod
    def check(permission: PermissionName) -> PermissionStatus:
        """Return the current status of ``permission`` without prompting."""
        if IS_ANDROID:
            return _android_check(permission)
        if IS_IOS:
            return _ios_check(permission)
        return UNDETERMINED

    @staticmethod
    async def request(permission: PermissionName) -> PermissionStatus:
        """Prompt for ``permission`` (if needed) and return the result."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[PermissionStatus] = loop.create_future()

        def _done(status: PermissionStatus) -> None:
            resolve_future(future, status)

        if IS_ANDROID:
            _android_request(permission, _done)
        elif IS_IOS:
            _ios_request(permission, _done)
        else:
            _done(UNDETERMINED)

        return await future


# ======================================================================
# Android
# ======================================================================

_android_pending: Dict[int, Callable[[PermissionStatus], None]] = {}
_android_next_code = 60001


def _android_check(permission: str) -> PermissionStatus:
    manifest = _ANDROID_PERMS.get(permission)
    if manifest is None:
        return UNDETERMINED
    try:
        from java import jclass

        from ..utils import get_android_context

        PackageManager = jclass("android.content.pm.PackageManager")
        ctx = get_android_context()
        granted = ctx.checkSelfPermission(manifest) == PackageManager.PERMISSION_GRANTED
        return GRANTED if granted else DENIED
    except Exception:
        return UNDETERMINED


def _android_request(permission: str, on_done: Callable[[PermissionStatus], None]) -> None:
    manifest = _ANDROID_PERMS.get(permission)
    if manifest is None:
        on_done(UNDETERMINED)
        return
    if _android_check(permission) == GRANTED:
        on_done(GRANTED)
        return
    try:
        global _android_next_code
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Activity = jclass("android.app.Activity")
        if not Activity.isInstance(ctx):
            on_done(_android_check(permission))
            return
        code = _android_next_code
        _android_next_code += 1
        _android_pending[code] = on_done
        ctx.requestPermissions([manifest], code)
    except Exception:
        on_done(_android_check(permission))


def deliver_android_permission_result(request_code: int, permissions: Any, grant_results: Any) -> bool:
    """Forward an ``onRequestPermissionsResult`` to the pending coroutine."""
    cb = _android_pending.pop(request_code, None)
    if cb is None:
        return False
    status = DENIED
    try:
        del permissions
        if grant_results is not None and len(grant_results) > 0 and grant_results[0] == 0:
            status = GRANTED
    except Exception:
        status = DENIED
    try:
        cb(status)
    except Exception:
        pass
    return True


# ======================================================================
# iOS
# ======================================================================


def _ios_media_status(media_type: str) -> PermissionStatus:
    from rubicon.objc import ObjCClass

    AVCaptureDevice = ObjCClass("AVCaptureDevice")
    status = AVCaptureDevice.authorizationStatusForMediaType_(media_type)
    # 0 notDetermined, 1 restricted, 2 denied, 3 authorized
    return {0: UNDETERMINED, 1: BLOCKED, 2: DENIED, 3: GRANTED}.get(int(status), UNDETERMINED)


def _ios_check(permission: str) -> PermissionStatus:
    try:
        if permission == "camera":
            return _ios_media_status("vide")
        if permission == "microphone":
            return _ios_media_status("soun")
        if permission == "photos":
            from rubicon.objc import ObjCClass

            status = ObjCClass("PHPhotoLibrary").authorizationStatus()
            return {0: UNDETERMINED, 1: BLOCKED, 2: DENIED, 3: GRANTED, 4: GRANTED}.get(int(status), UNDETERMINED)
        if permission == "location":
            from rubicon.objc import ObjCClass

            status = ObjCClass("CLLocationManager").authorizationStatus()
            return {0: UNDETERMINED, 1: BLOCKED, 2: DENIED, 3: GRANTED, 4: GRANTED}.get(int(status), UNDETERMINED)
    except Exception:
        return UNDETERMINED
    return UNDETERMINED


def _ios_request(permission: str, on_done: Callable[[PermissionStatus], None]) -> None:
    try:
        from rubicon.objc import Block, ObjCClass

        if permission in ("camera", "microphone"):
            media = "vide" if permission == "camera" else "soun"
            AVCaptureDevice = ObjCClass("AVCaptureDevice")

            def _granted(ok: bool) -> None:
                on_done(GRANTED if ok else DENIED)

            AVCaptureDevice.requestAccessForMediaType_completionHandler_(media, Block(_granted, None, bool))
            return

        if permission == "photos":
            PHPhotoLibrary = ObjCClass("PHPhotoLibrary")

            def _photos_done(status: int) -> None:
                # 0 notDetermined, 1 restricted, 2 denied, 3 authorized,
                # 4 limited (counts as granted).
                on_done({0: UNDETERMINED, 1: BLOCKED, 2: DENIED, 3: GRANTED, 4: GRANTED}.get(int(status), UNDETERMINED))

            PHPhotoLibrary.requestAuthorization_(Block(_photos_done, None, int))
            return

        if permission == "notifications":
            center = ObjCClass("UNUserNotificationCenter").currentNotificationCenter()

            def _notif_done(granted: bool, _error: Any) -> None:
                on_done(GRANTED if granted else DENIED)

            # 0x07 = badge | sound | alert.
            center.requestAuthorizationWithOptions_completionHandler_(0x07, Block(_notif_done, None, bool, object))
            return
    except Exception:
        pass
    # Fall back to reporting the current status for permissions whose
    # request flow isn't wired up natively (location needs a
    # CLLocationManager delegate; use the Location module's own
    # request path for that).
    on_done(_ios_check(permission))
