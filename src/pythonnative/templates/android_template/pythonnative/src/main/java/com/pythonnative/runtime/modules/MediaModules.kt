package com.pythonnative.runtime.modules

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
import com.pythonnative.runtime.bridge.str
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

/**
 * `Camera.take_photo()` / `pick_from_gallery()`: launch the system
 * capture or pick intent and resolve to the resulting path (a content
 * URI string, or a JPEG written to the cache dir for thumbnails) or
 * `null` when cancelled.
 */
class CameraModule : NativeModule {
    override val name = "Camera"
    private val pending = HashMap<Int, Promise>()

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "take_photo" -> launch(Intent(MediaStore.ACTION_IMAGE_CAPTURE), promise)
            "pick_from_gallery" -> launch(Intent(Intent.ACTION_PICK).apply { type = "image/*" }, promise)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    private fun launch(intent: Intent, promise: Promise) {
        val activity = PNBridge.activity() ?: return promise.resolve(null)
        val code = RequestCodes.next()
        pending[code] = promise
        try {
            @Suppress("DEPRECATION")
            activity.startActivityForResult(intent, code)
        } catch (e: Exception) {
            pending.remove(code)
            PNLog.swallowed("Camera.launch", e)
            promise.resolve(null)
        }
    }

    /** Route `Activity.onActivityResult`; `true` when a pending picker matched. */
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        val promise = pending.remove(requestCode) ?: return false
        var path: String? = null
        if (resultCode == Activity.RESULT_OK && data != null) {
            val uri = data.data
            if (uri != null) {
                path = uri.toString()
            } else {
                @Suppress("DEPRECATION")
                val thumb = data.extras?.get("data") as? Bitmap
                if (thumb != null) path = writeBitmapToCache(thumb)
            }
        }
        promise.resolve(path)
        return true
    }

    private fun writeBitmapToCache(bitmap: Bitmap): String? {
        return try {
            val target = File(PNBridge.context().cacheDir, "pn-camera-${System.currentTimeMillis()}.jpg")
            FileOutputStream(target).use { bitmap.compress(Bitmap.CompressFormat.JPEG, 85, it) }
            target.absolutePath
        } catch (e: Exception) {
            PNLog.swallowed("Camera.writeBitmapToCache", e)
            null
        }
    }
}

/**
 * `Location.get_current()`: the last known fix if fresh enough,
 * otherwise a single `network`/`gps` update with a 15 s timeout.
 * Resolves to `{latitude, longitude}` or `null`.
 */
class LocationModule : NativeModule {
    override val name = "Location"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "get_current" -> getCurrent(promise)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    @SuppressLint("MissingPermission")
    private fun getCurrent(promise: Promise) {
        val ctx = PNBridge.context()
        val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return promise.resolve(null)
        try {
            for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
                val last = lm.getLastKnownLocation(provider) ?: continue
                if (System.currentTimeMillis() - last.time < 60_000) return promise.resolve(coords(last))
            }
        } catch (e: SecurityException) {
            return promise.resolve(null)
        } catch (e: Exception) {
            PNLog.swallowed("Location.lastKnown", e)
        }
        var settled = false
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                if (settled) return
                settled = true
                lm.removeUpdates(this)
                promise.resolve(coords(location))
            }

            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
            override fun onProviderEnabled(provider: String) {}
            override fun onProviderDisabled(provider: String) {}
        }
        try {
            val provider = when {
                lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
                lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
                else -> return promise.resolve(null)
            }
            lm.requestLocationUpdates(provider, 1000L, 0f, listener)
            MainThread.postDelayed({
                if (settled) return@postDelayed
                settled = true
                lm.removeUpdates(listener)
                promise.resolve(null)
            }, 15_000L)
        } catch (e: Exception) {
            PNLog.swallowed("Location.requestUpdates", e)
            promise.resolve(null)
        }
    }

    private fun coords(location: Location): Map<String, Any?> = mapOf(
        "latitude" to location.latitude,
        "longitude" to location.longitude,
        "accuracy" to location.accuracy.toDouble(),
        "altitude" to if (location.hasAltitude()) location.altitude else null,
        "timestamp" to location.time,
    )
}

/** `Biometrics.is_available()` (sync bool) and `authenticate(reason)` (async bool via `BiometricPrompt`). */
class BiometricsModule : NativeModule {
    override val name = "Biometrics"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "is_available" -> promise.resolve(isAvailable())
            "authenticate" -> authenticate(args.str("reason") ?: "Authenticate", promise)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    private fun isAvailable(): Boolean {
        return try {
            val manager = BiometricManager.from(PNBridge.context())
            manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK) == BiometricManager.BIOMETRIC_SUCCESS
        } catch (e: Exception) {
            false
        }
    }

    private fun authenticate(reason: String, promise: Promise) {
        val activity = PNBridge.activity() as? FragmentActivity ?: return promise.resolve(false)
        if (!isAvailable()) return promise.resolve(false)
        try {
            val executor = ContextCompat.getMainExecutor(activity)
            val prompt = BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = promise.resolve(true)
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) = promise.resolve(false)
                override fun onAuthenticationFailed() {}
            })
            val info = BiometricPrompt.PromptInfo.Builder()
                .setTitle(reason)
                .setNegativeButtonText("Cancel")
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK)
                .build()
            prompt.authenticate(info)
        } catch (e: Exception) {
            PNLog.swallowed("Biometrics.authenticate", e)
            promise.resolve(false)
        }
    }
}
