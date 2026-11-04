# Push

`pythonnative.push` registers for remote push and reports tokens and messages. iOS
uses APNs and Android uses Firebase Cloud Messaging (FCM). The
[`notifications`](notifications.md) capability presents pushes and reports taps, so
push requires it.

## Setup

```toml
[plugins]
use = ["notifications", "push"]

[permissions]
notifications = true
remote_notifications = true

[plugins.push]
google_services_file = "google-services.json"
```

On iOS, `remote_notifications` adds the `aps-environment` entitlement and the
`remote-notification` background mode. Your signing identity's App ID needs the Push
Notifications capability, and your server needs an APNs key.

On Android, `google_services_file` adds the Google Services Gradle plugin and copies
the file to `app/google-services.json`. Download it from the Firebase console for
your app's ID. Without it the app still builds and launches, and `get_device_token`
raises `NativeModuleError` with the code `not_configured`.

## API

```python
from pythonnative.push import Push, PushMessage

def handle(message: PushMessage) -> None:
    print(message.title, message.body, message.data)

Push.on_message(handle)
Push.on_token(send_token_to_server)

async def register() -> None:
    send_token_to_server(await Push.get_device_token())
```

| Member | Meaning |
| --- | --- |
| `await get_device_token()` | The APNs or FCM token. `None` off device |
| `on_token(callback)` | Each new token. Subscribing registers with APNs on iOS |
| `on_message(callback)` | Each remote message the app gets to process |

`get_device_token` raises `NativeModuleError` with these codes:

| Code | Meaning |
| --- | --- |
| `not_configured` | Android, with no `google_services_file` built in |
| `apns` | APNs refused the registration, or didn't answer within 30 seconds |
| `fcm` | FCM couldn't issue a token |

Call `Notifications.request_permission()` first, because a push can't show anything
without it.

## Which callback runs

| The push | Foreground | Background or no process |
| --- | --- | --- |
| Visible | `on_message` and `Notifications.on_received`, and it appears | The system shows it, and nothing runs until a tap |
| Silent (`content-available` on iOS, a data message on Android) | `on_message` | `on_message` |
| Tapped | `Notifications.on_response` | `Notifications.on_response`, or `last_response` from cold |

A message that starts the process has no screen. Android starts Python on FCM's
worker thread, and on iOS the app's normal launch starts it. Either way Python
imports your entry module first, so subscribe at its top level to hear these. Native
code holds messages and tokens until the first subscriber, so nothing is lost if you
subscribe later, once a screen appears.

## Platform differences

- FCM delivers every `data` value as a string. APNs keeps JSON types.
- iOS allows 5 seconds of work after a background message, which is a choice here and
  below the 30 the OS allows. Android's limit belongs to FCM's service.
- An Android push tapped from the background reaches `on_response` with an empty
  `title` and `body`, because the system doesn't hand them to the app. `identifier` is
  the FCM message ID, and `data` has the custom keys.
- `Push.on_token` fires on iOS after each launch's registration only when the token
  changed. FCM calls it when it issues or rotates one.

## Verification

Delivery from real services wasn't tested. That takes an APNs key and a device on iOS,
and a Firebase project on Android, and no credentials were available. These parts ran
on an iOS 26.2 simulator and an API 31 emulator:

- iOS, with `xcrun simctl push`: a visible push in the foreground and the background,
  a tap on its banner with the app running and from cold, and a push sent while Python
  was still starting. The simulator also returned a token, 80 bytes against a real
  device's 32, which APNs won't accept. A simulator on an older host fails instead,
  with the code `apns`.
- iOS `didReceiveRemoteNotification`: `simctl` turns a `content-available` push into a
  background fetch, and it refuses unless the app also has `background_fetch` under
  `[permissions]`. So a test-only hook called `PNAppLifecycle` directly, with the app
  running and before Python started.
- Android without a file: the app launched, and `get_device_token` raised
  `not_configured`.
- Android with a syntactically valid, fake `google-services.json`: the Gradle plugin
  and the copy applied, Firebase initialized, and `get_device_token` raised `fcm` when
  the server refused the key.
- Android's service: a test-only receiver handed a message to Firebase's own service
  starter, which called `onMessageReceived` in the foreground. That produced
  `on_message`, `on_received`, and a posted notification.
- Android with no activity: from a stopped process, a test-only receiver delivered a
  message the way the service does. Python started, imported the entry module, and
  `on_message` ran, with no activity in the process.
- Android's tap on a system-posted FCM notification: `adb shell am start` with the
  extras FCM uses, warm and cold.

Before shipping, send a real push to a real device on each platform.
