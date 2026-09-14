package com.pythonnative.runtime.modules

import com.pythonnative.generated.*

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.provider.MediaStore
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import java.io.File
import java.io.FileOutputStream

/**
 * `Camera.take_photo()` / `pick_from_gallery()`: launch the system
 * capture or pick intent and resolve to the resulting path (a content
 * URI string, or a JPEG written to the cache dir for thumbnails) or
 * `null` when cancelled.
 */
class CameraModule : CameraImplementation {
    private data class Pending(val quality: Int, val done: (Result<String?>) -> Unit)
    private val pending = HashMap<Int, Pending>()

    override fun take_photo(quality: Double, allow_editing: Boolean, completion: (Result<String?>) -> Unit): (() -> Unit)? =
        launch(Intent(MediaStore.ACTION_IMAGE_CAPTURE), quality, allow_editing, completion)
    override fun pick_from_gallery(quality: Double, allow_editing: Boolean, completion: (Result<String?>) -> Unit): (() -> Unit)? =
        launch(Intent(Intent.ACTION_PICK).apply { type = "image/*" }, quality, allow_editing, completion)

    private fun launch(intent: Intent, quality: Double, editing: Boolean, completion: (Result<String?>) -> Unit): (() -> Unit)? {
        if (editing) { completion(Result.failure(UnsupportedOperationException("Camera editing requires a provider plugin on Android"))); return null }
        val activity = PNBridge.activity() ?: run { completion(Result.success(null)); return null }
        val code = RequestCodes.next()
        pending[code] = Pending((quality.coerceIn(0.0, 1.0) * 100).toInt(), completion)
        try {
            @Suppress("DEPRECATION")
            activity.startActivityForResult(intent, code)
        } catch (error: Exception) {
            pending.remove(code)
            completion(Result.failure(error))
            return null
        }
        return {
            pending.remove(code)
            @Suppress("DEPRECATION")
            activity.finishActivity(code)
        }
    }

    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        val request = pending.remove(requestCode) ?: return false
        if (resultCode != Activity.RESULT_OK || data == null) { request.done(Result.success(null)); return true }
        try {
            val uri = data.data
            @Suppress("DEPRECATION")
            val thumb = data.extras?.get("data") as? Bitmap
            val path = if (uri != null) uri.toString() else if (thumb != null) {
                val target = File.createTempFile("pn-camera-", ".jpg", PNBridge.context().cacheDir)
                FileOutputStream(target).use { check(thumb.compress(Bitmap.CompressFormat.JPEG, request.quality, it)) }
                target.absolutePath
            } else null
            request.done(Result.success(path))
        } catch (error: Exception) { request.done(Result.failure(error)) }
        return true
    }
}

/**
 * `Location.get_current()`: the last known fix if fresh enough,
 * otherwise a single `network`/`gps` update with a 15 s timeout.
 * Resolves to `{latitude, longitude}` or `null`.
 */
class LocationModule : LocationImplementation {
    @SuppressLint("MissingPermission")
    override fun get_current(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: (Result<Map<String, Double>?>) -> Unit): (() -> Unit)? {
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

/** `Biometrics.is_available()` (sync bool) and `authenticate(reason)` (async bool via `BiometricPrompt`). */
class BiometricsModule : BiometricsImplementation {
    override fun is_available(): Boolean = try {
        BiometricManager.from(PNBridge.context()).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK) == BiometricManager.BIOMETRIC_SUCCESS
    } catch (_: Exception) { false }

    override fun authenticate(reason: String, completion: (Result<Boolean>) -> Unit): (() -> Unit)? {
        val activity = PNBridge.activity() as? FragmentActivity ?: run { completion(Result.success(false)); return null }
        if (!is_available()) { completion(Result.success(false)); return null }
        return try {
            val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = completion(Result.success(true))
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) = completion(Result.success(false))
                override fun onAuthenticationFailed() {}
            })
            val info = BiometricPrompt.PromptInfo.Builder().setTitle(reason).setNegativeButtonText("Cancel")
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK).build()
            prompt.authenticate(info)
            val cancel: () -> Unit = { prompt.cancelAuthentication() }
            cancel
        } catch (error: Exception) { completion(Result.failure(error)); null }
    }
}
