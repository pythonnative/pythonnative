# Permissions

iOS and Android describe the same device permission in very different
ways: iOS wants *usage-description* strings in `Info.plist`, Android
wants `<uses-permission>` entries (and, since API 23, a runtime prompt).
PythonNative lets you declare permissions **once**, by name, in
`pythonnative.toml`, and expands each into the correct native artifacts
for both platforms.

```toml
[plugins]
use = ["camera", "location", "biometrics", "notifications"]

[permissions]
camera = "Scan receipts with your camera."
location_when_in_use = "Show nearby stores."
face_id = "Unlock the app with Face ID."
notifications = true
```

`[permissions]` describes what your app may ask for. The code that asks
lives in a [capability](capabilities/index.md), which you enable
separately with `[plugins].use`. Declaring a permission doesn't compile
any code into your app, and enabling a capability that needs a permission
fails the build until you declare it. See
[Permission providers](#permission-providers).

## Value semantics

Each permission's value can be:

| Value | Meaning |
| --- | --- |
| a **string** | The permission is declared; the string is used verbatim as the iOS permission-prompt text (the usage description). |
| **`true`** | The permission is declared using its built-in default reason. |
| **`false`** | The permission isn't declared, useful for toggling one off without deleting the line. |

!!! tip "Write a real reason"
    On iOS, App Review rejects apps whose usage strings are vague or
    missing. Prefer a concrete sentence (`"Scan receipts with your
    camera."`) over `true` for any permission that prompts the user.

Unknown names are rejected when the config is validated, so a typo like
`camara` fails fast instead of silently doing nothing.

## Permission catalog

Declaring an entry adds the listed iOS usage keys, Android permissions,
and (where relevant) iOS background modes.

| Name | What it's for | iOS usage key(s) | Android permission(s) |
| --- | --- | --- | --- |
| `camera` | Capture photos/video | `NSCameraUsageDescription` | `CAMERA` |
| `microphone` | Record audio | `NSMicrophoneUsageDescription` | `RECORD_AUDIO` |
| `photo_library` | Read photos/videos | `NSPhotoLibraryUsageDescription` | `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO` |
| `photo_library_add` | Save to photo library | `NSPhotoLibraryAddUsageDescription` | – |
| `location_when_in_use` | Foreground location | `NSLocationWhenInUseUsageDescription` | `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` |
| `location_always` | Foreground + background location | `NSLocationAlwaysAndWhenInUseUsageDescription`, `NSLocationWhenInUseUsageDescription` | `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION` |
| `contacts` | Read the address book, with your own plugin | `NSContactsUsageDescription` | `READ_CONTACTS` |
| `calendars` | Read/write calendar events, with your own plugin | `NSCalendarsUsageDescription` | `READ_CALENDAR`, `WRITE_CALENDAR` |
| `reminders` | Read/write reminders (iOS), with your own plugin | `NSRemindersUsageDescription` | – |
| `motion` | Motion / fitness data | `NSMotionUsageDescription` | `ACTIVITY_RECOGNITION` |
| `face_id` | Biometric auth | `NSFaceIDUsageDescription` | `USE_BIOMETRIC` |
| `bluetooth` | Nearby Bluetooth devices, with your own plugin | `NSBluetoothAlwaysUsageDescription` | `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` |
| `speech_recognition` | Speech recognition (iOS), with your own plugin | `NSSpeechRecognitionUsageDescription` | – |
| `notifications` | Show local notifications | – | `POST_NOTIFICATIONS` |
| `remote_notifications` | Server-sent (remote) push | – (adds the `aps-environment` entitlement and `remote-notification` background mode) | `POST_NOTIFICATIONS` |
| `vibration` | Haptics / vibration | – | `VIBRATE` |
| `background_audio` | Play audio in background | – (adds `audio` background mode) | `FOREGROUND_SERVICE` |
| `background_fetch` | Periodic background fetch | – (adds `fetch` background mode) | – |

Permissions marked "–" for a platform simply contribute nothing there.
`notifications`, `vibration`, `background_audio`, and `background_fetch`
need no iOS usage string, so declaring them as `true` is enough.

### Background modes

`location_always`, `background_audio`, `background_fetch`, and
`remote_notifications` also add the corresponding values to the iOS
`UIBackgroundModes` array (`location`, `audio`, `fetch`,
`remote-notification`) so the OS keeps your app scheduled.

### Entitlements

Some permissions need a code-signing entitlement rather than an
`Info.plist` key. Declaring `remote_notifications` generates an
`.entitlements` file with `aps-environment` and wires it into the
build, so `await Push.get_device_token()` from
[`pythonnative.push`](capabilities/push.md) can register with APNs. Release
builds exported for the App Store, ad hoc, or enterprise distribution use the
production APNs environment; every other build uses development.

## Permission providers

`pn.Permissions.check` and `request` don't know any permission on their
own. The core runtime has no reference to a privacy-sensitive framework, so
each name is provided by the plugin that uses it, and a name works only when
a plugin in the build provides it:

| Name | Provided by |
| --- | --- |
| `camera` | [`camera`](capabilities/camera.md) |
| `microphone` | [`camera`](capabilities/camera.md) or [`audio`](capabilities/audio.md) |
| `photo_library` | [`pickers`](capabilities/pickers.md) |
| `location_when_in_use` | [`location`](capabilities/location.md) |
| `motion` | [`sensors`](capabilities/sensors.md) |
| `notifications` | [`notifications`](capabilities/notifications.md) |

Any other name, or one of these without its plugin in the build, raises
[`NativeModuleError`][pythonnative.native_modules.NativeModuleError] with the
code `plugin_not_enabled`. Add the capability to `[plugins].use` and rebuild.

The catalog above still accepts names no first-party plugin provides, such
as `contacts` and `bluetooth`, so a plugin of your own can declare and provide
them with `PNPermissions.register`. See
[Native plugins](native-plugins.md#permissions).

A capability that needs a permission says so in its manifest, and the build
checks it: enabling `camera` without a `camera` entry under `[permissions]`
fails the build, because iOS crashes an app that reaches a protected API
without its usage string. Each [capability's guide](capabilities/index.md)
lists what it needs.

## Always-on permissions

Every app receives three install-time Android permissions automatically,
because almost every PythonNative app needs the network (`fetch`,
`use_query`, `NetInfo`, remote images) and the built-in `Haptics` module
vibrates:

- `android.permission.INTERNET`
- `android.permission.ACCESS_NETWORK_STATE`
- `android.permission.VIBRATE`

These never prompt the user and require no declaration. Runtime
permissions, such as `POST_NOTIFICATIONS` for notifications, come only
from what you declare.

## Adding raw Android permissions

For anything not in the catalog, append raw permission strings via
`[android].permissions`. They're merged (de-duplicated) with the
derived set:

```toml
[android]
permissions = ["com.android.alarm.permission.SET_ALARM"]
```

## How it maps to native files

When you run `pn run` or `pn build`, the configurators write:

- **iOS**: each usage key/string pair into `Info.plist`, plus a
  `UIBackgroundModes` array when any background-capable entry is
  declared.
- **Android**: a `<uses-permission android:name="…"/>` element into
  `AndroidManifest.xml` for every resolved permission.

=== "Info.plist (iOS)"

    ```xml
    <key>NSCameraUsageDescription</key>
    <string>Scan receipts with your camera.</string>
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>Show nearby stores.</string>
    ```

=== "AndroidManifest.xml (Android)"

    ```xml
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    ```

## Declaring vs. requesting at runtime

Declaring a permission makes it **available** to your app; it doesn't, by
itself, show a prompt:

- **iOS** shows the system prompt the first time you call the API that
  needs it (the camera, location, etc.), using the usage string you
  configured.
- **Android 6+ (API 23)** requires a runtime request for "dangerous"
  permissions before first use, in addition to the manifest entry.

Use [`pn.Permissions`](native-modules.md#permissions-runtime) or the
[capability](capabilities/index.md) itself to trigger the request at the
right moment in your UX. Keep your `[permissions]` table to the minimum
your app actually uses; both stores scrutinize over-broad permission
requests.
