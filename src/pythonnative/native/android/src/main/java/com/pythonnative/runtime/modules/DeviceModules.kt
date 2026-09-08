package com.pythonnative.runtime.modules

import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.Settings
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/** `Device.info()`: static facts about the OS, hardware, and app directories. */
class DeviceModule : NativeModule {
    override val name = "Device"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "info" -> {
                val ctx = PNBridge.context()
                val locale = Locale.getDefault()
                promise.resolve(
                    mapOf(
                        "os" to "android",
                        "os_version" to Build.VERSION.RELEASE,
                        "sdk_int" to Build.VERSION.SDK_INT,
                        "model" to Build.MODEL,
                        "manufacturer" to Build.MANUFACTURER,
                        "app_dir" to ctx.filesDir.absolutePath,
                        "cache_dir" to ctx.cacheDir.absolutePath,
                        "locale" to locale.toLanguageTag(),
                        "density" to PNBridge.density().toDouble(),
                    ),
                )
            }
            else -> promise.rejectUnknownMethod(method)
        }
    }
}

/**
 * `Alert.show({title, message, buttons:[{label, style}], style})`:
 * an `AlertDialog` resolving to the selected button index, or `-1`
 * on dismiss. `AlertDialog` has three slots; the first `default`
 * button takes positive, the first `cancel` negative, the first
 * `destructive` neutral, and leftovers spill into free slots.
 */
class AlertModule : NativeModule {
    override val name = "Alert"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "present" -> present(args, promise, fireAndForget = false)
            "show" -> present(args, promise, fireAndForget = true)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    /**
     * Build and show the dialog. `present` resolves with the tapped button
     * index (or -1 on dismiss); `show` resolves immediately so the Python
     * side's synchronous `call("show")` returns before the dialog closes.
     */
    private fun present(args: JSONObject, promise: Promise, fireAndForget: Boolean) {
        val activity = PNBridge.activity()
        if (activity == null) {
            if (fireAndForget) promise.resolve(null) else promise.reject("no activity", "no_activity")
            return
        }
        if (fireAndForget) promise.resolve(null)
        val builder = AlertDialog.Builder(activity)
        builder.setTitle(args.str("title") ?: "")
        args.str("message")?.let { builder.setMessage(it) }
        val buttons = args.value("buttons") as? JSONArray
        val specs = ArrayList<JSONObject>()
        if (buttons != null) for (i in 0 until buttons.length()) buttons.optJSONObject(i)?.let { specs.add(it) }
        if (specs.isEmpty()) specs.add(JSONObject().put("label", "OK").put("style", "default"))

        val slotFor = HashMap<Int, String>()
        val free = arrayListOf("positive", "negative", "neutral")
        specs.forEachIndexed { i, spec ->
            val preferred = when (spec.str("style") ?: "default") {
                "cancel" -> "negative"
                "destructive" -> "neutral"
                else -> "positive"
            }
            if (free.remove(preferred)) slotFor[i] = preferred
        }
        specs.forEachIndexed { i, _ ->
            if (!slotFor.containsKey(i) && free.isNotEmpty()) slotFor[i] = free.removeAt(0)
        }
        var delivered = false
        fun deliver(index: Int) {
            if (delivered) return
            delivered = true
            if (!fireAndForget) promise.resolve(index)
        }
        specs.forEachIndexed { i, spec ->
            val label = spec.str("label") ?: "OK"
            when (slotFor[i]) {
                "positive" -> builder.setPositiveButton(label) { _, _ -> deliver(i) }
                "negative" -> builder.setNegativeButton(label) { _, _ -> deliver(i) }
                "neutral" -> builder.setNeutralButton(label) { _, _ -> deliver(i) }
            }
        }
        builder.setOnCancelListener { deliver(-1) }
        builder.setOnDismissListener { deliver(-1) }
        builder.show()
    }
}

/** `Clipboard.set_string(value)` / `get_string()`. */
class ClipboardModule : NativeModule {
    override val name = "Clipboard"

    private fun manager(): ClipboardManager? =
        PNBridge.context().getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "set_string" -> {
                manager()?.setPrimaryClip(ClipData.newPlainText("pythonnative", args.str("value") ?: ""))
                promise.resolve(null)
            }
            "get_string" -> {
                val clip = manager()?.primaryClip
                val text = if (clip != null && clip.itemCount > 0) clip.getItemAt(0).text?.toString() else null
                promise.resolve(text ?: "")
            }
            "has_string" -> {
                val clip = manager()?.primaryClip
                promise.resolve(clip != null && clip.itemCount > 0 && !clip.getItemAt(0).text.isNullOrEmpty())
            }
            else -> promise.rejectUnknownMethod(method)
        }
    }
}

