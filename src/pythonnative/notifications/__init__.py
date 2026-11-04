"""Local notifications: schedule them, and hear when they arrive or get tapped.

Enable it in ``pythonnative.toml``:

```toml
[plugins]
use = ["notifications"]

[permissions]
notifications = true

[plugins.notifications]
android_icon = "assets/notification.png"  # optional; defaults to the app's icon
```

Call ``await Notifications.request_permission()`` before scheduling on either
platform. Android delayed notifications use OS-owned, inexact alarms and survive
ordinary process death. Power management may defer delivery, and reboot,
force-stop, and app removal clear them.

Events that arrive before Python subscribes wait in native code, so a tap that
launches the app reaches the first ``on_response`` subscriber, and
``last_response()`` answers during the first render.

Example:
    ```python
    from pythonnative.notifications import Notifications, NotificationResponse

    def open_entry(response: NotificationResponse) -> None:
        navigate_to(response.data["entry"])

    if launch := Notifications.last_response():
        open_entry(launch)
    Notifications.on_response(open_entry)

    async def remind() -> None:
        if await Notifications.request_permission():
            await Notifications.schedule(
                "Reminder",
                "Time for a walk!",
                delay_seconds=60,
                identifier="walk",
                data={"entry": 42},
            )
    ```
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Literal, Mapping, Optional, Protocol, Tuple, TypeVar

from ..native_modules.registry import native_module, on_event
from ..sdk.plugin import plugin_module

__all__ = ["NotificationResponse", "Notifications", "ReceivedNotification"]

_Event = Literal["received", "response"]
_Decoded = TypeVar("_Decoded")


@dataclass(frozen=True)
class ReceivedNotification:
    """A notification that arrived while the app was in the foreground.

    Attributes:
        identifier: The identifier it was scheduled with. A remote push has
            one the system or the push service chose.
        title: The title.
        body: The body text.
        data: The ``data`` it was scheduled with, or a push's custom keys.
    """

    identifier: str
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationResponse:
    """The user's interaction with a notification.

    Attributes:
        identifier: The identifier it was scheduled with. A remote push has
            one the system or the push service chose.
        title: The title. Empty for an Android push tapped while the app was
            in the background, because the system doesn't hand it to the app.
        body: The body text, with the same limit as ``title``.
        data: The ``data`` it was scheduled with, or a push's custom keys. The
            launching intent carries it on Android, and any installed app can
            start an activity with such an intent, so treat it as untrusted.
        action: ``"default"`` for a plain tap.
    """

    identifier: str
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    action: str = "default"


class _NotificationsService(Protocol):
    async def request_permission(self) -> bool: ...

    async def schedule(
        self,
        title: str,
        body: str = "",
        *,
        delay_seconds: float = 0.0,
        identifier: str = "default",
        data: Optional[Dict[str, Any]] = None,
        badge: Optional[int] = None,
        sound: bool = True,
    ) -> bool: ...

    async def cancel(self, identifier: str = "default") -> None: ...

    async def cancel_all(self) -> None: ...

    async def set_badge(self, count: int) -> None: ...

    def last_response(self) -> Optional[Dict[str, Any]]: ...

    def set_listening(self, event: _Event, listening: bool) -> None: ...


class _Fallback:
    """Nothing to notify off device: scheduling reports that, and tests can ``emit`` events."""

    def request_permission(self) -> bool:
        return False

    def schedule(
        self,
        title: str,
        body: str = "",
        *,
        delay_seconds: float = 0.0,
        identifier: str = "default",
        data: Optional[Dict[str, Any]] = None,
        badge: Optional[int] = None,
        sound: bool = True,
    ) -> bool:
        del title, body, delay_seconds, identifier, data, badge, sound
        return False

    def cancel(self, identifier: str = "default") -> None:
        del identifier

    def cancel_all(self) -> None:
        return None

    def set_badge(self, count: int) -> None:
        del count

    def last_response(self) -> Optional[Dict[str, Any]]:
        return None

    def set_listening(self, event: str, listening: bool) -> None:
        del event, listening


plugin_module(
    "Notifications",
    _NotificationsService,
    plugin="notifications",
    events={"received": Dict[str, Any], "response": Dict[str, Any]},
    fallback=_Fallback,
    platforms={"set_badge": ["ios"]},
)

_counts: Dict[Tuple[str, str], int] = {}
_counts_lock = threading.Lock()


def _subscribe(
    module: str, event: str, decode: Callable[[Any], _Decoded], callback: Callable[[_Decoded], None]
) -> Callable[[], None]:
    """Subscribe to a buffered event, telling native while anyone is listening.

    Native holds these events while nobody listens, so the first subscriber
    gets what arrived before it, including during a launch.
    """
    key = (module, event)
    remove = on_event(module, event, lambda payload: callback(decode(payload)))
    with _counts_lock:
        _counts[key] = _counts.get(key, 0) + 1
        first = _counts[key] == 1
    subscribed = True

    def unsubscribe() -> None:
        nonlocal subscribed
        if not subscribed:
            return
        subscribed = False
        remove()
        with _counts_lock:
            _counts[key] -= 1
            last = _counts[key] == 0
        if last:
            native_module(module).call("set_listening", event=event, listening=False)

    if first:
        try:
            native_module(module).call("set_listening", event=event, listening=True)
        except Exception:
            subscribed = False
            remove()
            with _counts_lock:
                _counts[key] -= 1
            raise
    return unsubscribe


def _received(payload: Mapping[str, Any]) -> ReceivedNotification:
    return ReceivedNotification(
        identifier=str(payload.get("identifier", "")),
        title=str(payload.get("title") or ""),
        body=str(payload.get("body") or ""),
        data=dict(payload.get("data") or {}),
    )


def _response(payload: Mapping[str, Any]) -> NotificationResponse:
    return NotificationResponse(
        identifier=str(payload.get("identifier", "")),
        title=str(payload.get("title") or ""),
        body=str(payload.get("body") or ""),
        data=dict(payload.get("data") or {}),
        action=str(payload.get("action") or "default"),
    )


class Notifications:
    """Local notification interface.

    Raises:
        NativeModuleError: If the native module fails, or with the code
            ``plugin_not_enabled`` when ``notifications`` isn't in the build.
    """

    @staticmethod
    async def request_permission() -> bool:
        """Request notification permission from the user.

        Android 13 (API 33) and up show the ``POST_NOTIFICATIONS`` prompt if
        the user hasn't decided. Below that, this reports whether notifications
        are enabled for the app, without prompting.

        Returns:
            ``True`` if notifications can be shown, ``False`` if the user
            declined (always ``False`` off device).
        """
        return bool(await native_module("Notifications").call_async("request_permission"))

    @staticmethod
    async def schedule(
        title: str,
        body: str = "",
        *,
        delay_seconds: float = 0,
        identifier: str = "default",
        data: Optional[Mapping[str, Any]] = None,
        badge: Optional[int] = None,
        sound: bool = True,
    ) -> bool:
        """Schedule a local notification, replacing a pending one with the same identifier.

        Args:
            title: Notification title.
            body: Notification body text.
            delay_seconds: Seconds from now until delivery. ``0`` delivers
                right away.
            identifier: Stable ID that
                [`cancel`][pythonnative.notifications.Notifications.cancel]
                targets and that listeners receive.
            data: JSON-compatible values handed back in
                [`NotificationResponse.data`][pythonnative.notifications.NotificationResponse].
            badge: On iOS, the number to put on the app icon when it arrives.
                On Android, the count launchers that show one may use.
            sound: Whether to play the default notification sound.

        Returns:
            ``True`` once scheduled, ``False`` if notification permission
            isn't granted (so nothing was scheduled).

        Raises:
            ValueError: If ``delay_seconds`` isn't finite and nonnegative, or
                ``badge`` is negative.
        """
        if not math.isfinite(delay_seconds) or delay_seconds < 0:
            raise ValueError("delay_seconds must be finite and nonnegative")
        if badge is not None and badge < 0:
            raise ValueError("badge must be nonnegative")
        result = await native_module("Notifications").call_async(
            "schedule",
            title=title,
            body=body,
            delay_seconds=float(delay_seconds),
            identifier=identifier,
            data=None if data is None else dict(data),
            badge=badge,
            sound=sound,
        )
        return bool(result)

    @staticmethod
    async def cancel(identifier: str = "default") -> None:
        """Cancel a notification by identifier, pending or delivered (a no-op when there's none)."""
        await native_module("Notifications").call_async("cancel", identifier=identifier)

    @staticmethod
    async def cancel_all() -> None:
        """Cancel every pending notification and remove every delivered one."""
        await native_module("Notifications").call_async("cancel_all")

    @staticmethod
    async def set_badge(count: int) -> None:
        """Set the number on the app icon, where ``0`` clears it.

        iOS only: Android has no API that sets a launcher badge. Pass ``badge``
        to [`schedule`][pythonnative.notifications.Notifications.schedule] there.

        Raises:
            NativeModuleError: With the code ``unsupported`` on Android.
            ValueError: If ``count`` is negative.
        """
        if count < 0:
            raise ValueError("count must be nonnegative")
        await native_module("Notifications").call_async("set_badge", count=count)

    @staticmethod
    def on_received(callback: Callable[[ReceivedNotification], None]) -> Callable[[], None]:
        """Call ``callback`` for each notification that arrives while the app is in the foreground.

        The notification still appears, as a banner on iOS and in the shade on
        Android. In the background the system shows it without telling the app.
        Arrivals from before the first subscriber are delivered to it.

        Args:
            callback: Receives a
                [`ReceivedNotification`][pythonnative.notifications.ReceivedNotification].

        Returns:
            A zero-argument function that unsubscribes.
        """
        return _subscribe("Notifications", "received", _received, callback)

    @staticmethod
    def on_response(callback: Callable[[NotificationResponse], None]) -> Callable[[], None]:
        """Call ``callback`` each time the user taps a notification.

        Taps from before the first subscriber are delivered to it, including
        the one that launched the app, unless
        [`last_response`][pythonnative.notifications.Notifications.last_response]
        already returned that tap. So read ``last_response`` first and then
        subscribe, and each tap is handled once.

        Args:
            callback: Receives a
                [`NotificationResponse`][pythonnative.notifications.NotificationResponse].

        Returns:
            A zero-argument function that unsubscribes.
        """
        return _subscribe("Notifications", "response", _response, callback)

    @staticmethod
    def last_response() -> Optional[NotificationResponse]:
        """Return the tap that launched the app from cold, if one did.

        It keeps returning that tap for the life of the process, so a screen
        can read it during its first render. Later taps go to
        [`on_response`][pythonnative.notifications.Notifications.on_response].

        Returns:
            The launching tap, or ``None`` when the app started any other way.
        """
        payload = native_module("Notifications").call("last_response")
        return _response(payload) if isinstance(payload, dict) else None
