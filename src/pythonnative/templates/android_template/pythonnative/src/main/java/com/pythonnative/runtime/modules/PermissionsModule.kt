package com.pythonnative.runtime.modules

import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.str
import org.json.JSONObject

/**
 * `Permissions.check(permission)` (sync) and `request(permission)`
 * (async, routed through `onRequestPermissionsResult`). Statuses are
 * `granted`, `denied`, `blocked`, and `undetermined`.
 */
class PermissionsModule : NativeModule {
    override val name = "Permissions"
    private val pending = HashMap<Int, Pair<String, (String) -> Unit>>()

    override fun call(method: String, args: JSONObject, promise: Promise) {
        val permission = args.str("permission") ?: ""
        when (method) {
            "check" -> promise.resolve(check(permission))
            "request" -> request(permission) { promise.resolve(it) }
            else -> promise.rejectUnknownMethod(method)
        }
    }

    /** Current status of `permission` without prompting. */
    fun check(permission: String): String {
        val manifest = MANIFEST[permission] ?: return UNDETERMINED
        if (permission == "notifications" && Build.VERSION.SDK_INT < 33) return GRANTED
        if (permission == "photos" && Build.VERSION.SDK_INT < 33) {
            return statusOf("android.permission.READ_EXTERNAL_STORAGE")
        }
        return statusOf(manifest)
    }

    private fun statusOf(manifest: String): String {
        val ctx = PNBridge.activity() ?: return UNDETERMINED
        val granted = ContextCompat.checkSelfPermission(ctx, manifest) == PackageManager.PERMISSION_GRANTED
        if (granted) return GRANTED
        // "denied" with no rationale after a previous denial means "don't ask again".
        val asked = ctx.getSharedPreferences("pn_permissions", 0).getBoolean(manifest, false)
        return if (asked && !ActivityCompat.shouldShowRequestPermissionRationale(ctx, manifest)) BLOCKED else DENIED
    }

    /** Prompt for `permission` if needed and report the resulting status to `onDone`. */
    fun request(permission: String, onDone: (String) -> Unit) {
        val manifest = MANIFEST[permission] ?: return onDone(UNDETERMINED)
        if (check(permission) == GRANTED) return onDone(GRANTED)
        val activity = PNBridge.activity() ?: return onDone(check(permission))
        val target = if (permission == "photos" && Build.VERSION.SDK_INT < 33) "android.permission.READ_EXTERNAL_STORAGE" else manifest
        val code = RequestCodes.next()
        pending[code] = target to onDone
        try {
            ActivityCompat.requestPermissions(activity, arrayOf(target), code)
        } catch (e: Exception) {
            pending.remove(code)
            onDone(check(permission))
        }
    }

    /** Route `Activity.onRequestPermissionsResult`; `true` when a pending request matched. */
    fun onRequestPermissionsResult(requestCode: Int, grantResults: IntArray): Boolean {
        val (manifest, onDone) = pending.remove(requestCode) ?: return false
        PNBridge.activity()?.getSharedPreferences("pn_permissions", 0)?.edit()?.putBoolean(manifest, true)?.apply()
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        onDone(if (granted) GRANTED else statusOf(manifest))
        return true
    }

    companion object {
        const val GRANTED = "granted"
        const val DENIED = "denied"
        const val BLOCKED = "blocked"
        const val UNDETERMINED = "undetermined"

        val MANIFEST = mapOf(
            "camera" to "android.permission.CAMERA",
            "microphone" to "android.permission.RECORD_AUDIO",
            "location" to "android.permission.ACCESS_FINE_LOCATION",
            "contacts" to "android.permission.READ_CONTACTS",
            "notifications" to "android.permission.POST_NOTIFICATIONS",
            "photos" to "android.permission.READ_MEDIA_IMAGES",
        )
    }
}
