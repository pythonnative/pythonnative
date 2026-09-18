package com.pythonnative.runtime.modules

import com.pythonnative.generated.*

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.fragment.app.FragmentActivity
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import java.io.File
import java.io.FileOutputStream

/**
 * `Camera.take_photo()` / `pick_from_gallery()`.
 *
 * `take_photo` launches `ACTION_IMAGE_CAPTURE` with `EXTRA_OUTPUT` set to
 * a `FileProvider` URI (authority `<applicationId>.pythonnative.fileprovider`,
 * declared by the library manifest over `res/xml/pn_file_paths.xml`) so
 * the camera writes the full-resolution capture instead of returning a
 * thumbnail. The result is the JPEG's path inside the app cache
 * directory (re-encoded at `quality` when it is below 1.0), like iOS.
 * `pick_from_gallery` copies the chosen content URI into the cache
 * directory and returns that path. Both resolve `null` on cancel.
 * `allow_editing` is accepted and ignored: Android has no system crop UI
 * to hand off to.
 */
class CameraModule : CameraImplementation {
    private class Pending(val quality: Int, val output: File?, val uri: Uri?, val done: (Result<String?>) -> Unit)
    private val pending = HashMap<Int, Pending>()

    override fun take_photo(quality: Double, allow_editing: Boolean, completion: (Result<String?>) -> Unit): (() -> Unit)? {
        noteEditing(allow_editing)
        val activity = PNBridge.activity() ?: run { completion(Result.success(null)); return null }
        val output: File
        val uri: Uri
        try {
            output = newCaptureFile(activity)
            uri = FileProvider.getUriForFile(activity, authority(activity), output)
        } catch (error: Exception) {
            completion(Result.failure(error))
            return null
        }
        val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            .putExtra(MediaStore.EXTRA_OUTPUT, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        // Some camera apps read EXTRA_OUTPUT from a ClipData; grant every resolver explicitly too.
        intent.clipData = android.content.ClipData.newRawUri("output", uri)
        try {
            for (info in activity.packageManager.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY)) {
                activity.grantUriPermission(info.activityInfo.packageName, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            }
        } catch (error: Exception) {
            PNLog.swallowed("Camera.grant", error)
        }
        return launch(activity, intent, quality, output, uri, completion)
    }

    override fun pick_from_gallery(quality: Double, allow_editing: Boolean, completion: (Result<String?>) -> Unit): (() -> Unit)? {
        noteEditing(allow_editing)
        val activity = PNBridge.activity() ?: run { completion(Result.success(null)); return null }
        return launch(activity, Intent(Intent.ACTION_PICK).apply { type = "image/*" }, quality, null, null, completion)
    }

    private fun noteEditing(editing: Boolean) {
        if (editing) PNLog.once("camera-editing", "Camera: allow_editing is not supported on Android and is ignored")
    }

    private fun launch(activity: Activity, intent: Intent, quality: Double, output: File?, uri: Uri?, completion: (Result<String?>) -> Unit): (() -> Unit)? {
        val code = RequestCodes.next()
        pending[code] = Pending((quality.coerceIn(0.0, 1.0) * 100).toInt(), output, uri, completion)
        try {
            @Suppress("DEPRECATION")
            activity.startActivityForResult(intent, code)
        } catch (error: Exception) {
            pending.remove(code)
            revoke(activity, uri)
            output?.delete()
            completion(Result.failure(error))
            return null
        }
        return {
            pending.remove(code)?.let { revoke(activity, it.uri); it.output?.delete() }
            @Suppress("DEPRECATION")
            activity.finishActivity(code)
        }
    }

    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        val request = pending.remove(requestCode) ?: return false
        val ctx = PNBridge.context()
        revoke(PNBridge.activity(), request.uri)
        if (resultCode != Activity.RESULT_OK) {
            request.output?.delete()
            request.done(Result.success(null))
            return true
        }
        try {
            val captured = request.output
            val path = when {
                captured != null && captured.exists() && captured.length() > 0L -> finishCapture(ctx, captured, request.quality)
                data?.data != null -> copyToCache(ctx, data.data!!, request.quality)
                else -> {
                    // Legacy cameras that ignore EXTRA_OUTPUT still hand back a thumbnail.
                    @Suppress("DEPRECATION")
                    val thumb = data?.extras?.get("data") as? Bitmap
                    captured?.delete()
                    thumb?.let { writeJpeg(ctx, it, request.quality) }
                }
            }
            request.done(Result.success(path))
        } catch (error: Exception) {
            request.output?.delete()
            request.done(Result.failure(error))
        }
        return true
    }

    private fun finishCapture(ctx: Context, file: File, quality: Int): String {
        if (quality >= 100) return file.absolutePath
        return try {
            val bitmap = BitmapFactory.decodeFile(file.absolutePath) ?: return file.absolutePath
            val path = writeJpeg(ctx, bitmap, quality)
            bitmap.recycle()
            file.delete()
            path
        } catch (error: Throwable) {
            // Out of memory or a decoder failure: the full-resolution file is still a valid answer.
            PNLog.swallowed("Camera.recompress", error)
            file.absolutePath
        }
    }

    private fun copyToCache(ctx: Context, uri: Uri, quality: Int): String? {
        val target = newCaptureFile(ctx)
        ctx.contentResolver.openInputStream(uri)?.use { input -> FileOutputStream(target).use { input.copyTo(it) } }
            ?: return uri.toString()
        return finishCapture(ctx, target, quality)
    }

    private fun writeJpeg(ctx: Context, bitmap: Bitmap, quality: Int): String {
        val target = newCaptureFile(ctx)
        FileOutputStream(target).use { check(bitmap.compress(Bitmap.CompressFormat.JPEG, quality.coerceIn(1, 100), it)) }
        return target.absolutePath
    }

    private fun revoke(activity: Activity?, uri: Uri?) {
        if (activity == null || uri == null) return
        try { activity.revokeUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION) } catch (_: Exception) {}
    }

    companion object {
        /** Suffix appended to the application id to form the provider authority. */
        const val AUTHORITY_SUFFIX = ".pythonnative.fileprovider"

        /** The FileProvider authority declared by the library manifest for `ctx`'s app. */
        fun authority(ctx: Context): String = ctx.packageName + AUTHORITY_SUFFIX

        /** A fresh JPEG file under `<cache>/pn-camera/`. */
        fun newCaptureFile(ctx: Context): File {
            val dir = File(ctx.cacheDir, "pn-camera").apply { mkdirs() }
            return File.createTempFile("pn-camera-", ".jpg", dir)
        }
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
    override fun get_current(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: (Result<Map<String, Double>?>) -> Unit): (() -> Unit)? {
        val permissions = BuiltinModules.permissions
        if (permissions.isGranted(PermissionsModule.FINE_LOCATION) || permissions.isGranted(PermissionsModule.COARSE_LOCATION)) {
            return read(accuracy, timeout, completion)
        }
        var cancelled = false
        var cancelRead: (() -> Unit)? = null
        val cancelRequest = permissions.requestManifest(arrayOf(PermissionsModule.FINE_LOCATION, PermissionsModule.COARSE_LOCATION)) { results ->
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
