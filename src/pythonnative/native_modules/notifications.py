"""Local notifications and remote push registration.

Coroutines for requesting permission and scheduling / cancelling local
notifications, backed by the native ``Notifications`` module
(``UNUserNotificationCenter`` on iOS, ``NotificationManager`` on
Android).

Call ``await Notifications.request_permission()`` before scheduling on either
platform. Android 13+ requests ``POST_NOTIFICATIONS``; scheduling returns
``False`` when notifications aren't enabled. Android delayed notifications use
OS-owned, inexact alarms and survive ordinary process death. Delivery may be
deferred by power management. Reboot, force-stop, and app removal clear alarms.

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

from typing import Optional

from .registry import native_module


class Notifications:
    """Local notification interface."""

    @staticmethod
    async def request_permission() -> bool:
        """Request notification permission from the user.

        On Android 12 and below the manifest declaration is sufficient
        and this returns ``True`` without prompting. On Android 13+
        (API 33) the ``POST_NOTIFICATIONS`` runtime permission prompt
        is shown if the user hasn't decided yet.

        Returns:
            ``True`` if granted (or no prompt is needed), ``False`` if
            the user declined (always ``False`` off device).

        Raises:
            NativeModuleError: If the native module fails.
        """
        return bool(await native_module("Notifications").call_async("request_permission"))

    @staticmethod
    async def schedule(
        title: str,
        body: str = "",
        *,
        delay_seconds: float = 0,
        identifier: str = "default",
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

        Returns:
            ``True`` once scheduled, ``False`` if the user has denied
            notification permission (so nothing was scheduled).

        Raises:
            NativeModuleError: If the native module fails.
        """
        result = await native_module("Notifications").call_async(
            "schedule",
            title=title,
            body=body,
            delay_seconds=float(delay_seconds),
            identifier=identifier,
        )
        return bool(result)

    @staticmethod
    async def cancel(identifier: str = "default") -> None:
        """Cancel a pending notification by its identifier (a no-op when none is pending)."""
        await native_module("Notifications").call_async("cancel", identifier=identifier)

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
            remote push support (Android and off device).

        Raises:
            NativeModuleError: If APNs registration fails; ``code`` is
                ``"apns"`` and the message carries the system's error.
        """
        token = await native_module("Notifications").call_async("get_device_token")
        return str(token) if token else None
