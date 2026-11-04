# Notifications

`pythonnative.notifications` schedules local notifications and tells the app when
one arrives or gets tapped. On iOS it uses `UNUserNotificationCenter`. On Android it
uses `NotificationManager` and `AlarmManager`.

## Setup

```toml
[plugins]
use = ["notifications"]

[permissions]
notifications = true

[plugins.notifications]
android_icon = "assets/notification.png"  # optional
```

A build without `notifications` under `[permissions]` fails and names the line to
add. On Android that entry is what declares `POST_NOTIFICATIONS`.

Android's status bar draws a notification's small icon from its alpha channel, so a
full-color app icon usually shows as a solid shape. `android_icon` takes a path to a
white-on-transparent PNG. Without one, notifications use the app's icon. Android 8.0
falls back to a system icon instead, because its System UI crashes on an adaptive
icon in a notification.

## Scheduling

```python
from pythonnative.notifications import Notifications

if await Notifications.request_permission():
    await Notifications.schedule(
        "Reminder",
        "Time for a walk!",
        delay_seconds=60,
        identifier="walk",
        data={"entry": 42},
    )
```

`schedule` returns `False` and schedules nothing when permission isn't granted.
Scheduling again with the same `identifier` replaces the pending notification.

| Method | Meaning |
| --- | --- |
| `request_permission()` | Prompts if needed. Returns whether notifications can be shown |
| `schedule(title, body, *, delay_seconds, identifier, data, badge, sound)` | Deliver after a delay |
| `cancel(identifier)` | Remove a pending or delivered notification |
| `cancel_all()` | Remove every pending and delivered notification |
| `set_badge(count)` | Set the number on the app icon (iOS) |

`Permissions.check("notifications")` and `Permissions.request("notifications")` work
when the plugin is in the build, because the plugin owns that permission name.

## Hearing about them

```python
from pythonnative.notifications import Notifications

def open_entry(response) -> None:
    navigate_to(response.data["entry"])

if launch := Notifications.last_response():
    open_entry(launch)
unsubscribe = Notifications.on_response(open_entry)
```

- `on_received(callback)` runs for each notification that arrives while the app is
  in the foreground. It gets a `ReceivedNotification`, and the notification still
  appears. In the background the system shows it without telling the app.
- `on_response(callback)` runs when the user taps one. It gets a
  `NotificationResponse` with `identifier`, `title`, `body`, `data`, and `action`.
- `last_response()` returns the tap that launched the app from cold, for the whole
  life of the process.

## Early events

Python starts after the app does, and an app subscribes later still, from a screen's
effect. So native code holds these events while nobody is subscribed, up to the 64
most recent of each kind, and hands them to the first subscriber.

That covers the launching tap, so an app that only uses `on_response` doesn't miss
it. An app that reads `last_response` first claims that tap and won't see it again
through `on_response`. Read first and then subscribe, as above, and each tap is
handled once. Subscribing first delivers the tap to both.

## Platform differences

| | iOS | Android |
| --- | --- | --- |
| Permission prompt | Always, the first time | Android 13 (API 33) and up. Below that, `request_permission` reports whether notifications are enabled |
| `set_badge` | Sets the icon's number | Raises `NativeModuleError` with the code `unsupported`: there's no such API |
| `badge` on `schedule` | Sets the icon's number on arrival | A hint that launchers showing a count may use |
| `sound=False` | No sound | Uses a separate silent channel on Android 8 and up |
| Foreground arrival | A banner | In the shade, at the channel's default importance |
| Delayed delivery | Exact | Inexact, so power management may defer it. No exact-alarm permission is needed |
| Survives process death | Yes | Yes |
| Survives reboot | Yes | No: reboot, force-stop, and removing the app clear alarms |

On Android the data of a tap arrives through the launching intent, and any installed
app can start an exported activity with such extras. Treat `data` as untrusted, as
you would a deep link.

## Verification

These ran on an iOS 26.2 simulator and an API 31 emulator:

- Scheduling, canceling, and `cancel_all`, right away and delayed. `on_received`
  fired on both.
- `set_badge` returned on iOS and raised `unsupported` on Android. The number on the
  icon itself wasn't checked.
- Tapping a notification with the app running, and from cold, with both orders of
  `last_response` and `on_response`. On iOS the taps were on real banners. On Android
  they were in the shade.
- On Android, an alarm firing after the process died, with no Python running, and a
  later launch not reporting the old tap again. On iOS, a local notification firing
  after the app was terminated, then launching it.
- Events that arrived while Python was still starting.

Android 13's prompt wasn't exercised, because the emulator runs API 31. Android 8.0's
icon fallback wasn't exercised either. Nor were the iOS 13 code paths, or any physical
device.
