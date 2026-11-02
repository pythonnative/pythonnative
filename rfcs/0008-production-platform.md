# RFC 0008: Production platform

- Status: Accepted
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-11-01
- Implemented in: (pull request link, once shipped)
- Supersedes / Superseded by: replaces the built-in `Camera`, `Location`,
  `Biometrics`, and `Notifications` modules and the `pn_plugin.json` format
  from RFC 0002 and RFC 0003. Takes on the export trimming that RFC 0006
  deferred, and the release pipeline items RFC 0002 deferred. Everything
  else in those RFCs remains implemented.

## Summary

PythonNative's renderer is close to React Native's, but most real apps can't
ship on it: there's no video, audio, camera preview, maps, push, background
work, or in-app purchase; a package can't change `Info.plist`, entitlements,
or the Android manifest, so nobody else can add those things either; and no
build has ever been proven to reach a store. This RFC adds the layer Expo
provides for React Native. A declarative plugin format (the equivalent of
config plugins and Expo Modules), a set of first-party capabilities built
only on that public format and enabled per app, a release path checked in CI
down to `pn submit`, a production failure path, and a real reference app that
acts as the acceptance test.

## Motivation

The audit behind this RFC found five things that stop an app, in the order a
developer hits them:

1. **Missing capabilities.** No video, audio, camera preview, maps, sensors,
   background tasks, in-app purchases, or document picking. Notifications can
   be scheduled but not received or tapped. Android has no remote push.
   `pn.fetch` has no streaming, multipart, or WebSocket support.
2. **A plugin can't configure the app.** `pn_plugin.json` allows `entry`,
   `resources`, `assets`, `contracts`, and `dependencies`. A package can't add
   an `Info.plist` key, an entitlement, a privacy manifest entry, an
   `AndroidManifest.xml` service, or a Gradle plugin. It can't observe
   `application(_:didReceiveRemoteNotification:)` or `onNewIntent`, and it
   can't ship C, C++, or an xcframework. So the escape hatch for item 1 doesn't
   reach most of what's missing.
3. **Every app links everything.** `PermissionModules.swift` imports
   `AVFoundation`, `Contacts`, `CoreLocation`, `LocalAuthentication`, `Photos`,
   and `UserNotifications`, and it's compiled into every app. A note-taking app
   references the camera, location, and contacts APIs. Apple flags binaries that
   reference privacy-sensitive APIs without a matching usage string.
4. **Release is unproven.** No workflow runs `pn build`, an archive, or
   `bundleRelease`; those paths are only covered by mocks. An archive built by
   hand shows real gaps. `Python.framework` calls `statfs` and
   `mach_absolute_time` without declared reasons, the template's privacy
   manifest is empty, a build with no icon succeeds with no `Assets.car`,
   an unsigned Android build exits 0, `app_packages/bin` ships scripts with a
   build-machine shebang, `CFBundleName` stays `ios_template`, and manual
   signing only reaches `exportOptions`, so the archive stays on automatic
   signing. There's no upload command at all.
5. **Production failures are silent.** With no error boundary, a render error
   in a release build is logged and the old UI stays up. A failed mount poisons
   the surface, and `reset()` is reachable only from a hot-reload remount, so
   the screen stays dead. There's no hook an app can use to report errors.

Underneath all of that, the largest app ever built on PythonNative is 347
lines. Nothing has forced these pieces to work together.

## Reference behavior

| Concern | React Native and Expo | This RFC |
| --- | --- | --- |
| Native module packaging | Expo Modules: Swift and Kotlin DSL, autolinked from `package.json` | `pn_plugin.json` in a wheel, autolinked. Contracts come from typed Python, which generates the Swift and Kotlin adapters |
| Project configuration | Config plugins: JavaScript functions that mutate plist, manifest, and Gradle | Declarative JSON manifest. Target wheels are inspected as data and never imported into the build interpreter (RFC 0002), so an imperative hook isn't possible here without giving that up |
| App lifecycle | `ExpoAppDelegateSubscriber`, `ReactActivityLifecycleListener` | `PNAppLifecycleHook` on iOS and `PNLifecycleHook` on Android |
| Capabilities | One package per capability, installed with `expo install`, autolinked | One subpackage per capability inside the `pythonnative` wheel, enabled with `[plugins].use`. Same version as the framework, so no compatibility matrix |
| Prebuilt client | Expo Go carries the whole SDK | PythonNative Go carries every first-party plugin |
| Build and submit | EAS Build, EAS Submit | Local `pn build`, `pn submit`. No hosted service |
| Fatal errors | `ErrorUtils.setGlobalHandler`, RedBox, LogBox | `pn.set_error_handler`, a default root boundary, DevTools |

