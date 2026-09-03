# Native modules

Native modules are PythonNative's wrappers around device APIs that
aren't part of the view tree: the camera, GPS, file I/O, clipboard,
share sheet, deep links, permissions, connectivity, secure storage,
battery, haptics, and biometrics. Each module is a Swift class in
`PythonNativeKit` and a Kotlin class in the `pythonnative` Gradle
module, registered by name; the Python class you call is a thin facade
that routes through the [native bridge](../concepts/bridge.md). Off
device (`pn preview`, `pytest`), the same facade resolves to a Python
implementation with safe defaults (in-memory buffers, `"unknown"`
states, no-op feedback), so app code stays single-source.

Every facade follows the same two rules, so you never need to look
one up:

1. **Sync or async is decided by what the OS has to do.** A method is a
   plain function when the answer is already on the device and returns
   on the calling thread: `Clipboard`, `Linking`, `Haptics` /
   `Vibration`, `Battery`, `NetInfo.fetch`, `SecureStore`, `AppState`,
   `FileSystem`, `Permissions.check`, `Biometrics.is_available`. It is
   a coroutine when the OS has to prompt the user, drive hardware, or
   hand off to another process: `Camera.take_photo` /
   `pick_from_gallery`, `Location.get_current`, `Share.share`,
   `Permissions.request`, `Biometrics.authenticate`, `Notifications.*`,
   `Alert.confirm` / `choose`, and all of `AsyncStorage`. Inside a
   component, drive coroutines with an `async def`
   [`use_effect`][pythonnative.use_effect] callback,
   [`use_resource`][pythonnative.use_resource],
   [`use_query`][pythonnative.hooks.use_query], or
   [`pn.run_async(coro)`][pythonnative.runtime.run_async] from a sync
   handler.
2. **Failures raise; "nothing happened" returns a value.** A native
   error (a rejected call, a missing module, a bad argument) is a
   [`NativeModuleError`][pythonnative.native_modules.NativeModuleError]
   and propagates like any other exception; `FileSystem` raises the
   standard `OSError` family. Outcomes that are not errors, such as the
   user cancelling a picker (`None`), dismissing the share sheet
   (`False`), or denying a permission (`"blocked"`), come back as
   values and are documented per method. No facade turns an exception
   into a default. Off device the desktop implementations never raise;
   they answer with the "nothing happened" value.

Two modules also ship reactive hooks:
[`use_app_state`][pythonnative.use_app_state] and
[`use_net_info`][pythonnative.use_net_info].

## Permissions: declare them once, request at runtime

