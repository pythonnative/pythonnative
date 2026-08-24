# Native modules

Native modules are PythonNative's wrappers around device APIs that
aren't part of the view tree: the camera, GPS, file I/O, clipboard,
share sheet, deep links, permissions, connectivity, secure storage,
battery, haptics, and biometrics. Each module is implemented twice
(once per platform) and dispatches at runtime based on
`utils.IS_ANDROID` / `utils.IS_IOS`, so app code stays single-source.
Off-device (desktop), each module falls back to a safe default
(in-memory buffers, `"unknown"` states, no-op feedback) so the same
code runs in the desktop mock and in unit tests.

Both synchronous and coroutine APIs exist, chosen to match the
underlying platform call:

- **Synchronous**: `Clipboard`, `Linking`, `Haptics` / `Vibration`,
  `Battery`, `NetInfo`, `SecureStore`, `AppState`, `FileSystem`,
  `Permissions.check`. These answer immediately.
- **Coroutines** (`await` them): `Camera.take_photo`,
  `Location.get_current`, `Share.share`, `Permissions.request`,
  `Biometrics.authenticate`, `Notifications.*`. Inside a component,
  drive them with an `async def`
  [`use_effect`][pythonnative.use_effect] callback,
  [`use_resource`][pythonnative.use_resource],
  [`use_query`][pythonnative.hooks.use_query], or
  [`pn.run_async(coro)`][pythonnative.runtime.run_async] from a sync
  handler.

Two modules also ship reactive hooks:
[`use_app_state`][pythonnative.use_app_state] and
[`use_net_info`][pythonnative.use_net_info].

## Permissions: declare them once, request at runtime

PythonNative does not edit `Info.plist` or `AndroidManifest.xml` for
you. You declare what your app needs in the platform manifests, and
the operating system shows the permission prompt the first time you
call into the API.

=== "Android (`android_template/app/src/main/AndroidManifest.xml`)"

    ```xml
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    ```

=== "iOS (`ios_template/Info.plist`)"

    ```xml
    <key>NSCameraUsageDescription</key>
    <string>So you can take photos in MyApp.</string>
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>So MyApp can show nearby content.</string>
    <key>NSPhotoLibraryUsageDescription</key>
    <string>So you can pick photos from your library.</string>
    ```

The exact strings on iOS appear in the system permission dialog, so
write them as you would want a user to read them.

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

[`FileSystem`][pythonnative.native_modules.file_system.FileSystem] is
scoped to your app's documents directory; relative paths are resolved
inside that sandbox automatically. Unlike the other modules, the file
system surface is synchronous; local disk reads are typically
faster than the cost of hopping onto the asyncio loop. For large
files you can opt into a worker thread:

```python
import asyncio
import pythonnative as pn

# Sync: fine for small files (preferences, JSON state, etc.)
pn.FileSystem.write_text("notes.txt", "hello")
text = pn.FileSystem.read_text("notes.txt")

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
Settings page, and reports the URL that launched the app.

```python
if pn.Linking.can_open_url("tel:+15551234567"):
    pn.Linking.open_url("tel:+15551234567")

launch_url = pn.Linking.get_initial_url()  # deep link the app opened with
pn.Linking.open_settings()                 # this app's entry in Settings
```

## Permissions (runtime)

[`Permissions`][pythonnative.Permissions] normalizes the iOS/Android
permission models. `check` is synchronous; `request` prompts and is a
coroutine. Names: `"camera"`, `"microphone"`, `"location"`, `"photos"`,
`"notifications"`, `"contacts"`. Statuses: `"granted"`, `"denied"`,
`"blocked"`, `"undetermined"`.

```python
if pn.Permissions.check("camera") != "granted":
    status = await pn.Permissions.request("camera")
    if status == "blocked":
        pn.Linking.open_settings()  # user must enable it in Settings
```

You still declare the permission in the platform manifest (above); the
OS shows the prompt the first time you `request` it.

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
pn.SecureStore.set_item("auth_token", token)
token = pn.SecureStore.get_item("auth_token")
pn.SecureStore.delete_item("auth_token")
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

A native module is just a class with two implementations behind a
runtime dispatch. The built-in modules above all follow this shape.
Coroutine wrappers should bridge native delegates through the
[`pn.runtime`](../api/runtime.md) helpers:

```python
import asyncio

from pythonnative.runtime import resolve_future
from pythonnative.utils import IS_ANDROID, IS_IOS


class Compass:
    @staticmethod
    async def heading() -> float:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[float] = loop.create_future()

        if IS_ANDROID:
            from java import jclass  # noqa: F401

            from pythonnative.utils import get_android_context

            ctx = get_android_context()
            # ... subscribe to the SensorManager and resolve_future(future, deg)
            resolve_future(future, 0.0)
        elif IS_IOS:
            from rubicon.objc import ObjCClass  # noqa: F401

            # ... start CLLocationManager heading updates, resolve on the first fix
            resolve_future(future, 0.0)
        else:
            resolve_future(future, 0.0)  # desktop fallback

        return await future
```

Keep platform imports inside the platform branch so the desktop
import path doesn't pull in Chaquopy or rubicon-objc. Prefer a safe
desktop fallback (a default value / no-op) over raising, so the same
code stays runnable in the desktop mock and in unit tests.

## Next steps

- Reference: [Native modules API](../api/native_modules.md).
- Async hooks and data fetching: [Async + data](async.md).
- See how device APIs interact with focus: [Lifecycle](../concepts/lifecycle.md).
- Wrap a custom widget instead of an API: [Native views](../concepts/native-views.md).
