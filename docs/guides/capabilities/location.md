# Location

One position fix, or a stream of them while the app is in use.

## Setup

```toml
[plugins]
use = ["location"]

[permissions]
location_when_in_use = "Show nearby stores."
```

## Usage

```python
from pythonnative.location import Location


async def show_position() -> None:
    position = await Location.get_current(accuracy="high", timeout=10)
    if position is None:
        return  # permission denied, location services off, or it timed out
    print(position.latitude, position.longitude, position.accuracy)
```

The call prompts for permission when it needs to. Everything except `latitude` and `longitude` is
`None` when the platform doesn't report it.

`Location.watch` is an async iterator. Leaving the loop stops the updates, and so does canceling its task, so it fits an effect:

```python
@pn.component
def Tracker() -> pn.Node:
    position, set_position = pn.use_state(None)

    async def follow() -> None:
        async for fix in Location.watch(distance=10):
            set_position(fix)

    pn.use_effect(follow, [])
    return pn.Text(f"{position.latitude}, {position.longitude}" if position else "Locating...")
```

`distance` is how far, in meters, the device must move between updates. A refused permission raises
`NativeModuleError` with the code `permission_denied`.

## Platform differences

- iOS uses `CLLocationManager`, and Android uses `LocationManager`, so a device with no Google Play services still works.
- `accuracy="high"` asks Android for GPS when it's enabled and iOS for its best accuracy. `"balanced"` saves power.
- Updates stop when the app is in the background on both platforms; background location isn't supported.
- The browser preview uses the Geolocation API.

## What wasn't verified

The iOS simulator and Android emulator report a position you set, so CI proves the capability answers, not that a fix is accurate.
Continuous updates on physical devices haven't been tested.
