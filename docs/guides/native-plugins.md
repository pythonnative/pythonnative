# Native plugins

A plugin adds Swift and Kotlin to an app: component managers, native modules, and the project configuration they need.
Every [first-party capability](capabilities/index.md) is one, built only with what this page describes, so
`src/pythonnative/location/` and `src/pythonnative/biometrics/` are good examples to read.

## Layout

```text
my_badge/
    __init__.py            # the Python facade
    native/
        pn_plugin.json
        schema.json        # generated from your Python declarations
        ios/BadgePlugin.swift
        android/com/example/badge/BadgePlugin.kt
        web/index.js       # optional browser preview implementation
```

Publish it in a wheel with an entry point, and any app that requires your package picks it up. Its target wheel is inspected as data,
so nothing runs on the build machine.

```toml
[project.entry-points."pythonnative.plugins"]
my_badge = "my_badge.native"

[tool.setuptools.package-data]
"my_badge.native" = ["*.json", "ios/**/*", "android/**/*", "web/**/*"]
```

For code inside one app, list the directory under `[plugins].paths` in `pythonnative.toml` instead.

## The Python side

Declare the contract with a `Protocol`. [`plugin_module`][pythonnative.sdk.plugin.plugin_module] registers it
with an off-device fallback, and [`plugin_component`][pythonnative.sdk.plugin.plugin_component] returns a typed
element factory.

```python
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from pythonnative.native_modules.registry import native_module
from pythonnative.sdk.plugin import plugin_component, plugin_module


class _ClockService(Protocol):
    def now(self) -> float: ...


class _Fallback:
    def now(self) -> float:
        import time

        return time.time()


plugin_module("Clock", _ClockService, plugin="my_badge", fallback=_Fallback)


@dataclass
class BadgeProps:
    text: str = ""
    on_press: Callable[[], Any] | None = None


Badge = plugin_component("Badge", BadgeProps, plugin="my_badge", measurement="intrinsic")


def now() -> float:
    return native_module("Clock").call("now")
```

Write `schema.json` from those declarations with a small script, as in
`examples/inbox-extension/generate_contracts.py`. The build generates Swift and Kotlin protocols and adapters from it, so your native code implements
`ClockImplementation` and `BadgeProps` with the types already checked.

For `async for` APIs, [`event_stream`][pythonnative.native_modules.registry.event_stream] pairs a start method and a stop method with an event, and stops delivery
when the iteration ends for any reason.

## The manifest

`pn_plugin.json` is declarative: there's no build-time code, which is what keeps a wheel safe to inspect.

| Key | Meaning |
| --- | --- |
| `name` | Required. An identifier, unique in the app. |
| `contracts` | The generated `schema.json`. |
| `requires.permissions` | `[permissions]` entries the app must declare. A missing one fails the build. |
| `requires.plugins` | Plugins that must also be in the build. They're checked, not added. |
| `options` | Options apps set in `[plugins.<name>]`. See below. |
| `ios.entry` | The Swift type conforming to `PNPlugin`. |
| `ios.dependencies` | SwiftPM packages at exact versions: `{"url", "version", "products"}`. |
| `ios.resources` | Globs of files copied into the runtime's bundle. |
| `ios.info_plist` | Keys merged into `Info.plist`. |
| `ios.entitlements` | Keys merged into the entitlements file. |
| `ios.privacy` | Merged into `PrivacyInfo.xcprivacy`: `accessed_api_types` (`{"type", "reasons"}`), `collected_data_types`, and `tracking_domains`. |
| `ios.binary_targets` | `.xcframework` directories to link. |
| `ios.c_target` | C sources as a SwiftPM target: `{"sources", "public_headers"}`. Swift imports it as `PNC_<name>`. |
| `android.entry` | The Kotlin object implementing `PNPlugin`. |
| `android.dependencies` | Maven coordinates at exact versions. |
| `android.resources`, `android.assets` | Globs of Android resources and assets. |
| `android.permissions` | `<uses-permission>` entries. |
| `android.manifest` | XML fragments: `root` goes before `<application>`, `application` inside it. |
| `android.cmake` | A `CMakeLists.txt` built into the app. Load its library with `System.loadLibrary`. |
| `android.gradle_plugins` | Gradle plugins: `{"id", "version"}`. |
| `android.files` | Files copied into the project: `{"from", "to"}`. |
| `ios.when`, `android.when` | Keys applied only when an option has a value. |
| `web.entry` | An ES module for the browser preview. |