/** `Share.share({message, url, title})`: an `ACTION_SEND` chooser resolving `true` when it returns. */
class ShareModule : NativeModule {
    override val name = "Share"
    private var pending: Promise? = null
    private var pendingCode = 0

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "share" -> share(args, promise)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    private fun share(args: JSONObject, promise: Promise) {
        val activity = PNBridge.activity() ?: return promise.reject("no activity", "no_activity")
        val message = args.str("message")
        val url = args.str("url")
        val body = listOfNotNull(message, url).joinToString("\n")
        if (body.isEmpty()) return promise.resolve(false)
        val intent = Intent(Intent.ACTION_SEND)
        intent.type = "text/plain"
        intent.putExtra(Intent.EXTRA_TEXT, body)
        args.str("title")?.let { intent.putExtra(Intent.EXTRA_SUBJECT, it) }
        try {
            pending?.resolve(true)
            pending = promise
            pendingCode = RequestCodes.next()
            @Suppress("DEPRECATION")
            activity.startActivityForResult(Intent.createChooser(intent, args.str("title")), pendingCode)
        } catch (e: Exception) {
            pending = null
            promise.resolve(false)
        }
    }

    /** Resolve the pending share when the chooser activity returns. */
    fun onActivityResult(requestCode: Int): Boolean {
        if (requestCode != pendingCode || pending == null) return false
        val p = pending
        pending = null
        // The chooser gives no success signal; returning to the app counts as shared.
        p?.resolve(true)
        return true
    }
}

/**
 * `Linking`: `open_url`, `can_open_url`, `open_settings` (sync bools)
 * plus `url` events for deep links, buffered until a `PythonHost` is
 * installed.
 */
class LinkingModule : NativeModule {
    override val name = "Linking"
    private val buffered = ArrayList<String>()
    private var initialUrl: String? = null

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "open_url" -> promise.resolve(openUrl(args.str("url") ?: ""))
            "can_open_url" -> promise.resolve(canOpen(args.str("url") ?: ""))
            "open_settings" -> promise.resolve(openSettings())
            "get_initial_url" -> promise.resolve(initialUrl)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    /** Record a deep link and emit it once Python can receive it. */
    fun onDeepLink(url: String) {
        if (initialUrl == null) initialUrl = url
        buffered.add(url)
        PNBridge.runWhenHostReady { flush() }
    }

    private fun flush() {
        val urls = ArrayList(buffered)
        buffered.clear()
        for (url in urls) ModuleEvents.emit(name, "url", JSONObject().put("url", url))
    }

    private fun openUrl(url: String): Boolean {
        if (url.isEmpty()) return false
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            PNBridge.context().startActivity(intent)
            true
        } catch (e: Exception) {
            PNLog.swallowed("Linking.open_url", e)
            false
        }
    }

    private fun canOpen(url: String): Boolean {
        if (url.isEmpty()) return false
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            intent.resolveActivity(PNBridge.context().packageManager) != null
        } catch (e: Exception) {
            false
        }
    }

    private fun openSettings(): Boolean {
        return try {
            val ctx = PNBridge.context()
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
            intent.data = Uri.fromParts("package", ctx.packageName, null)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            ctx.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }
}

/** `Haptics`: `impact(style)`, `notification(type)`, `selection()`, `vibrate(duration_ms)`, `cancel()`. */
class HapticsModule : NativeModule {
    override val name = "Haptics"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "impact" -> buzz(IMPACT_MS[args.str("style") ?: "medium"] ?: 20L)
            "notification" -> buzz(NOTIFICATION_MS[args.str("type") ?: args.str("type_") ?: "success"] ?: 30L)
            "selection" -> buzz(10L)
            "vibrate" -> buzz(JsonUtil.toLong(args.opt("duration_ms"), 400L))
            "cancel" -> vibrator()?.cancel()
            else -> return promise.rejectUnknownMethod(method)
        }
        promise.resolve(null)
    }

    private fun vibrator(): Vibrator? {
        val ctx = PNBridge.context()
        return if (Build.VERSION.SDK_INT >= 31) {
            (ctx.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            ctx.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }

    private fun buzz(durationMs: Long) {
        val v = vibrator() ?: return
        try {
            if (Build.VERSION.SDK_INT >= 26) {
                v.vibrate(VibrationEffect.createOneShot(durationMs, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                v.vibrate(durationMs)
            }
        } catch (e: Exception) {
            PNLog.swallowed("Haptics.buzz", e)
        }
    }

    private companion object {
        val IMPACT_MS = mapOf("light" to 10L, "medium" to 20L, "heavy" to 40L, "soft" to 15L, "rigid" to 30L)
        val NOTIFICATION_MS = mapOf("success" to 30L, "warning" to 50L, "error" to 70L)
    }
}

/** Monotonic request codes for `startActivityForResult` / `requestPermissions`. */
object RequestCodes {
    private var next = 50001

    fun next(): Int = next++
}
