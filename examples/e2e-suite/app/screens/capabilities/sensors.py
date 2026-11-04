"""Demo screen for [`pythonnative.sensors`][pythonnative.sensors].

Each sensor reports whether it's available. Starting one streams its readings
into the readouts until the screen goes away or "Stop" cancels the effect. On
the iOS simulator nothing is available, so starting shows the ``unavailable``
error; the Android emulator's virtual sensors stream real values.
"""

from __future__ import annotations

from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.native_modules.registry import NativeModuleError
from pythonnative.sensors import Accelerometer, Barometer, Gyroscope, Magnetometer


@pn.component
def SensorsDemo() -> pn.Node:
    """Render availability readouts and a start/stop stream of accelerometer readings."""
    running, set_running = pn.use_state(False)
    count, set_count = pn.use_state(0)
    latest, set_latest = pn.use_state("none")
    error, set_error = pn.use_state("none")

    async def stream() -> None:
        if not running:
            return
        try:
            async for reading in Accelerometer.readings(hz=10):
                set_count(lambda total: total + 1)
                set_latest(f"{reading.x:.2f}, {reading.y:.2f}, {reading.z:.2f}")
        except NativeModuleError as failure:
            set_error(failure.code or "unknown")
            set_running(False)

    pn.use_effect(stream, [running])

    return DemoScreen(
        "Sensors",
        "Availability, and a stream that stops with its effect.",
        DemoSection(
            "Availability",
            ResultText("Accelerometer", "yes" if Accelerometer.is_available() else "no"),
            ResultText("Gyroscope", "yes" if Gyroscope.is_available() else "no"),
            ResultText("Magnetometer", "yes" if Magnetometer.is_available() else "no"),
            ResultText("Barometer", "yes" if Barometer.is_available() else "no"),
        ),
        DemoSection(
            "Accelerometer stream",
            pn.Button("Stop readings" if running else "Start readings", on_press=lambda: set_running(not running)),
            ResultText("Running", "yes" if running else "no"),
            ResultText("Readings", "some" if count else "none"),
            ResultText("Latest", latest),
            ResultText("Stream error", error),
            Hint("In m/s^2, including gravity. Flat on a table with the screen up, z is about +9.81."),
        ),
    )
