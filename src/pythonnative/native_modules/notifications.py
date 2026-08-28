"""Cross-platform local notifications and remote push registration.

Provides coroutines for requesting permission and scheduling /
cancelling local push notifications. Uses Android's
``NotificationManager`` or iOS's ``UNUserNotificationCenter``.

On iOS you must ``await Notifications.request_permission()`` before
scheduling. On Android 13+ the runtime permission should be requested
through standard Android APIs (the manifest declaration is otherwise
sufficient).

For remote (server-sent) pushes, enable the ``remote_notifications``
capability in ``pythonnative.toml`` and call
``Notifications.get_device_token()`` to register with APNs and receive
the device token your server needs. Android remote push requires
Firebase Cloud Messaging, which needs a per-app ``google-services.json``
and is not wired up by the built-in module; ``get_device_token`` returns
``None`` there.

Example:
    ```python
    import pythonnative as pn

    async def setup_reminders():
        if not await pn.Notifications.request_permission():
            return
        await pn.Notifications.schedule(
            title="Reminder",
            body="Time for a walk!",
            delay_seconds=60,
            identifier="walk",
        )
    ```
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .. import diagnostics
from ..runtime import reject_future, resolve_future
from ..utils import IS_ANDROID, IS_IOS

# Delayed Android deliveries in flight, keyed by identifier, so
# ``cancel`` can abort a notification that hasn't posted yet. (iOS
# delivers delays natively through UNTimeIntervalNotificationTrigger.)
_android_delayed: Dict[str, "asyncio.Task[Any]"] = {}


class Notifications:
    """Local notification interface."""

    @staticmethod
    async def request_permission() -> bool:
        """Request notification permission from the user.

        On Android the manifest declaration is normally sufficient for
        legacy permission grants and this returns ``True`` without
        prompting (the runtime POST_NOTIFICATIONS prompt for Android
        13+ should be requested via standard Android APIs).

        Returns:
            ``True`` if granted (or no prompt is needed), ``False``
            otherwise.
        """
        if IS_ANDROID:
            return True
        return await _ios_request_permission()

    @staticmethod
    async def schedule(
        title: str,
        body: str = "",
        *,
        delay_seconds: float = 0,
        identifier: str = "default",
        **options: Any,
    ) -> bool:
        """Schedule a local notification.

        Args:
            title: Notification title.
            body: Notification body text.
            delay_seconds: Seconds from now until delivery. Use ``0``
                for an effectively immediate notification.
            identifier: Stable ID used by
                [`cancel`][pythonnative.native_modules.notifications.Notifications.cancel]
                to target this notification.
            **options: Reserved for future tuning (e.g., ``sound``,
                ``badge``, ``category``).

        Returns:
            ``True`` on success, ``False`` if the underlying native
            call failed.
        """
        del options
        if IS_ANDROID:
            if delay_seconds > 0:
                _cancel_android_delayed(identifier)
                _android_delayed[identifier] = asyncio.ensure_future(
                    _android_schedule_later(title, body, delay_seconds, identifier)
                )
                return True
            return await asyncio.to_thread(_android_schedule, title, body, identifier)
        return await asyncio.to_thread(_ios_schedule, title, body, delay_seconds, identifier)

    @staticmethod
    async def cancel(identifier: str = "default") -> None:
        """Cancel a pending notification by its identifier.

        Args:
            identifier: The same string passed to
                [`schedule`][pythonnative.native_modules.notifications.Notifications.schedule].
        """
        if IS_ANDROID:
            _cancel_android_delayed(identifier)
            await asyncio.to_thread(_android_cancel, identifier)
            return
        await asyncio.to_thread(_ios_cancel, identifier)

    @staticmethod
    async def get_device_token() -> Optional[str]:
        """Register for remote notifications and return the device token.

        On iOS this calls ``registerForRemoteNotifications`` and waits
        for the APNs callback; the token is a lowercase hex string your
        server passes to APNs. Requires the ``remote_notifications``
        capability (which adds the ``aps-environment`` entitlement) and
        a real device (the simulator has no APNs connection).

        Returns:
            The APNs token, or ``None`` on platforms without built-in
            remote push support (Android and desktop).

        Raises:
            RuntimeError: If APNs registration fails, with the native
                error description.
        """
        if not IS_IOS:
            return None
        return await _ios_get_device_token()


# ======================================================================
# Android implementation
# ======================================================================


def _cancel_android_delayed(identifier: str) -> None:
    pending = _android_delayed.pop(identifier, None)
    if pending is not None and not pending.done():
        pending.cancel()


async def _android_schedule_later(title: str, body: str, delay_seconds: float, identifier: str) -> None:
    """Post an Android notification after ``delay_seconds`` on the framework loop.

    The delay lives in the app process (matching the semantics of
    ``UNTimeIntervalNotificationTrigger`` closely enough for in-app
    reminders); notifications whose delay outlives the process need
    ``AlarmManager``, which is out of scope for the built-in module.
    """
    try:
        await asyncio.sleep(delay_seconds)
        await asyncio.to_thread(_android_schedule, title, body, identifier)
    finally:
        _android_delayed.pop(identifier, None)


def _android_schedule(title: str, body: str, identifier: str) -> bool:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        nm = ctx.getSystemService(jclass("android.content.Context").NOTIFICATION_SERVICE)
        channel_id = "pn_default"
        NotificationChannel = jclass("android.app.NotificationChannel")
        channel = NotificationChannel(channel_id, "PythonNative", 3)  # IMPORTANCE_DEFAULT
        nm.createNotificationChannel(channel)

        Builder = jclass("android.app.Notification$Builder")
        builder = Builder(ctx, channel_id)
        builder.setContentTitle(title)
        builder.setContentText(body)
        builder.setSmallIcon(jclass("android.R$drawable").ic_dialog_info)
        nm.notify(abs(hash(identifier)) % (2**31), builder.build())
        return True
    except Exception:
        return False


def _android_cancel(identifier: str) -> None:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        nm = ctx.getSystemService(jclass("android.content.Context").NOTIFICATION_SERVICE)
        nm.cancel(abs(hash(identifier)) % (2**31))
    except Exception:
        diagnostics.swallowed("notifications._android_cancel")


# ======================================================================
# iOS implementation
# ======================================================================


async def _ios_request_permission() -> bool:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[bool] = loop.create_future()
    try:
        from rubicon.objc import Block, ObjCClass

        center = ObjCClass("UNUserNotificationCenter").currentNotificationCenter()

        # Build a block that mirrors the UNNotificationCenter signature
        # ``void(^)(BOOL granted, NSError* error)``.
        def _completion(granted: bool, _error: Any) -> None:
            resolve_future(future, bool(granted))

        try:
            block = Block(_completion, None, bool, object)
        except Exception:
            # If Block ctor signature changed across rubicon versions,
            # fall back to optimistic "granted" without polling.
            resolve_future(future, True)
            return await future

        center.requestAuthorizationWithOptions_completionHandler_(0x07, block)
    except Exception:
        resolve_future(future, False)
    return await future


def _ios_schedule(title: str, body: str, delay_seconds: float, identifier: str) -> bool:
    try:
        from rubicon.objc import ObjCClass

        content = ObjCClass("UNMutableNotificationContent").alloc().init()
        content.setTitle_(title)
        content.setBody_(body)

        interval = float(delay_seconds) if delay_seconds > 0 else 1.0
        trigger = ObjCClass("UNTimeIntervalNotificationTrigger").triggerWithTimeInterval_repeats_(interval, False)
        request = ObjCClass("UNNotificationRequest").requestWithIdentifier_content_trigger_(
            identifier, content, trigger
        )
        center = ObjCClass("UNUserNotificationCenter").currentNotificationCenter()
        center.addNotificationRequest_withCompletionHandler_(request, None)
        return True
    except Exception:
        return False


def _ios_cancel(identifier: str) -> None:
    try:
        from rubicon.objc import ObjCClass

        center = ObjCClass("UNUserNotificationCenter").currentNotificationCenter()
        NSArray = ObjCClass("NSArray")
        arr = NSArray.arrayWithObject_(identifier)
        center.removePendingNotificationRequestsWithIdentifiers_(arr)
    except Exception:
        diagnostics.swallowed("notifications._ios_cancel")


# ----------------------------------------------------------------------
# Remote notifications (APNs)
# ----------------------------------------------------------------------
#
# The registration result arrives through UIApplicationDelegate
# callbacks in the native template, which forward here via
# dispatch_device_token / dispatch_device_token_error. The token is
# cached so later get_device_token() calls resolve immediately.

_device_token: Optional[str] = None
_device_token_error: Optional[str] = None
_token_waiters: List["asyncio.Future[str]"] = []


async def _ios_get_device_token() -> str:
    if _device_token is not None:
        return _device_token
    if _device_token_error is not None:
        raise RuntimeError(f"APNs registration failed: {_device_token_error}")

    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    _token_waiters.append(future)

    def _register() -> None:
        from rubicon.objc import ObjCClass

        ObjCClass("UIApplication").sharedApplication.registerForRemoteNotifications()

    try:
        # registerForRemoteNotifications must run on the main thread.
        from ..runtime import call_on_main_thread

        call_on_main_thread(_register)
    except Exception as exc:
        _token_waiters.remove(future)
        raise RuntimeError(f"Could not start APNs registration: {exc}") from exc
    return await future


def dispatch_device_token(token: str) -> None:
    """Deliver the APNs device token from the native host."""
    global _device_token, _device_token_error
    _device_token = token
    _device_token_error = None
    waiters, _token_waiters[:] = list(_token_waiters), []
    for future in waiters:
        resolve_future(future, token)


def dispatch_device_token_error(message: str) -> None:
    """Deliver an APNs registration failure from the native host."""
    global _device_token_error
    _device_token_error = message
    waiters, _token_waiters[:] = list(_token_waiters), []
    error = RuntimeError(f"APNs registration failed: {message}")
    for future in waiters:
        reject_future(future, error)