Two deliberate differences:

- **In the wheel, not on PyPI.** Expo has a package per capability because npm
  makes that cheap and Expo's SDK versions are coordinated by its CLI.
  PythonNative's contracts and adapters are generated from the exact framework
  version, and Go requires an exact match, so a separately versioned package
  would add a compatibility matrix and no benefit before 1.0. Native sources
  already ship in the wheel and are only compiled when enabled. Third parties
  use exactly the same format from their own wheels.
- **Python async idioms.** Streams are async iterators and subscriptions are
  context managers or plain unsubscribe functions, rather than a listener
  object per API. Failures raise and outcomes return values, as the
  `native_modules` rules already say.

## Design

### Enabling a capability

```toml
[plugins]
use = ["camera", "notifications", "maps"]   # first-party capabilities
paths = ["native/badge"]                    # project-local plugins, as before

# Options for one plugin, first-party or third-party.
[plugins.maps]
android_api_key = "..."   # or leave it out and set GOOGLE_MAPS_API_KEY

[permissions]
camera = "Scan receipts with your camera."
```

```python
from pythonnative.camera import Camera, CameraView
from pythonnative.maps import MapView, Marker
```

- A capability is a subpackage: `src/pythonnative/<name>/`, holding its Python
  facade and a `native/` plugin directory. `native` directories never reach an
  app bundle (`project/bundle.py` already ignores that name at any depth).
- `pn build` stages only the plugins in `use`. So an app that doesn't enable
  `camera` doesn't compile a line that references `AVCaptureDevice`.
- Importing a facade whose plugin isn't in the build still works. Calling it
  raises `NativeModuleError` with code `plugin_not_enabled` and the message
  names the `[plugins].use` entry to add. A component whose manager isn't
  registered reports the same thing at commit time.
- Off device, each facade registers a Python fallback, so tests and the browser
  preview run the same code.
- PythonNative Go compiles every first-party plugin. A project that only uses
  first-party plugins stays Go-compatible; a project with third-party native
  code still needs `pn run`.

### Plugin manifest v2

`pn_plugin.json` gains the config-plugin surface. Every new key is optional.

```json
{
  "name": "push",
  "contracts": "schema.json",
  "requires": {"plugins": ["notifications"], "permissions": ["notifications"]},
  "options": {
    "google_services_file": {"type": "path", "default": null},
    "aps_environment": {"type": "string", "default": "production"}
  },
  "ios": {
    "entry": "PushPlugin",
    "info_plist": {"UIBackgroundModes": ["remote-notification"]},
    "entitlements": {"aps-environment": "${aps_environment}"},
    "privacy": {"accessed_api_types": [{"type": "NSPrivacyAccessedAPICategoryUserDefaults", "reasons": ["CA92.1"]}]},
    "binary_targets": ["ios/vendor/Foo.xcframework"],
    "c_target": {"sources": "ios/c", "public_headers": "ios/c/include"}
  },
  "android": {
    "entry": "com.pythonnative.plugins.push.PushPlugin",
    "permissions": ["android.permission.POST_NOTIFICATIONS"],
    "manifest": {"application": "android/application.xml", "root": "android/manifest.xml"},
    "cmake": "android/cpp/CMakeLists.txt",
    "gradle_plugins": [{"id": "com.google.gms.google-services", "version": "4.4.2"}],
    "dependencies": ["com.google.firebase:firebase-messaging:24.1.0"],
    "when": {
      "google_services_file": {
        "files": [{"from": "${google_services_file}", "to": "app/google-services.json"}]
      }
    }
  }
}
```

Rules:

