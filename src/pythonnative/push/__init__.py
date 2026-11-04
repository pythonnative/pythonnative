"""Remote push: the device token your server needs, and the messages it sends.

Requires the ``notifications`` capability, which presents pushes and reports
taps. iOS uses APNs. Android uses Firebase Cloud Messaging and needs your
project's ``google-services.json``:

```toml
[plugins]
use = ["notifications", "push"]

[permissions]
notifications = true
remote_notifications = true

[plugins.push]
google_services_file = "google-services.json"
```

Without that file an Android app still builds and launches, and
``get_device_token`` raises ``NativeModuleError`` with the code
``not_configured``.

Example:
    ```python
    from pythonnative.push import Push, PushMessage

    def handle(message: PushMessage) -> None:
        print(message.title, message.data)

    Push.on_message(handle)
    Push.on_token(send_token_to_server)

    async def register() -> None:
        send_token_to_server(await Push.get_device_token())
    ```

Subscribe at the top of your entry module to hear a message that starts the app
with no screen, as Python's startup imports that module first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Literal, Mapping, Optional, Protocol

from ..native_modules.registry import native_module
from ..notifications import _subscribe
from ..sdk.plugin import plugin_module

__all__ = ["Push", "PushMessage"]

_Event = Literal["token", "message"]


@dataclass(frozen=True)
class PushMessage:
    """A remote message the app received.

    Attributes:
        title: The visible title, when it has one.
        body: The visible body, when it has one.
        data: The server's custom keys. FCM delivers every value as a string.
    """

    title: Optional[str] = None
    body: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class _PushService(Protocol):
    async def get_device_token(self) -> Optional[str]: ...

    def set_listening(self, event: _Event, listening: bool) -> None: ...


class _Fallback:
    """No push service off device: no token, and tests can ``emit`` events."""

    def get_device_token(self) -> Optional[str]:
        return None

    def set_listening(self, event: str, listening: bool) -> None:
        del event, listening


plugin_module(
    "Push",
    _PushService,
    plugin="push",
    events={"token": str, "message": Dict[str, Any]},
    fallback=_Fallback,
)


def _message(payload: Mapping[str, Any]) -> PushMessage:
    title, body = payload.get("title"), payload.get("body")
    return PushMessage(
        title=None if title is None else str(title),
        body=None if body is None else str(body),
        data=dict(payload.get("data") or {}),
    )


class Push:
    """Remote push interface.

    Raises:
        NativeModuleError: If the native module fails, or with the code
            ``plugin_not_enabled`` when ``push`` isn't in the build.
    """

    @staticmethod
    async def get_device_token() -> Optional[str]:
        """Register for remote push and return this device's token.

        On iOS it's a lowercase hex APNs token, and on Android an FCM
        registration token. A simulator without APNs access can't get one.

        Returns:
            The token, or ``None`` off device.

        Raises:
            NativeModuleError: With the code ``not_configured`` on Android
                when no ``google_services_file`` was built in, ``apns`` when
                APNs registration fails or doesn't answer within 30 seconds,
                or ``fcm`` when FCM can't issue a token.
        """
        token = await native_module("Push").call_async("get_device_token")
        return str(token) if token else None

    @staticmethod
    def on_token(callback: Callable[[str], None]) -> Callable[[], None]:
        """Call ``callback`` with each new token, so your server stays current.

        Subscribing registers for remote push on iOS. A token issued before
        the first subscriber is delivered to it.

        Args:
            callback: Receives the token string.

        Returns:
            A zero-argument function that unsubscribes.
        """
        return _subscribe("Push", "token", str, callback)

    @staticmethod
    def on_message(callback: Callable[[PushMessage], None]) -> Callable[[], None]:
        """Call ``callback`` for each remote message the app gets to process.

        - In the foreground, every push.
        - In the background, or with no process running, a silent push: one
          with ``content-available`` on iOS, or a data message on Android. The
          OS shows a visible push by itself and tells the app only if it's
          tapped, through
          [`Notifications.on_response`][pythonnative.notifications.Notifications.on_response].

        A message from before the first subscriber is delivered to it.

        Args:
            callback: Receives a [`PushMessage`][pythonnative.push.PushMessage].

        Returns:
            A zero-argument function that unsubscribes.
        """
        return _subscribe("Push", "message", _message, callback)
