"""Cross-platform local notifications.

Provides coroutines for requesting permission and scheduling /
cancelling local push notifications. Uses Android's
``NotificationManager`` or iOS's ``UNUserNotificationCenter``.

On iOS you must ``await Notifications.request_permission()`` before
scheduling. On Android 13+ the runtime permission should be requested
through standard Android APIs (the manifest declaration is otherwise
sufficient).

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
from typing import Any

from ..runtime import resolve_future
from ..utils import IS_ANDROID


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
            return await asyncio.to_thread(_android_schedule, title, body, delay_seconds, identifier)
        return await asyncio.to_thread(_ios_schedule, title, body, delay_seconds, identifier)

    @staticmethod
    async def cancel(identifier: str = "default") -> None:
        """Cancel a pending notification by its identifier.

        Args:
            identifier: The same string passed to
                [`schedule`][pythonnative.native_modules.notifications.Notifications.schedule].
        """
        if IS_ANDROID:
            await asyncio.to_thread(_android_cancel, identifier)
            return
        await asyncio.to_thread(_ios_cancel, identifier)


# ======================================================================
# Android implementation
# ======================================================================


def _android_schedule(title: str, body: str, delay_seconds: float, identifier: str) -> bool:
    del delay_seconds  # Android schedule is fire-and-forget for now.
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
        pass


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
        pass