- `options` values are declared with a `type` (`string`, `integer`, `boolean`,
  `path`, `list`), a `default`, optional `required`, and optional `env`, which
  names an environment variable to read when the app's table doesn't set the
  option, so secrets stay out of `pythonnative.toml`. Unknown options in
  `[plugins.<name>]` are a build error, as is a missing required one.
- `${option}` substitutes in `info_plist`, `entitlements`, `files`, and manifest
  fragments. An unknown name is a build error.
- `info_plist` and `entitlements` merge: dictionaries recursively and lists as
  ordered unions. Two plugins setting the same scalar to different values is a
  build error naming both. `[ios].extra_info_plist` applies last and wins, so
  an app always has the final say.
- `privacy` merges into the app's `PrivacyInfo.xcprivacy`, deduplicating reasons
  per API type.
- `requires.permissions` makes a missing `[permissions]` entry a build error,
  because a missing usage string crashes at the call on iOS.
- `requires.plugins` is checked, not implied: naming a plugin in `use` doesn't
  silently pull another in.
- `when.<option>` applies its nested keys only if that option has a value.
- Only manifest, plist, entitlement, privacy, dependency, and file changes are
  possible. There's no arbitrary code at build time, which keeps wheels safe to
  inspect as data.

Staging keeps the existing shape: `stage_ios_plugins` and
`stage_android_plugins` copy sources, and a new `project/plugin_config.py`
applies the declarative parts after `ios.configure` and `android.configure`.

**C, C++, and xcframeworks.** `binary_targets` adds `.binaryTarget(path:)` entries
to the staged `Package.swift`. `c_target` adds a sibling SwiftPM target
`PNC_<plugin>` that `PythonNativeKit` depends on, which Swift imports by that
name. `cmake` adds an `add_subdirectory` to a generated `plugins.cmake` that
the runtime's `CMakeLists.txt` includes. The e2e suite carries a small local
plugin using both, so this path stays honest.

### Lifecycle hooks

```swift
public protocol PNAppLifecycleHook: AnyObject {
    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?)
    func didRegisterForRemoteNotifications(deviceToken: Data)
    func didFailToRegisterForRemoteNotifications(error: Error)
    func didReceiveRemoteNotification(_ userInfo: [AnyHashable: Any],
                                      completion: @escaping (UIBackgroundFetchResult) -> Void) -> Bool
    func handleEventsForBackgroundSession(identifier: String, completion: @escaping () -> Void) -> Bool
    func openURL(_ url: URL) -> Bool
    func continueUserActivity(_ activity: NSUserActivity) -> Bool
    func didEnterBackground()
    func willEnterForeground()
}
```

Every method has a default no-op in a protocol extension. Plugins register a
hook with `registry.registerLifecycleHook(_:)`. `AppDelegate` and
`SceneDelegate` forward to `PNAppLifecycle.shared`, whose first call forces
registration, so a hook is installed before `didFinishLaunching` returns.

```kotlin
interface PNLifecycleHook {
    fun onApplicationCreate(application: Application) {}
    fun onActivityCreated(activity: Activity) {}
    fun onNewIntent(intent: Intent): Boolean = false
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean = false
    fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray): Boolean = false
    fun onActivityResumed(activity: Activity) {}
    fun onActivityPaused(activity: Activity) {}
    fun onActivityStopped(activity: Activity) {}
    fun onActivityDestroyed(activity: Activity) {}
}
```

The Android template gains `PNApplication`, because push and background work
start the process with no `Activity`.

**Headless Python.** `PythonHost` (Android) and `PythonRuntime` (iOS) start
Python without a screen. A plugin that needs Python while there's no UI calls
`PNHeadless.deliver(module, event, payload)`, which starts the runtime if it
isn't up, imports the app's entry module so its registrations run, and then
delivers through the normal module event path. Rendering is unaffected: no
surface exists until an activity or scene asks for one.

### Permissions

The `Permissions` module stays in the core, without importing any
privacy-sensitive framework. A plugin registers a provider for the names it
owns:

```swift
PNPermissions.register("camera", PNCameraPermission())
```

`Permissions.check` and `request` for a name with no provider raise
`NativeModuleError` with code `plugin_not_enabled`. `contacts` is removed from
the vocabulary because no API here uses it, and a third-party plugin can add
its own name back. `Permissions.request("notifications")` keeps working when
`notifications` is enabled.

