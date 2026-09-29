package com.pythonnative.runtime.modules

import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.generated.PermissionsImplementation

/**
 * `Permissions.check(permission)` (sync) and `request(permission)`
 * (async, routed through `onRequestPermissionsResult`). Statuses are
 * `granted`, `denied`, `blocked`, and `undetermined`.
 *
 * Permission names are the `[permissions]` keys from pythonnative.toml
 * (`camera`, `microphone`, `photo_library`, `location_when_in_use`,
 * `contacts`, `notifications`); the Python facade validates them before
 * the call reaches this module, so an unknown name here is a bug rather
 * than user input, and is rejected rather than answered.
 */
class PermissionsModule : PermissionsImplementation {
    private val pending = HashMap<Int, Pair<Array<String>, (IntArray) -> Unit>>()

    override fun check(permission: String, completion: (Result<String>) -> Unit): (() -> Unit)? {
        require(MANIFEST.containsKey(permission)) { "Unknown permission: $permission" }
        completion(Result.success(check(permission)))
        return null
    }

    override fun request(permission: String, completion: (Result<String>) -> Unit): (() -> Unit)? {
        require(MANIFEST.containsKey(permission)) { "Unknown permission: $permission" }
        return requestStatus(permission) { completion(Result.success(it)) }
    }

    /** Current status of `permission` without prompting. */
    fun check(permission: String): String {
        val manifest = MANIFEST[permission] ?: return UNDETERMINED
        if (permission == "notifications" && Build.VERSION.SDK_INT < 33) return GRANTED
        if (permission == "photo_library" && Build.VERSION.SDK_INT < 33) {
            return statusOf("android.permission.READ_EXTERNAL_STORAGE")
        }
        return statusOf(manifest)
    }

    private fun statusOf(manifest: String): String {
        val ctx = PNBridge.activity() ?: return UNDETERMINED
        if (isGranted(manifest)) return GRANTED
        // Coarse location satisfies a when-in-use request the user downgraded to "approximate".
        if (manifest == FINE_LOCATION && isGranted(COARSE_LOCATION)) return GRANTED
        // "denied" with no rationale after a previous denial means "don't ask again".
        val asked = ctx.getSharedPreferences("pn_permissions", 0).getBoolean(manifest, false)
        return if (asked && !ActivityCompat.shouldShowRequestPermissionRationale(ctx, manifest)) BLOCKED else DENIED
    }

    /** Whether the manifest permission `manifest` is currently granted. */
    fun isGranted(manifest: String): Boolean {
        val ctx = PNBridge.activity() ?: return false
        return ContextCompat.checkSelfPermission(ctx, manifest) == PackageManager.PERMISSION_GRANTED
    }

    /** Prompt for `permission` if needed and report the resulting status to `onDone`. */
    fun requestStatus(permission: String, onDone: (String) -> Unit): (() -> Unit)? {
        val manifest = MANIFEST[permission] ?: run { onDone(UNDETERMINED); return null }
        if (check(permission) == GRANTED) { onDone(GRANTED); return null }
        val targets = when {
            permission == "photo_library" && Build.VERSION.SDK_INT < 33 -> arrayOf("android.permission.READ_EXTERNAL_STORAGE")
            // Android 12+ ignores a fine-location request that omits coarse.
            manifest == FINE_LOCATION -> arrayOf(FINE_LOCATION, COARSE_LOCATION)
            else -> arrayOf(manifest)
        }
        return requestManifest(targets) { results ->
            val granted = results.isNotEmpty() && results.any { it == PackageManager.PERMISSION_GRANTED }
            onDone(if (granted) GRANTED else statusOf(targets[0]))
        }
    }

    /**
     * Request raw manifest permissions and deliver the grant results
     * (`onDone` gets an empty array when no activity can prompt). Other
     * modules reuse this for inline prompts (`Location.get_current`).
     */
    fun requestManifest(targets: Array<String>, onDone: (IntArray) -> Unit): (() -> Unit)? {
        if (targets.all { isGranted(it) }) { onDone(IntArray(targets.size) { PackageManager.PERMISSION_GRANTED }); return null }
        val activity = PNBridge.activity() ?: run { onDone(IntArray(0)); return null }
        val code = RequestCodes.next()
        pending[code] = targets to onDone
        try {
            ActivityCompat.requestPermissions(activity, targets, code)
        } catch (e: Exception) {
            pending.remove(code)
            onDone(IntArray(0))
            return null
        }
        return { pending.remove(code); Unit }
    }

    /** Route `Activity.onRequestPermissionsResult`; `true` when a pending request matched. */
    fun onRequestPermissionsResult(requestCode: Int, grantResults: IntArray): Boolean {
        val (targets, onDone) = pending.remove(requestCode) ?: return false
        PNBridge.activity()?.getSharedPreferences("pn_permissions", 0)?.edit()?.apply {
            for (target in targets) putBoolean(target, true)
            apply()
        }
        onDone(grantResults)
        return true
    }

    companion object {
        const val GRANTED = "granted"
        const val DENIED = "denied"
        const val BLOCKED = "blocked"
        const val UNDETERMINED = "undetermined"
        const val FINE_LOCATION = "android.permission.ACCESS_FINE_LOCATION"
        const val COARSE_LOCATION = "android.permission.ACCESS_COARSE_LOCATION"

        val MANIFEST = mapOf(
            "camera" to "android.permission.CAMERA",
            "microphone" to "android.permission.RECORD_AUDIO",
            "photo_library" to "android.permission.READ_MEDIA_IMAGES",
            "location_when_in_use" to FINE_LOCATION,
            "contacts" to "android.permission.READ_CONTACTS",
            "notifications" to "android.permission.POST_NOTIFICATIONS",
        )
    }
}
