# Capabilities

A capability is device functionality an app opts into: video, push, maps, and so on. Each one
ships inside the `pythonnative` package, and only the ones you list are compiled into your app.

```toml
[plugins]
use = ["camera", "maps", "notifications"]

[permissions]
camera = "Scan receipts with your camera."
notifications = true
```

```python
from pythonnative.camera import CameraView
from pythonnative.maps import MapView, Marker
from pythonnative.notifications import Notifications
```

| Capability | What it gives you | Needs under `[permissions]` |
| --- | --- | --- |
| [`audio`](audio.md) | Sound playback and recording | `microphone`, to record |
| [`background`](background.md) | Periodic work while the app isn't open | |
| [`biometrics`](biometrics.md) | Face ID, Touch ID, and fingerprint prompts | `face_id` |
| [`camera`](camera.md) | A live camera view, photo and video capture, and barcodes | `camera` |
| [`location`](location.md) | A position fix, or a stream of them | `location_when_in_use` |
| [`maps`](maps.md) | Native maps with markers and lines | |
| [`notifications`](notifications.md) | Local notifications, with handlers for receiving and tapping | `notifications` |
| [`pickers`](pickers.md) | System image, video, and document pickers | |
| [`purchases`](purchases.md) | In-app purchases | |
| [`push`](push.md) | Remote push through APNs and Firebase | `remote_notifications` |
| [`sensors`](sensors.md) | Accelerometer, gyroscope, magnetometer, and barometer | `motion` |
| [`video`](video.md) | A native video player | |

## Why they're opt-in

Compiling everything into every app has a cost beyond size. An app whose binary references the camera
API must explain why in its `Info.plist`, even if it never opens the camera, and App Review notices. So
an app that doesn't list `camera` doesn't contain a line of camera code. CI enforces this
with a project that enables nothing.

## When a capability isn't in the build

Importing a capability's Python package always works, so shared code and tests don't need to care.
Using it on a device whose build left it out fails with a message that says what to do:

```text
NativeModuleError: Camera.take_photo: the 'camera' capability isn't in this build. Add 'camera' to
[plugins].use in pythonnative.toml and rebuild.
```

The error's `code` is `plugin_not_enabled`. After changing `use`, run `pn run ios` or `pn run android`:
native code can't be delivered over Fast Refresh.

## In PythonNative Go

Go carries every capability except `push`, whose tokens belong to your app's own bundle ID and Firebase project.
A project that uses `push` runs in its own debug build, and `pn start` tells you so.

## Off device

Every capability has a Python fallback, so tests and the browser preview run the same code. Fallbacks return
safe values, such as `None` for a location fix. The preview implements what a browser can honor,
such as `Video`, `Sound`, and location through the browser's own APIs.

## Writing your own

Capabilities use nothing private. [Native plugins](../native-plugins.md) covers the same format for your
own packages.
