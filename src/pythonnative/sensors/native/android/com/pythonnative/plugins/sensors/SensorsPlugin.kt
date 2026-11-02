package com.pythonnative.plugins.sensors

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import com.pythonnative.generated.PNSensorsIsAvailableSensor
import com.pythonnative.generated.SensorsImplementation
import com.pythonnative.generated.SensorsModuleAdapter
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.modules.PNModuleError
import com.pythonnative.runtime.modules.PNPermissions

/** Registers `Sensors` and owns the `motion` permission. */
object SensorsPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { SensorsModuleAdapter(SensorsModule()) }
        // None of these sensors needs it. `motion` means this on Android for
        // apps that read step or activity data, and it's a runtime permission
        // only from API 29.
        PNPermissions.register("motion", "android.permission.ACTIVITY_RECOGNITION", minSdk = 29)
    }
}

/**
 * `Sensors`: `SensorManager` already reports m/s^2, rad/s, microtesla, and hPa,
 * with the signs the Python facade promises. Only the clock needs converting.
 */
class SensorsModule : SensorsImplementation {
    private val listeners = HashMap<Long, SensorEventListener>()
    private var nextId = 1L

    private val manager: SensorManager
        get() = PNBridge.context().getSystemService(Context.SENSOR_SERVICE) as SensorManager

    /** Serializing readings at 100 Hz is work the UI thread shouldn't do. */
    private val handler: Handler by lazy {
        Handler(HandlerThread("pn-sensors").apply { start() }.looper)
    }

    private fun hardware(sensor: PNSensorsIsAvailableSensor): Sensor? = manager.getDefaultSensor(
        when (sensor) {
            PNSensorsIsAvailableSensor.`accelerometer` -> Sensor.TYPE_ACCELEROMETER
            PNSensorsIsAvailableSensor.`gyroscope` -> Sensor.TYPE_GYROSCOPE
            PNSensorsIsAvailableSensor.`magnetometer` -> Sensor.TYPE_MAGNETIC_FIELD
            PNSensorsIsAvailableSensor.`barometer` -> Sensor.TYPE_PRESSURE
        },
    )

    override fun is_available(sensor: PNSensorsIsAvailableSensor): Boolean = hardware(sensor) != null

    override fun start(hz: Double, sensor: PNSensorsIsAvailableSensor, completion: (Result<Long>) -> Unit): (() -> Unit)? {
        val source = hardware(sensor)
        if (source == null) {
            completion(Result.failure(PNModuleError("This device has no ${sensor.rawValue}", "unavailable")))
            return null
        }
        val id = nextId++
        val isBarometer = sensor == PNSensorsIsAvailableSensor.`barometer`
        // `SensorEvent.timestamp` counts nanoseconds from boot; this turns it into Unix seconds.
        val bootTime = System.currentTimeMillis() / 1000.0 - SystemClock.elapsedRealtimeNanos() / 1e9
        // The hardware runs at the fastest rate any app on the device asked for.
        // A little slack, so a jittery sample doesn't halve a matching rate.
        val minimumGap = (0.8e9 / hz).toLong()
        val listener = object : SensorEventListener {
            private var last = 0L

            override fun onSensorChanged(event: SensorEvent) {
                if (event.timestamp - last < minimumGap) return
                last = event.timestamp
                val timestamp = bootTime + event.timestamp / 1e9
                val value: Map<String, Double> = if (isBarometer) {
                    mapOf("hpa" to event.values[0].toDouble(), "timestamp" to timestamp)
                } else {
                    mapOf(
                        "x" to event.values[0].toDouble(),
                        "y" to event.values[1].toDouble(),
                        "z" to event.values[2].toDouble(),
                        "timestamp" to timestamp,
                    )
                }
                ModuleEvents.emit("Sensors", "reading", mapOf("id" to id, "value" to value))
            }

            override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) {}
        }
        if (!manager.registerListener(listener, source, (1_000_000 / hz).toInt(), handler)) {
            completion(Result.failure(PNModuleError("The ${sensor.rawValue} couldn't start", "unavailable")))
            return null
        }
        listeners[id] = listener
        completion(Result.success(id))
        return null
    }

    override fun stop(id: Long) {
        listeners.remove(id)?.let { manager.unregisterListener(it) }
    }
}
