package com.pythonnative.plugins.location

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import com.pythonnative.generated.LocationImplementation
import com.pythonnative.generated.LocationModuleAdapter
import com.pythonnative.generated.PNLocationGetCurrentAccuracy
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.modules.PNModuleError
import com.pythonnative.runtime.modules.PNPermissions

private const val FINE_LOCATION = "android.permission.ACCESS_FINE_LOCATION"
private const val COARSE_LOCATION = "android.permission.ACCESS_COARSE_LOCATION"

/** Registers `Location` and owns the `location_when_in_use` permission. */
object LocationPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { LocationModuleAdapter(LocationModule()) }
        PNPermissions.register("location_when_in_use", FINE_LOCATION, arrayOf(FINE_LOCATION, COARSE_LOCATION), satisfiedBy = COARSE_LOCATION)
    }
}

/**
 * `Location.get_current()`: requests when-in-use permission inline
 * (`ACCESS_FINE_LOCATION` + `ACCESS_COARSE_LOCATION`, through the
 * Permissions module's request machinery) and then reads the last known
 * fix if fresh enough, otherwise a single `network`/`gps` update with a
 * timeout. Resolves to `{latitude, longitude, ...}`, or `null` only when
 * the permission was denied, no provider is enabled, or the timeout
 * elapsed.
 */
class LocationModule : LocationImplementation {
    private val watchers = HashMap<Long, () -> Unit>()
    private var nextWatcher = 1L

    override fun start_watching(accuracy: PNLocationGetCurrentAccuracy, distance: Double, completion: (Result<Long>) -> Unit): (() -> Unit)? {
        val id = nextWatcher++
        val begin = {
            completion(runCatching {
                watchers[id] = beginUpdates(id, accuracy == PNLocationGetCurrentAccuracy.`high`, distance)
                id
            })
        }
        val permissions = BuiltinModules.permissions
        if (permissions.isGranted(FINE_LOCATION) || permissions.isGranted(COARSE_LOCATION)) {
            begin()
            return null
        }
        return permissions.requestManifest(arrayOf(FINE_LOCATION, COARSE_LOCATION)) { results ->
            if (results.any { it == PackageManager.PERMISSION_GRANTED }) begin()
            else completion(Result.failure(PNModuleError("Location permission was denied", "permission_denied")))
        }
    }

    override fun stop_watching(id: Long) {
        watchers.remove(id)?.invoke()
    }

    @SuppressLint("MissingPermission")
    private fun beginUpdates(id: Long, high: Boolean, distance: Double): () -> Unit {
        val manager = PNBridge.context().getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val providers = manager.getProviders(true)
        val provider = when {
            high && LocationManager.GPS_PROVIDER in providers -> LocationManager.GPS_PROVIDER
            LocationManager.NETWORK_PROVIDER in providers -> LocationManager.NETWORK_PROVIDER
            else -> providers.firstOrNull() ?: throw PNModuleError("No location provider is enabled", "unavailable")
        }
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                ModuleEvents.emit("Location", "position", mapOf("id" to id, "value" to coords(location)))
            }
            override fun onProviderEnabled(provider: String) {}
            override fun onProviderDisabled(provider: String) {}
            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        }
        manager.requestLocationUpdates(provider, 1000L, distance.toFloat(), listener, android.os.Looper.getMainLooper())
        return { manager.removeUpdates(listener) }
    }

    override fun get_current(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: (Result<Map<String, Double>?>) -> Unit): (() -> Unit)? {
        val permissions = BuiltinModules.permissions
        if (permissions.isGranted(FINE_LOCATION) || permissions.isGranted(COARSE_LOCATION)) {
            return read(accuracy, timeout, completion)
        }
        var cancelled = false
        var cancelRead: (() -> Unit)? = null
        val cancelRequest = permissions.requestManifest(arrayOf(FINE_LOCATION, COARSE_LOCATION)) { results ->
            if (cancelled) return@requestManifest
            val granted = results.any { it == PackageManager.PERMISSION_GRANTED }
            if (!granted) completion(Result.success(null)) else cancelRead = read(accuracy, timeout, completion)
        }
        return {
            cancelled = true
            cancelRequest?.invoke()
            cancelRead?.invoke()
        }
    }

    @SuppressLint("MissingPermission")
    private fun read(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: (Result<Map<String, Double>?>) -> Unit): (() -> Unit)? {
        val lm = PNBridge.context().getSystemService(Context.LOCATION_SERVICE) as? LocationManager
            ?: run { completion(Result.success(null)); return null }
        try {
            for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
                val last = lm.getLastKnownLocation(provider) ?: continue
                if (System.currentTimeMillis() - last.time < 60_000) { completion(Result.success(coords(last))); return null }
            }
        } catch (_: SecurityException) { completion(Result.success(null)); return null }
        catch (error: Exception) { PNLog.swallowed("Location.lastKnown", error) }
        var settled = false
        var timer: Runnable? = null
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                if (settled) return
                settled = true
                timer?.let { MainThread.remove(it) }
                lm.removeUpdates(this)
                completion(Result.success(coords(location)))
            }
            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
            override fun onProviderEnabled(provider: String) {}
            override fun onProviderDisabled(provider: String) {}
        }
        val cancel = {
            settled = true
            timer?.let { MainThread.remove(it) }
            lm.removeUpdates(listener)
        }
        try {
            val provider = when {
                accuracy.rawValue == "high" && lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
                lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
                lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
                else -> { completion(Result.success(null)); return null }
            }
            timer = Runnable { if (!settled) { cancel(); completion(Result.success(null)) } }
            lm.requestLocationUpdates(provider, 1000L, 0f, listener)
            MainThread.postDelayed(timer!!, (timeout.coerceIn(1.0, 86400.0) * 1000).toLong())
        } catch (error: Exception) {
            cancel()
            completion(Result.failure(error))
            return null
        }
        return cancel
    }

    private fun coords(location: Location): Map<String, Double> = buildMap {
        put("latitude", location.latitude); put("longitude", location.longitude)
        put("accuracy", location.accuracy.toDouble()); put("timestamp", location.time / 1000.0)
        if (location.hasAltitude()) put("altitude", location.altitude)
        if (location.hasSpeed()) put("speed", location.speed.toDouble())
        if (location.hasBearing()) put("heading", location.bearing.toDouble())
    }
}