Declare the capabilities your app uses in the `[permissions]` table of
`pythonnative.toml`. `pn` writes the matching `Info.plist` usage
strings, `AndroidManifest.xml` `<uses-permission>` entries, background
modes, and entitlements into the native projects for you (the full
catalog is in the [configuration reference](configuration.md#permissions)):

```toml
[permissions]
camera = "So you can take photos in MyApp."
location_when_in_use = "So MyApp can show nearby content."
photo_library = "So you can pick photos from your library."
notifications = true
```

The strings appear in the system permission dialog on iOS, so write
them as you would want a user to read them. The same keys are the
names you pass to [`Permissions`](#permissions-runtime) at runtime, so
there is one vocabulary to learn.

## Camera

[`Camera`][pythonnative.native_modules.camera.Camera] wraps photo
capture and gallery picking. Both coroutines resolve to a path to the
saved file (or `None` if the user cancelled).

```python
import pythonnative as pn


@pn.component
def CameraScreen():
    photo, set_photo = pn.use_state(None)

    async def take():
        path = await pn.Camera.take_photo()
        if path:
            set_photo(path)

    return pn.Column(
        pn.Button("Take photo", on_press=lambda: pn.run_async(take())),
        pn.Image(source=photo) if photo else pn.Spacer(),
    )
```

!!! note "Cold-start permissions"
    The first call shows the system permission prompt. If the user
    denies it, subsequent calls resolve to `None` immediately; surface
    a helpful message in your UI rather than calling in a loop.

## Location

[`Location.get_current`][pythonnative.native_modules.location.Location.get_current]
reads a single GPS fix.

```python
import pythonnative as pn


@pn.component
def WhereAmI():
    q = pn.use_query(pn.Location.get_current, [])
    if q.loading:
        return pn.Text("Acquiring location...")
    if q.data is None:
        return pn.Text("Location unavailable")
    lat, lon = q.data
    return pn.Text(f"{lat:.4f}, {lon:.4f}")
```

[`use_query`][pythonnative.hooks.use_query] manages the
loading/data/error state for you and exposes a `refetch()` callable.

For continuous updates, write a small native module that subscribes
to `CLLocationManagerDelegate` (iOS) or `LocationManager.requestUpdates`
(Android) and pushes deltas through `set_state` from the main thread.

## File system

[`FileSystem`][pythonnative.native_modules.file_system.FileSystem]
answers the one question the standard library can't, "where may this
app write?", and then gets out of the way. `app_dir()` is the app's
sandboxed documents directory; `path("notes/today.txt")` resolves a
relative name inside it and returns a `pathlib.Path` you use like any
other. The read/write helpers are thin conveniences over that path and
raise the same `OSError` subclasses `open` does (`FileNotFoundError`,
`PermissionError`, ...). Everything is synchronous, exactly like the
standard library it wraps; for large files, offload to a worker thread:

```python
import asyncio
import pythonnative as pn

# Sync: fine for small files (preferences, JSON state, etc.)
pn.FileSystem.write_text("notes.txt", "hello")
text = pn.FileSystem.read_text("notes.txt")

# Work with the Path directly when you need more than the helpers.
for entry in sorted(pn.FileSystem.path("notes").iterdir()):
    print(entry.name)

# Async: explicitly offload to a worker thread for big payloads.
text = await asyncio.to_thread(pn.FileSystem.read_text, "big.txt")
```

!!! tip "Need just a key-value store?"
    Prefer [`AsyncStorage`][pythonnative.storage.AsyncStorage] over
    serialising JSON into a file by hand; it's the native
    `NSUserDefaults` / `SharedPreferences` API and is async-first.

## Notifications

[`Notifications`][pythonnative.native_modules.notifications.Notifications]
schedules local notifications and cancels previously scheduled ones.

```python
import pythonnative as pn


async def setup_reminder():
    granted = await pn.Notifications.request_permission()
    if not granted:
        return
    await pn.Notifications.schedule(
        title="Stretch break",
        body="Stand up!",
        delay_seconds=1800,
        identifier="reminder",
    )
```

`request_permission()` is required on iOS and on Android 13+. On
older Android the call returns `True` without prompting.

For server-sent (remote) pushes, declare the `remote_notifications`
capability in `pythonnative.toml`, then register with APNs:

```python
token = await pn.Notifications.get_device_token()  # APNs hex token
```

Your server passes the token to APNs to address this install. The
simulator has no APNs connection, so test on a real device. Android
remote push requires Firebase Cloud Messaging, which the built-in
module doesn't wire up; `get_device_token()` returns `None` there.

## Clipboard

[`Clipboard`][pythonnative.Clipboard] reads and writes the system
pasteboard synchronously.

```python
import pythonnative as pn

pn.Clipboard.set_string("Copied!")
text = pn.Clipboard.get_string()
if pn.Clipboard.has_string():
    ...
```

## Share

[`Share.share`][pythonnative.Share] presents the system share sheet and
resolves to `True` once the user completes a share.

```python
async def share_link():
    await pn.Share.share(message="Check this out", url="https://example.com")
```

## Linking

[`Linking`][pythonnative.Linking] opens URLs, deep links, and the app's
Settings page, and delivers inbound deep links to your app.

```python
if pn.Linking.can_open_url("tel:+15551234567"):
    pn.Linking.open_url("tel:+15551234567")

launch_url = pn.Linking.get_initial_url()  # deep link the app opened with
pn.Linking.open_settings()                 # this app's entry in Settings
```

To receive deep links, declare your schemes in `pythonnative.toml`:

```toml
[app]
url_schemes = ["myapp"]
```

Opening `myapp://orders/42` now launches (or foregrounds) your app on
both platforms. The URL that cold-started the app is returned by
`get_initial_url()`; URLs that arrive while the app is running reach
subscribers:

```python
unsubscribe = pn.Linking.add_listener(lambda url: navigate_to(url))
```

## Permissions (runtime)

[`Permissions`][pythonnative.Permissions] normalizes the iOS/Android
permission models. `check` is synchronous; `request` prompts and is a
coroutine. Names are the `[permissions]` keys from `pythonnative.toml`
that have a runtime prompt: `"camera"`, `"microphone"`,
`"photo_library"`, `"location_when_in_use"`, `"contacts"`,
`"notifications"` (any other name raises `ValueError`). Statuses:
`"granted"`, `"denied"`, `"blocked"`, `"undetermined"`.

```python
if pn.Permissions.check("camera") != "granted":
    status = await pn.Permissions.request("camera")
    if status == "blocked":
        pn.Linking.open_settings()  # user must enable it in Settings
```

Declaring the capability in `[permissions]` is what puts the usage
string in the manifest; `request` is what shows the prompt.

## App state

[`AppState`][pythonnative.AppState] reports the foreground/background
lifecycle phase (`"active"`, `"inactive"`, `"background"`). Use the
[`use_app_state`][pythonnative.use_app_state] hook in components:

```python
@pn.component
def Status():
    state = pn.use_app_state()
    return pn.Text(f"App is {state}")
```

Outside the tree, subscribe imperatively:

```python
unsubscribe = pn.AppState.add_listener(lambda s: print("now", s))
```

## Network connectivity

[`NetInfo`][pythonnative.NetInfo] reports connectivity. `fetch()` returns
`{"is_connected": bool, "type": str, "is_internet_reachable": bool}`;
the [`use_net_info`][pythonnative.use_net_info] hook re-renders on change.

```python
@pn.component
def Banner():
    net = pn.use_net_info()
    if not net["is_connected"]:
        return pn.Text("You are offline", style=pn.style(color="#B91C1C"))
    return pn.Spacer()
```

## Secure storage

[`SecureStore`][pythonnative.SecureStore] persists secrets in the iOS
Keychain / Android `EncryptedSharedPreferences`. Use it for tokens,
not [`AsyncStorage`][pythonnative.storage.AsyncStorage], which is
unencrypted.

```python
pn.SecureStore.set_item("auth_token", token)      # raises NativeModuleError on failure
token = pn.SecureStore.get_item("auth_token")     # None when absent
pn.SecureStore.delete_item("auth_token")          # True if it existed
```

## Battery

[`Battery`][pythonnative.Battery] exposes the charge level (`0.0`–`1.0`,
or `-1.0` if unknown) and state, plus a change listener.

```python
level = pn.Battery.get_level()
state = pn.Battery.get_state()   # "charging" | "full" | "unplugged" | "unknown"
```

## Haptics & vibration

[`Haptics`][pythonnative.Haptics] plays semantic feedback;
[`Vibration`][pythonnative.Vibration] is a blunt duration-based buzz.

```python
pn.Haptics.impact("medium")          # light | medium | heavy | soft | rigid
pn.Haptics.notification("success")   # success | warning | error
pn.Haptics.selection()
pn.Vibration.vibrate(400)            # milliseconds
```

## Biometrics

[`Biometrics`][pythonnative.Biometrics] gates an action behind Face ID /
Touch ID / fingerprint.

```python
async def unlock():
    if pn.Biometrics.is_available() and await pn.Biometrics.authenticate("Unlock"):
        show_secrets()
```

## Writing your own native module

A native module has three parts: a Swift class, a Kotlin class, and a
Python facade. The two native classes are registered under one name by
a plugin entry (the same `pn_plugin.json` layout used for
[custom components](custom-native-components.md)); the facade calls
them by that name and never imports platform code.

### Native side

Each platform's base type is one method that settles a promise:

```swift
// native/ios/CompassModule.swift
import CoreLocation
import PythonNativeKit

public final class CompassModule: NSObject, PNNativeModule, CLLocationManagerDelegate {
    public static let name = "Compass"
    private let manager = CLLocationManager()
    private var pending: PNPromise?

    public override required init() {
        super.init()
        manager.delegate = self
    }

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "is_available":
            promise.resolve(CLLocationManager.headingAvailable())
        case "heading":
            pending = promise               // settled later from the delegate
            manager.startUpdatingHeading()
        default:
            promise.reject("Compass has no method '\(method)'", code: "unknown_method")
        }
    }

    public func locationManager(_ manager: CLLocationManager, didUpdateHeading heading: CLHeading) {
        manager.stopUpdatingHeading()
        pending?.resolve(heading.trueHeading)
        pending = nil
    }
}
```

```kotlin
// native/android/com/example/compass/CompassModule.kt
package com.example.compass

import com.pythonnative.runtime.modules.NativeModule
import com.pythonnative.runtime.modules.Promise
import org.json.JSONObject

class CompassModule : NativeModule {
    override val name = "Compass"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "is_available" -> promise.resolve(true)
            "heading" -> readHeadingOnce { degrees -> promise.resolve(degrees) }
            else -> promise.rejectUnknownMethod(method)
        }
    }
}
```

Settling the promise before `call` returns answers Python inline (a
plain synchronous return). Settling it later, from any thread, delivers
the result through the bridge's event channel on the main thread. Push
unsolicited events with `PNModuleEvents.emit(module:event:payload:)` /
`ModuleEvents.emit(module, event, payload)`.

Register both in the plugin entry next to any component managers:

```swift
registry.registerModule(CompassModule.self)
```

```kotlin
registry.registerModule { CompassModule() }
```

### Python facade

```python
# compass/__init__.py
from typing import Optional

from pythonnative.native_modules.registry import native_module

_compass = native_module("Compass")


class Compass:
    @staticmethod
    def is_available() -> bool:
        return bool(_compass.call("is_available"))

    @staticmethod
    async def heading() -> float:
        return float(await _compass.call_async("heading"))

    @staticmethod
    def add_listener(callback) -> callable:
        return _compass.add_listener("change", callback)
```

`call` is for methods that answer inline; it raises
[`NativeModuleError`][pythonnative.native_modules.registry.NativeModuleError]
when native rejects. `call_async` awaits methods that settle later.
`add_listener` subscribes to module events and returns an unsubscribe
callable.

Follow the two rules the built-in facades follow: pick sync or async by
what the OS does (a heading read is a coroutine here because the sensor
has to spin up), and let `NativeModuleError` propagate rather than
catching it and returning a placeholder. A caller who wants a fallback
can write the `try` themselves; a caller who wanted to know it failed
can't undo a swallowed exception.

### Desktop and test implementation

`native_module("Compass")` returns a
[`BridgeModule`][pythonnative.native_modules.registry.BridgeModule] on
device. Off device it looks for a Python implementation registered
under the same name, so register one for `pn preview` and unit tests:

```python
from pythonnative.native_modules.registry import register_python_module


class DesktopCompass:
    def is_available(self) -> bool:
        return False

    def heading(self) -> float:
        return 0.0


register_python_module("Compass", DesktopCompass())
```

Methods are looked up by name and called with the same keyword
arguments the facade passed; a coroutine function is awaited by
`call_async`. Packages register their desktop implementations through
the `pythonnative.modules` entry point group so they are found without
an explicit import:

```toml
[project.entry-points."pythonnative.modules"]
compass = "compass.desktop"
```

Tests can push module events directly with
[`emit`][pythonnative.native_modules.registry.emit] to exercise
listeners without a device.

## Next steps

- Reference: [Native modules API](../api/native_modules.md).
- Async hooks and data fetching: [Async + data](async.md).
- See how device APIs interact with focus: [Lifecycle](../concepts/lifecycle.md).
- Wrap a custom widget instead of an API: [Custom native components](custom-native-components.md).
- Wire protocol and plugin layout: [The native bridge](../concepts/bridge.md).
