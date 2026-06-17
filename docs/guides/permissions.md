# Permissions

iOS and Android describe the same device capability in very different
ways: iOS wants *usage-description* strings in `Info.plist`, Android
wants `<uses-permission>` entries (and, since API 23, a runtime prompt).
PythonNative lets you declare capabilities **once**, by name, in
`pythonnative.toml`, and expands each into the correct native artifacts
for both platforms.

```toml
[permissions]
camera = "Scan receipts with your camera."
location_when_in_use = "Show nearby stores."
face_id = "Unlock the app with Face ID."
notifications = true
```

## Value semantics

Each capability's value can be:

| Value | Meaning |
| --- | --- |
| a **string** | The capability is enabled; the string is used verbatim as the iOS permission-prompt text (the usage description). |
| **`true`** | The capability is enabled using its built-in default reason. |
| **`false`** | The capability is disabled, useful for toggling one off without deleting the line. |

!!! tip "Write a real reason"
    On iOS, App Review rejects apps whose usage strings are vague or
    missing. Prefer a concrete sentence (`"Scan receipts with your
    camera."`) over `true` for any capability that prompts the user.

Unknown capability names are rejected when the config is validated, so a
typo like `camara` fails fast instead of silently doing nothing.

## Capability catalog

Declaring a capability adds the listed iOS usage keys, Android
permissions, and (where relevant) iOS background modes.

| Capability | What it's for | iOS usage key(s) | Android permission(s) |
| --- | --- | --- | --- |
| `camera` | Capture photos/video | `NSCameraUsageDescription` | `CAMERA` |
| `microphone` | Record audio | `NSMicrophoneUsageDescription` | `RECORD_AUDIO` |
| `photo_library` | Read photos/videos | `NSPhotoLibraryUsageDescription` | `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO` |
| `photo_library_add` | Save to photo library | `NSPhotoLibraryAddUsageDescription` | – |
| `location_when_in_use` | Foreground location | `NSLocationWhenInUseUsageDescription` | `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` |
| `location_always` | Foreground + background location | `NSLocationAlwaysAndWhenInUseUsageDescription`, `NSLocationWhenInUseUsageDescription` | `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION` |
| `contacts` | Read the address book | `NSContactsUsageDescription` | `READ_CONTACTS` |
| `calendars` | Read/write calendar events | `NSCalendarsUsageDescription` | `READ_CALENDAR`, `WRITE_CALENDAR` |
| `reminders` | Read/write reminders (iOS) | `NSRemindersUsageDescription` | – |
| `motion` | Motion / fitness data | `NSMotionUsageDescription` | `ACTIVITY_RECOGNITION` |
| `face_id` | Biometric auth | `NSFaceIDUsageDescription` | `USE_BIOMETRIC` |
| `bluetooth` | Nearby Bluetooth devices | `NSBluetoothAlwaysUsageDescription` | `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` |
| `speech_recognition` | Speech recognition (iOS) | `NSSpeechRecognitionUsageDescription` | – |
| `notifications` | Local/push notifications | – | `POST_NOTIFICATIONS` |
| `vibration` | Haptics / vibration | – | `VIBRATE` |
| `background_audio` | Play audio in background | – (adds `audio` background mode) | `FOREGROUND_SERVICE` |
| `background_fetch` | Periodic background fetch | – (adds `fetch` background mode) | – |

Capabilities marked "–" for a platform simply contribute nothing there.
`notifications`, `vibration`, `background_audio`, and `background_fetch`
need no iOS usage string, so declaring them as `true` is enough.

### Background modes

`location_always`, `background_audio`, and `background_fetch` also add
the corresponding values to the iOS `UIBackgroundModes` array
(`location`, `audio`, `fetch`) so the OS keeps your app scheduled.

## Always-on permissions

Every app receives two install-time Android permissions automatically,
because almost every PythonNative app needs the network (`fetch`,
`use_query`, `NetInfo`, remote images):

- `android.permission.INTERNET`
- `android.permission.ACCESS_NETWORK_STATE`

These never prompt the user and require no declaration.

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
  `UIBackgroundModes` array when any background-capable capability is
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

Declaring a capability makes the permission **available** to your app;
it does not, by itself, show a prompt:

- **iOS** shows the system prompt the first time you call the API that
  needs it (the camera, location, etc.), using the usage string you
  configured.
- **Android 6+ (API 23)** requires a runtime request for "dangerous"
  permissions before first use, in addition to the manifest entry.

Use the relevant [native module](native-modules.md) to trigger the
request at the right moment in your UX. Keep your `[permissions]` table
to the minimum your app actually uses; both stores scrutinize
over-broad permission requests.