### First-party capabilities

All are built only with the public plugin format, and each has a Python
fallback, a contract, Swift, Kotlin, tests, a demo in `examples/e2e-suite`, and
a Maestro flow where a simulator can run it.

| Import | Public API | iOS | Android | Moved or new |
| --- | --- | --- | --- | --- |
| `pythonnative.location` | `Location.get_current`, `Location.watch` (async iterator) | CoreLocation | `LocationManager` | Moved, `watch` new |
| `pythonnative.biometrics` | `Biometrics.authenticate`, `Biometrics.available` | LocalAuthentication | `androidx.biometric` | Moved |
| `pythonnative.camera` | `Camera.take_photo`, `CameraView` with `take_picture`, `start_recording`, `stop_recording`, barcode scanning | AVFoundation | CameraX | Moved, `CameraView` new |
| `pythonnative.pickers` | `pick_images`, `pick_videos`, `pick_documents` | PHPicker, `UIDocumentPicker` | Photo picker, `ACTION_OPEN_DOCUMENT` | `pick_from_gallery` moved, rest new |
| `pythonnative.notifications` | `schedule`, `cancel`, `set_badge`, `on_received`, `on_response`, `last_response` | UserNotifications | `NotificationManager`, `AlarmManager` | Moved, handlers new |
| `pythonnative.push` | `get_device_token`, `on_token`, `on_message` | APNs | FCM | Token moved, FCM new |
| `pythonnative.video` | `Video` with `VideoHandle` | AVPlayer | Media3 ExoPlayer | New |
| `pythonnative.audio` | `Sound`, `Recorder` | AVAudioPlayer, AVAudioRecorder | Media3, `MediaRecorder` | New |
| `pythonnative.maps` | `MapView`, `Marker`, `Region`, `Polyline` | MapKit | Google Maps SDK | New |
| `pythonnative.sensors` | `Accelerometer`, `Gyroscope`, `Magnetometer`, `Barometer` (async iterators) | CoreMotion | `SensorManager` | New |
| `pythonnative.background` | `@background.task(name, every=...)`, `background.schedule` | BGTaskScheduler | WorkManager | New |
| `pythonnative.purchases` | `Purchases.products`, `purchase`, `restore`, `on_update` | StoreKit 2 | Play Billing | New |

```python
from pythonnative.sensors import Accelerometer
from pythonnative.video import Video


@pn.component
def Player(url: str) -> pn.Node:
    player = pn.use_ref()
    return pn.Column(
        Video(source=url, controls=True, ref=player, style=pn.style(aspect_ratio=16 / 9)),
        pn.Button("Restart", on_press=lambda: player.current.seek(0)),
    )


async def watch_motion() -> None:
    async for reading in Accelerometer.readings(hz=30):
        print(reading.x, reading.y, reading.z)
```

Platform differences are documented per method and enforced through the
contract's `platforms` field, not by silent no-ops. Anything iOS 15+ only, such as
StoreKit 2, raises `unsupported` below that version; the deployment target stays
at 13.0.

### Networking (core, no plugin)

- `pn.WebSocket`: an RFC 6455 client in pure Python on `asyncio`, used as an
  async context manager and an async iterator. No native code, so it behaves the
  same on device, in tests, and in the preview.
- `pn.fetch` gains `files=` for multipart bodies, `stream=True` for chunked
  responses read with `async for chunk in response.chunks()`, and an upload
  progress callback. TLS verification on device is verified, not assumed.

```python
async with pn.WebSocket("wss://example.com/feed") as socket:
    await socket.send_json({"subscribe": "news"})
    async for message in socket:
        handle(message)
```

### Universal links and app links

`[app].associated_domains = ["example.com"]` writes the `applinks:` entitlement
on iOS and an `android:autoVerify` `https` intent filter on Android.
`SceneDelegate` forwards `NSUserActivity` to `Linking`. Navigation's existing
deep-link matching takes the `https` URL's path. `pn doctor` prints the files the
site must host, and `pn links` prints their exact contents for the app's bundle ID
and signing team.

### Store release

`pn build` changes:

