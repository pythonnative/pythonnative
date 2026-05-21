# Native modules

Native modules are PythonNative's wrappers around device APIs that
aren't part of the view tree: the camera, GPS, app-scoped file I/O,
and local notifications. Each module is implemented twice (once per
platform) and dispatches at runtime based on `utils.IS_ANDROID` /
`utils.IS_IOS`, so app code stays single-source.

Apart from `FileSystem`, every public method is a coroutine —
`async def take_photo()`, `async def get_current()`, and so on. The
typical call site uses `await` (inside a component, that means
[`use_async_effect`][pythonnative.hooks.use_async_effect],
[`use_query`][pythonnative.hooks.use_query], or
[`pn.run_async(coro)`][pythonnative.runtime.run_async] from a sync
handler).

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
        pn.Button("Take photo", on_click=lambda: pn.run_async(take())),
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
system surface is synchronous — local disk reads are typically
faster than the cost of hopping onto the asyncio loop. For large
files you can opt into a worker thread:

```python
import asyncio
import pythonnative as pn

# Sync — fine for small files (preferences, JSON state, etc.)
pn.FileSystem.write_text("notes.txt", "hello")
text = pn.FileSystem.read_text("notes.txt")

# Async — explicitly offload to a worker thread for big payloads.
text = await asyncio.to_thread(pn.FileSystem.read_text, "big.txt")
```

!!! tip "Need just a key-value store?"
    Prefer [`AsyncStorage`][pythonnative.storage.AsyncStorage] over
    serialising JSON into a file by hand — it's the native
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

## Writing your own native module

A native module is just a class with two implementations behind a
runtime dispatch. Coroutine wrappers should bridge native delegates
through the [`pn.runtime`](../api/runtime.md) helpers:

```python
import asyncio

from pythonnative.runtime import resolve_future
from pythonnative.utils import IS_ANDROID, IS_IOS


class Battery:
    @staticmethod
    async def get_level() -> float:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[float] = loop.create_future()

        if IS_ANDROID:
            from java import jclass

            from pythonnative.utils import get_android_context

            ctx = get_android_context()
            mgr = ctx.getSystemService("batterymanager")
            level = mgr.getIntProperty(jclass(...).BATTERY_PROPERTY_CAPACITY) / 100.0
            resolve_future(future, level)
        elif IS_IOS:
            from rubicon.objc import ObjCClass

            UIDevice = ObjCClass("UIDevice")
            UIDevice.currentDevice.batteryMonitoringEnabled = True
            resolve_future(future, float(UIDevice.currentDevice.batteryLevel))
        else:
            raise RuntimeError("Battery is only available on Android or iOS")

        return await future
```

Keep platform imports inside the platform branch so the desktop
import path doesn't pull in Chaquopy or rubicon-objc.

## Next steps

- Reference: [Native modules API](../api/native_modules.md).
- Async hooks and data fetching: [Async + data](async.md).
- See how device APIs interact with focus: [Lifecycle](../concepts/lifecycle.md).
- Wrap a custom widget instead of an API: [Native views](../concepts/native-views.md).
