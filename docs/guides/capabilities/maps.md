# Maps

`pythonnative.maps` shows a native map: MapKit on iOS and the Google Maps SDK on
Android. Markers and polylines are typed data in props, not child elements, so
a list of them is an ordinary value you can keep in state.

## Setup

```toml
[plugins]
use = ["maps"]
```

iOS needs nothing else. Android needs an API key from the
[Google Cloud console](https://console.cloud.google.com/google/maps-apis/credentials)
with the Maps SDK for Android enabled. Set it in one of two ways:

```toml
[plugins.maps]
android_api_key = "..."
```

```sh
GOOGLE_MAPS_API_KEY=... pn build android
```

Prefer the environment variable if the file is checked in. A key in the table
wins when both are set. The key is written to the Android manifest as
`com.google.android.geo.API_KEY`, so it's readable in the built app; restrict it
to your package name and signing certificate in the console.

A project with no key still builds and runs. The view then explains what's
missing and calls `on_error`.

Maps declares no required permission. See [Showing the user's location](#showing-the-users-location).

## Using it

A map has no intrinsic size, so give it one with `style`.

```python
import pythonnative as pn
from pythonnative.maps import Coordinate, MapView, Marker, Polyline, Region

OSLO = Coordinate(59.9139, 10.7522)
BERGEN = Coordinate(60.3913, 5.3221)


@pn.component
def Route() -> pn.Node:
    map_ref = pn.use_ref()
    chosen, set_chosen = pn.use_state(None)
    return pn.Column(
        MapView(
            ref=map_ref,
            initial_region=Region(OSLO, latitude_delta=6, longitude_delta=12),
            markers=[
                Marker("oslo", OSLO, title="Oslo", color="#2563EB"),
                Marker("bergen", BERGEN, title="Bergen", description="End of the line"),
            ],
            polylines=[Polyline("train", [OSLO, BERGEN], color="#DC2626", width=3)],
            on_marker_press=set_chosen,
            style=pn.style(flex=1),
        ),
        pn.Text(chosen or "Pick a city"),
        pn.Button("Go to Bergen", on_press=lambda: map_ref.current.animate_to(Region(BERGEN, 1, 1))),
        style=pn.style(flex=1),
    )
```

### Where the map looks

| You want | Use |
| --- | --- |
| A starting place, then let the user roam | `initial_region` |
| Python decides where the map is | `region`, which moves it without animating |
| A one-off animated move | `ref.current.animate_to(region)` |

A map fits the region it's given to its own shape and zoom levels, so the region
`on_region_change` reports is close to the one requested but rarely equal to it.
It's safe to store that region and pass it back as `region`: one within a rounding
error (0.1 percent of the span) of the current view is ignored, so this can't loop.

### Events

| Prop | Called with | When |
| --- | --- | --- |
| `on_ready` | nothing | Once, when the map can be controlled |
| `on_region_change` | `Region` | The map stopped moving, however it was moved |
| `on_press` | `Coordinate` | A press on the map itself |
| `on_marker_press` | The marker's `id` | A press on a marker |
| `on_error` | A message | The map can't work (see below) |

### Showing the user's location

`shows_user_location=True` draws the user's position, but doesn't ask for
permission. The app has to hold it first, and the `location` capability is what
provides that permission:

```toml
[plugins]
use = ["maps", "location"]

[permissions]
location_when_in_use = "Show where you are on the map."
```

```python
from pythonnative import Permissions

status = await Permissions.request("location_when_in_use")
```

Without the permission, Android calls `on_error` and tries again the next time the
app resumes, and iOS simply draws no location.

## Platform differences

| | iOS | Android |
| --- | --- | --- |
| Engine | MapKit | Google Maps SDK (`play-services-maps`) |
| Key | None | Required |
| Device requirement | None | Google Play services |
| `on_ready` | First render finished, or the load failed | The map object exists, before tiles load |
| `on_error` | Map data failed to load | No key, no Play services, or no location permission |
| Pressing a selected marker | Doesn't fire `on_marker_press` again | Fires it every time |
| `Marker.color` | Any color | Only the hue: Google's pin has no other tint |
| A marker press | Shows its callout | Shows its info window and centers on it |

The Android view forwards `onCreate`, `onStart`, `onResume`, `onPause`, `onStop`,
`onDestroy`, and `onLowMemory` to the SDK's `MapView` for you, combining the
activity's state with whether the view is attached to a window. It doesn't forward
`onSaveInstanceState`: Python holds the region, so a recreated map comes back where
its props say.

In the browser preview, `MapView` is a labeled plate with the markers and lines in
their relative positions. There are no tiles and nothing leaves the page. `on_ready`,
`on_press`, `on_marker_press`, `on_region_change`, `region`, and `animate_to` work;
there's no panning or zooming.

## What a simulator can't verify

- **A wrong Android key isn't detectable.** The SDK logs `Authorization failure` to
  Logcat and draws an empty map with its logo. No callback reports it, so `on_error`
  can't, and neither can `pn doctor`. `on_ready` still fires. Check Logcat if the map
  is blank.
- **Android tiles, markers, and lines need a real key.** With a placeholder key the
  SDK starts, follows the lifecycle, and accepts camera moves, but it draws nothing,
  never fires `on_region_change`, and doesn't finish `animate_to`. So those, and
  `on_marker_press`, weren't verified on Android. On iOS, MapKit needs no key, and
  all of them were.
- **A device without Play services** needs an emulator image without them (the
  `AOSP` system images) to see that message.
- **The user's location** needs the simulator's simulated location, or a device.