- The template's privacy manifest declares what the embedded runtime actually
  uses (`SystemBootTime` 35F9.1, `DiskSpace` E174.1, `FileTimestamp` C617.1,
  `UserDefaults` CA92.1), merged with plugin entries and the app's own file.
- A release build fails when there's no icon or Pillow is missing, when a store
  export isn't signed, or when a required usage string is missing.
  `--allow-unsigned` keeps the old behavior for CI smoke builds.
- `app_packages` drops `bin/`, `tests/`, and `test/` from wheels in release
  builds on iOS.
- `[ios.signing].provisioning_profile` also applies to the archive, with
  `CODE_SIGN_STYLE=Manual`.
- App Store Connect API key arguments are read from `PN_ASC_KEY_PATH`,
  `PN_ASC_KEY_ID`, and `PN_ASC_ISSUER_ID`, so CI doesn't need an Xcode account.

New commands and flags:

- `pn submit ios` uploads the built `.ipa` with `xcrun altool` and the API key.
- `pn submit android --track internal` uses the Google Play Developer API with
  a service account (`PN_PLAY_SERVICE_ACCOUNT`): insert an edit, upload the
  bundle, assign the track, and commit. It signs its JWT with `openssl` so it
  adds no dependency.
- `pn run --release` runs the release configuration on a simulator or emulator
  so release-mode e2e is possible.

CI gains a `release` job that runs `pn build android` and an iOS release archive
with `--allow-unsigned`, validates each artifact with `project/artifacts.py`, and
runs a smoke flow against the release configuration.

### Production failure path

- **`pn.set_error_handler(fn)`** receives every uncaught error with its phase
  (`render`, `effect`, `event`, `async`, `mount`) in dev and release. It's where
  crash reporters attach.
- **Default root boundary.** In a release build, a render error that escapes all
  boundaries replaces the screen with a fallback showing a retry button. Apps
  can replace it with `pn.set_error_fallback(component)`. Dev builds keep the
  existing error screen.
- **Mount recovery.** `surface_failed` now schedules a full remount of the
  surface, once. A second failure inside a minute shows the fallback, so a broken
  tree can't loop forever.

### Exports

The top-level namespace drops what has a better home or a duplicate:

- Moved to their capability package: `Camera`, `Location`, `Biometrics`,
  `Notifications`.
- Moved to `pythonnative.sdk`: `UNSET`, `UnsetType`, `element_factory`.
- Moved to `pythonnative.style`: `resolve_style`, `Dimension`, `AlignContent`,
  `AlignItems`, `BorderStyle`, `Display`, `FlexDirection`, `FlexWrap`,
  `FontWeight`, `JustifyContent`, `LayoutDirection`, `Overflow`, `PointerEvents`,
  `Position`, `ScaleType`, `TextAlign`, `TextDecoration`, `TextTransform`, and the
  other style aliases.
- Moved to `pythonnative.animated`: `ANIMATABLE_PROPS`.
- Removed: `TouchableOpacity` (use `Pressable` with `pressed_opacity`),
  `Vibration` (use `Haptics`), `get_platform` (use `Platform`), `AlignSelf` (it's
  `AlignItems`), `create_screen`, and the `runtime` and `diagnostics` re-exports.

### Reference app

`examples/fieldnotes` is a field journal, 3,000 to 5,000 lines: entries with
photos and voice notes, a map of where they were taken, live collaboration over
a WebSocket, reminders that deep-link to an entry, a background sync, a video
attachment player, and a one-time "Pro" unlock. It replaces Inbox as the example
the docs lead with. Inbox stays as the extension SDK's acceptance test. It has its
own Maestro flows, and CI builds it in release mode.

### Browser preview

A plugin may declare `"web": {"entry": "web/index.js"}`, an ES module that exports
component managers and module implementations for the preview. The dev server
serves it to the page. First-party plugins use it where a browser can honor the
contract: `Video`, `Sound`, `CameraView` (`getUserMedia`), `pick_documents`, and
`Location`. Others get the existing labeled placeholder and the Python fallback.

### Wire contract

`PROTOCOL_VERSION` doesn't change. Contracts move: the moved modules leave the
built-in document and arrive through plugin contracts, so the contract fingerprint
differs per app, which the handshake already handles. Removing `TouchableOpacity`
removes a component from the built-in contract.

