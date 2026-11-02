# Sensors

`pythonnative.sensors` streams the device's motion and pressure sensors as async
iterators. Every platform reports the same units and axes, so code doesn't branch
on `Platform.OS`.

## Setup

```toml
[plugins]
use = ["sensors"]

[permissions]
motion = "Measure air pressure for your altitude."
```

The `motion` line is required, even if you only read the accelerometer. iOS's
`CMAltimeter`, behind `Barometer`, terminates the app at the call when
`NSMotionUsageDescription` is missing, and the plugin compiles that API in. Only
`Barometer` can actually show the prompt: reading the accelerometer, gyroscope, or
magnetometer never does.

On Android, none of these sensors needs a permission. `motion` also adds
`ACTIVITY_RECOGNITION` to the manifest, because that's what the name means for apps
reading step or activity data, but the sensors here never check it.

## Using it

Each sensor is a class with `is_available()` and `readings(hz=30)`. Leaving the
`async for`, or canceling its task, stops the hardware, so a stream fits in
`use_effect`:

```python
import pythonnative as pn
from pythonnative.sensors import Accelerometer


@pn.component
def Tilt() -> pn.Node:
    latest, set_latest = pn.use_state(None)

    async def watch() -> None:
        if Accelerometer.is_available():
            async for reading in Accelerometer.readings(hz=30):
                set_latest(reading)

    pn.use_effect(watch, [])
    return pn.Text("No sensor" if latest is None else f"z = {latest.z:.2f} m/s^2")
```

`Accelerometer`, `Gyroscope`, and `Magnetometer` yield
[`Vector`][pythonnative.sensors.Vector]`(x, y, z, timestamp)`. `Barometer` yields
[`Pressure`][pythonnative.sensors.Pressure]`(hpa, timestamp)`. Both are frozen
dataclasses, and `timestamp` is Unix seconds on every platform.

`readings` raises `NativeModuleError` with the code `unavailable` when the device
has no such sensor, which `is_available()` tells you ahead of time. `hz` must be
above 0 and at most 100, which is CoreMotion's ceiling, and the hardware may deliver
a different rate.

## Units and axes

Axes are the device's, on every platform: `x` toward the right edge of the screen,
`y` toward its top edge, and `z` out of its face.

| Sensor | Unit | iOS reports | Android reports | Conversion on iOS |
| --- | --- | --- | --- | --- |
| `Accelerometer` | m/s^2, including gravity | g | m/s^2 | Multiply by -9.80665 |
| `Gyroscope` | rad/s, counterclockwise positive | rad/s | rad/s | None |
| `Magnetometer` | microtesla | microtesla | microtesla | None |
| `Barometer` | hPa | kPa | hPa | Multiply by 10 |

**The accelerometer's sign.** A device at rest, flat on a table with its screen up,
reads `z` of about **+9.81**: the sensor reports the table pushing up on it. Android
and the W3C `DeviceMotionEvent` spec work this way. CoreMotion reports the opposite,
-1 g, so iOS negates every axis as well as scaling it. Turning the phone upright
reads `y` of about +9.81 everywhere.

## Platform differences

| | iOS | Android | Browser preview |
| --- | --- | --- | --- |
| Engine | `CMMotionManager`, `CMAltimeter` | `SensorManager` | `DeviceMotionEvent` |
| `Accelerometer`, `Gyroscope` | Yes | Yes | On touch devices |
| `Magnetometer`, `Barometer` | Yes | Where the hardware exists | Never: no browser API |
| `Barometer` rate | About 1 Hz, ignoring `hz` | Follows `hz` where the hardware can | |
| `Barometer` prompt | Motion and Fitness, on first use | None | |
| `Magnetometer` values | Raw, including the device's own bias | Calibrated | |

iOS's raw magnetometer can read hundreds of microtesla from the device's own
magnetism, where Android's calibrated value stays around 25 to 65. Don't build a
compass on the raw value without calibrating it.

When the user refuses Motion and Fitness access, `Barometer.readings` raises
`NativeModuleError` with the code `permission_denied`.

In the browser preview, `Accelerometer` and `Gyroscope` read `DeviceMotionEvent` on
touch devices. A desktop browser defines the event but never fires it with real
values, so sensors are unavailable there. Safari on iOS grants motion access only
during a user gesture, which the preview's round trip through Python can lose, so
expect a refusal there.

## What a simulator can't verify

- **The iOS simulator has no sensors.** `is_available()` is `False` for all four,
  and `readings` raises `unavailable`. That's all it can show. The CoreMotion paths,
  including the unit conversions, the Motion and Fitness prompt, and the
  `permission_denied` path, need a real device.
- **The Android emulator has virtual sensors,** so its values are real readings of a
  fake device. Set them with `adb emu sensor set acceleration 1:2:3`.