Dictionaries merge recursively and lists merge as ordered unions. Two plugins setting one value differently is a build error naming
both. `[ios].extra_info_plist` applies last, so an app always has the final say.

### Options

```json
{
  "options": {
    "google_services_file": {"type": "path"},
    "android_api_key": {"type": "string", "env": "GOOGLE_MAPS_API_KEY"},
    "tasks": {"type": "list", "default": []}
  },
  "ios": {"info_plist": {"BGTaskSchedulerPermittedIdentifiers": "${tasks}"}},
  "android": {
    "when": {
      "google_services_file": {
        "gradle_plugins": [{"id": "com.google.gms.google-services", "version": "4.4.2"}],
        "files": [{"from": "${google_services_file}", "to": "app/google-services.json"}]
      }
    }
  }
}
```

Types are `string`, `integer`, `boolean`, `path`, and `list`. `path` resolves against the project and must exist. `env` names a variable to read when
the app's table leaves the option out, and `required` fails the build when neither supplies it. `${name}` substitutes in manifest values and fragments,
keeping a whole-value reference's type. `${app_id}` and `${display_name}` are always available, and `${applicationId}` passes through to Gradle.

## Native code

Generated record types share one namespace across every plugin in a build, so a record
named `Recording` in two plugins is a compile error. Give a record a name specific to
your plugin, as `camera` does with `VideoRecording`.

Your sources compile inside the runtime's own module, so don't import `PythonNativeKit` in Swift.

```swift
public enum BadgePlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("Badge") { BadgeManager() }
        registry.registerModule(ClockModuleAdapter<ClockModule>.self)
        registry.registerLifecycleHook(BadgeHook.shared)
        PNPermissions.register("camera", CameraPermission())
    }
}
```

```kotlin
object BadgePlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerComponent("Badge") { BadgeManager() }
        registry.registerModule { ClockModuleAdapter(ClockModule()) }
        registry.registerLifecycleHook(BadgeHook)
        PNPermissions.register("camera", "android.permission.CAMERA")
    }
}
```

Failures carry codes that reach Python's `NativeModuleError.code`: `NSError(domain: "my_code", ...)` in Swift, and
`throw PNModuleError(message, "my_code")` in Kotlin.

### Lifecycle hooks

A hook observes application events. Implement only what you need; every method has a default.

- **iOS, `PNAppLifecycleHook`:** `didFinishLaunching`, `didRegisterForRemoteNotifications`, `didFailToRegisterForRemoteNotifications`, `didReceiveRemoteNotification`,
  `handleEventsForBackgroundSession`, `openURL`, `continueUserActivity`, `didEnterBackground`, and `willEnterForeground`. Hooks are installed before
  `didFinishLaunching` returns, which `UNUserNotificationCenter` delegates and `BGTaskScheduler` need.
- **Android, `PNLifecycleHook`:** `onApplicationCreate`, `onActivityCreated`, `onNewIntent`, `onActivityResult`, `onRequestPermissionsResult`, `onActivityResumed`,
  `onActivityPaused`, `onActivityStopped`, and `onActivityDestroyed`. `onApplicationCreate` runs with no activity, for a process started by a push or a job. Call
  `PNHeadless.ensureStarted()` when such code needs Python. On iOS, Python starts on every launch.

### Permissions

A name works in `pn.Permissions` only when a plugin in the build provides it. On iOS, implement `PNPermissionProvider`. On Android, give the manifest permission, what to
request, and optionally `satisfiedBy` and `minSdk`.

## The browser preview

A `web` entry exports `components`, element types mapped to `ViewManager` subclasses from `/static/renderer.js`, and `modules(host)`, which returns module implementations. Pass `browser=True` to
`plugin_module` when the page implements the module; otherwise, calls go to the Python fallback. Components without a manager get a labeled placeholder.