## Removals

- `CameraModule`, `LocationModule`, `BiometricsModule`, `NotificationsModule`,
  and their facades, services, and permission checks from the core, on both
  platforms. They move to plugins, with no aliases left behind.
- `pn.Camera.pick_from_gallery`, replaced by `pythonnative.pickers.pick_images`.
- The `contacts` permission name, the Android `pn_permissions` code path that
  only `contacts` needed, and the e2e app's `contacts` declaration.
- `TouchableOpacity` from Python, the contract, Swift, Kotlin, and the preview.
- The exports listed above. `check-e2e-coverage.py` tracks the smaller list.
- `AppDelegate` and `MainActivity` calls into specific modules, in favor of hooks.
- The narrower `pn_plugin.json` validation: the old format still parses because
  every new key is optional, but the sample in `project/plugins.py` that omits
  `name` is corrected, and `name` becomes required so two plugins can't collide
  on the `native` default.

## Alternatives considered

- **One PyPI package per capability.** Matches Expo, but adds version
  coordination and multiple release pipelines for no benefit while the contracts
  are generated from the exact framework version.
- **Python functions as config plugins.** Matches Expo's model more closely, but
  means importing target wheels into the build interpreter, which RFC 0002
  rejected for binary wheels and for safety. A declarative manifest covers what
  first-party plugins need.
- **Enable capabilities from `[permissions]`.** Tempting, since `camera = "..."`
  says most of it, but video, maps, sensors, and purchases have no permission, and
  a permission doesn't imply which capability wants it.
- **A hosted build service.** EAS is a large part of Expo's value, but it's a
  business rather than a framework feature. `pn build` runs locally and in the
  user's CI.
- **Replacing Chaquopy now.** It would close the Android wheel gap, but it's a
  runtime swap with its own risk, and it isn't what stops an app shipping today.
- **WebSocket through native code.** Needs an extra dependency on Android (OkHttp),
  and a preview and test implementation besides. Python's `asyncio` already runs on
  every target.

## Non-goals

- UI-thread logic, layout animations, and shared-element transitions. That's the
  next RFC.
- Over-the-air updates, which raise App Store policy questions of their own.
- Replacing Chaquopy, frozen stdlib, device benchmarks, and time-sliced rendering.
- R8 or ABI splits for Android. R8 can strip classes Chaquopy reaches by reflection,
  and AAB already delivers per-ABI splits.
- A `State` object and a typed `use_mutation`, from the same audit.
- Contacts, calendar, Bluetooth, NFC, and Apple Pay. Each is a plugin anyone can
  now write; none is on the shortest path to shipping most apps.
- Publishing Go to a store.
- A native drawer, sheet detents, or top tabs.
- Production web and desktop targets.

## Testing and rollout

- **Unit:** the manifest parser and merge rules (including conflicts), `use`
  validation, option substitution, plist and manifest output, privacy manifest
  merging, release gates, `pn submit` against a fake server, each facade's fallback,
  the error handler, and mount recovery.
- **Native:** the existing XCTest and Android unit suites, plus hook dispatch and
  permission providers.
- **E2E:** a demo and Maestro flow per capability, and flows for `examples/fieldnotes`,
  on the iOS simulator and Android emulator.
- **Release:** the new CI job, plus an artifact check that a project using no
  capabilities has no reference to the sensitive frameworks.

Limits of what a simulator proves, stated here so nobody assumes otherwise:

- `CameraView` capture needs real hardware on iOS. The simulator has no camera.
- Remote push needs APNs and Firebase credentials, and a device for APNs.
- Purchases need App Store Connect and Play Console setup. StoreKit's local test
  configuration covers the iOS flow; Play Billing needs a Play-signed build.
- A background task can be forced with `adb` on Android, but iOS's scheduler has
  only a debugger-driven trigger.
- Android maps need an API key and a Google APIs emulator image.
- `pn submit` needs real store credentials, and a real upload is the maintainer's
  to do. CI proves the artifact and the request flow.

Migration: nobody depends on the removed names yet, so there are no shims. The
templates, `pn init`, examples, and docs change in the same pull request.
