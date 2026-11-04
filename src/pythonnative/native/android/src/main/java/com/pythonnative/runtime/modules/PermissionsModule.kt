package com.pythonnative.runtime.modules

import android.content.pm.PackageManager
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.pythonnative.generated.PermissionsImplementation
import com.pythonnative.runtime.PNBridge

/**
 * The permission names plugins own. A name works only when a plugin that uses
 * it is in the build, so the app's manifest never needs a permission it
 * doesn't use.
 */
object PNPermissions {
    /**
     * @property manifest The permission whose grant decides the status.
     * @property requests What to prompt for (Android 12+ ignores a fine-location request that omits coarse).
     * @property satisfiedBy Another permission that also counts as granted (coarse for a downgraded fine request).
     * @property minSdk Below this API level the permission doesn't exist and is implicitly granted.
     * @property legacy What to check below [minSdk] instead of granting implicitly.
     */
    class Spec(
        val manifest: String,
        val requests: Array<String>,
        val satisfiedBy: String? = null,
        val minSdk: Int = 0,
        val legacy: String? = null,
    )

    private val specs = HashMap<String, Spec>()

    /** Register (or replace) the Android permissions behind `[permissions]` name [name]. */
    fun register(
        name: String,
        manifest: String,
        requests: Array<String> = arrayOf(manifest),
        satisfiedBy: String? = null,
        minSdk: Int = 0,
        legacy: String? = null,
    ) {
        specs[name] = Spec(manifest, requests, satisfiedBy, minSdk, legacy)
    }

    internal fun spec(name: String): Spec? {
        com.pythonnative.runtime.bridge.PNRegistry.ensureBuiltins()
        return specs[name]
    }
}

/**
 * `Permissions.check(permission)` and `request(permission)` (async, routed
 * through `onRequestPermissionsResult`). Statuses are `granted`, `denied`,
 * `blocked`, and `undetermined`. A name no plugin in this build owns is
 * rejected with the code `plugin_not_enabled`.
 */
class PermissionsModule : PermissionsImplementation {
    private val pending = HashMap<Int, Pair<Array<String>, (IntArray) -> Unit>>()

    override fun check(permission: String, completion: (Result<String>) -> Unit): (() -> Unit)? {
        val spec = PNPermissions.spec(permission)
        completion(if (spec == null) Result.failure(notEnabled(permission)) else Result.success(status(spec)))
        return null
    }

    override fun request(permission: String, completion: (Result<String>) -> Unit): (() -> Unit)? {
        val spec = PNPermissions.spec(permission) ?: run { completion(Result.failure(notEnabled(permission))); return null }
        return requestStatus(spec) { completion(Result.success(it)) }
    }

    private fun notEnabled(permission: String) =
        PNModuleError("No plugin in this build provides the $permission permission", "plugin_not_enabled")

    private fun status(spec: PNPermissions.Spec): String {
        if (android.os.Build.VERSION.SDK_INT < spec.minSdk) {
            return if (spec.legacy == null) GRANTED else statusOf(spec.legacy, null)
        }
        return statusOf(spec.manifest, spec.satisfiedBy)
    }

    private fun statusOf(manifest: String, satisfiedBy: String?): String {
        val ctx = PNBridge.activity() ?: return UNDETERMINED
        if (isGranted(manifest) || (satisfiedBy != null && isGranted(satisfiedBy))) return GRANTED
        // "denied" with no rationale after a previous denial means "don't ask again".
        val asked = ctx.getSharedPreferences("pn_permissions", 0).getBoolean(manifest, false)
        return if (asked && !ActivityCompat.shouldShowRequestPermissionRationale(ctx, manifest)) BLOCKED else DENIED
    }

    /** Whether the manifest permission [manifest] is currently granted. */
    fun isGranted(manifest: String): Boolean {
        val ctx = PNBridge.activity() ?: return false
        return ContextCompat.checkSelfPermission(ctx, manifest) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestStatus(spec: PNPermissions.Spec, onDone: (String) -> Unit): (() -> Unit)? {
        if (status(spec) == GRANTED) { onDone(GRANTED); return null }
        val legacy = android.os.Build.VERSION.SDK_INT < spec.minSdk
        val targets = if (legacy) arrayOf(spec.legacy!!) else spec.requests
        return requestManifest(targets) { results ->
            val granted = results.isNotEmpty() && results.any { it == PackageManager.PERMISSION_GRANTED }
            onDone(if (granted) GRANTED else statusOf(targets[0], null))
        }
    }

    /**
     * Request raw manifest permissions and deliver the grant results
     * ([onDone] gets an empty array when no activity can prompt). Plugins
     * reuse this for inline prompts (`Location.get_current`).
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
    }
}
