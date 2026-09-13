package com.pythonnative.runtime.modules

import com.pythonnative.generated.*
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
import com.pythonnative.runtime.bridge.PNLog
import java.util.Locale

/** `Device.info()`: static facts about the OS, hardware, and app directories. */
class DeviceModule : DeviceImplementation {
    override fun info(): Map<String, PNJSONValue> {
        val ctx = PNBridge.context()
        return mapOf(
            "os" to "android", "os_version" to Build.VERSION.RELEASE,
            "sdk_int" to Build.VERSION.SDK_INT, "model" to Build.MODEL,
            "manufacturer" to Build.MANUFACTURER, "app_dir" to ctx.filesDir.absolutePath,
            "cache_dir" to ctx.cacheDir.absolutePath, "locale" to Locale.getDefault().toLanguageTag(),
            "density" to PNBridge.density().toDouble()
        ).mapValues { PNJSONValue(it.value) }
    }
}

/**
 * `Alert.show({title, message, buttons:[{label, style}], style})`:
 * an `AlertDialog` resolving to the selected button index, or `-1`
 * on dismiss. `AlertDialog` has three slots; the first `default`
 * button takes positive, the first `cancel` negative, the first
 * `destructive` neutral, and leftovers spill into free slots.
 */
class AlertModule : AlertImplementation {
    override fun show(title: String, message: String?, buttons: List<Map<String, PNJSONValue>>, style: String) {
        dialog(title, message, buttons) { }
    }

    override fun present(title: String, message: String?, buttons: List<Map<String, PNJSONValue>>, style: String, completion: (Result<Long>) -> Unit): (() -> Unit)? =
        dialog(title, message, buttons) { completion(Result.success(it)) }

    private fun dialog(title: String, message: String?, buttons: List<Map<String, PNJSONValue>>, done: (Long) -> Unit): (() -> Unit)? {
        val activity = PNBridge.activity() ?: run { done(-1); return null }
        val builder = AlertDialog.Builder(activity).setTitle(title).setMessage(message)
        val specs = buttons.ifEmpty { listOf(mapOf("label" to PNJSONValue("OK"))) }
        var delivered = false
        fun deliver(index: Long) { if (!delivered) { delivered = true; done(index) } }
        if (specs.size > 3) {
            // Android's three action slots must never silently hide extra choices.
            builder.setItems(specs.map { it["label"]?.value as? String ?: "OK" }.toTypedArray()) { _, index -> deliver(index.toLong()) }
        } else {
            val free = arrayListOf("positive", "negative", "neutral")
            val slots = HashMap<Int, String>()
            specs.forEachIndexed { index, spec ->
                val preferred = when (spec["style"]?.value) { "cancel" -> "negative"; "destructive" -> "neutral"; else -> "positive" }
                if (free.remove(preferred)) slots[index] = preferred
            }
            specs.forEachIndexed { index, spec ->
                val slot = slots[index] ?: free.removeAt(0)
                val label = spec["label"]?.value as? String ?: "OK"
                when (slot) {
                    "positive" -> builder.setPositiveButton(label) { _, _ -> deliver(index.toLong()) }
                    "negative" -> builder.setNegativeButton(label) { _, _ -> deliver(index.toLong()) }
                    else -> builder.setNeutralButton(label) { _, _ -> deliver(index.toLong()) }
                }
            }
        }
        builder.setOnCancelListener { deliver(-1) }
        builder.setOnDismissListener { deliver(-1) }
        val dialog = builder.show()
        return { delivered = true; dialog.dismiss() }
    }
}

/** `Clipboard.set_string(text)` / `get_string()`. */
class ClipboardModule : ClipboardImplementation {
    private fun manager(): ClipboardManager? =
        PNBridge.context().getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
    override fun set_string(text: String) {
        manager()?.setPrimaryClip(ClipData.newPlainText("pythonnative", text))
    }
    override fun get_string(): String {
        val clip = manager()?.primaryClip
        return if (clip != null && clip.itemCount > 0) clip.getItemAt(0).coerceToText(PNBridge.context()).toString() else ""
    }
}

/** `Share.share({message, url, title})`: an `ACTION_SEND` chooser resolving `true` when it returns. */
class ShareModule : ShareImplementation {
    private var pending: ((Result<Boolean>) -> Unit)? = null
    private var pendingCode = 0

    override fun share(message: String?, url: String?, title: String?, completion: (Result<Boolean>) -> Unit): (() -> Unit)? {
        val activity = PNBridge.activity() ?: run { completion(Result.failure(IllegalStateException("No activity"))); return null }
        val body = listOfNotNull(message, url).joinToString("\n")
        if (body.isEmpty()) { completion(Result.success(false)); return null }
        if (pending != null) { completion(Result.failure(IllegalStateException("A share is already open"))); return null }
        val intent = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, body)
        title?.let { intent.putExtra(Intent.EXTRA_SUBJECT, it) }
        val code = RequestCodes.next()
        pending = completion
        pendingCode = code
        try {
            @Suppress("DEPRECATION")
            activity.startActivityForResult(Intent.createChooser(intent, title), code)
        } catch (error: Exception) {
            pending = null
            completion(Result.failure(error))
            return null
        }
        return {
            if (pendingCode == code) {
                pending = null
                @Suppress("DEPRECATION")
                activity.finishActivity(code)
            }
        }
    }

    fun onActivityResult(requestCode: Int): Boolean {
        if (requestCode != pendingCode) return false
        val completion = pending ?: return false
        pending = null
        // ACTION_SEND has no trustworthy delivery status; this reports chooser return.
        completion(Result.success(true))
        return true
    }
}

/**
 * `Linking`: `open_url`, `can_open_url`, `open_settings` (sync bools)
 * plus `url` events for deep links, buffered until a `PythonHost` is
 * installed.
 */
class LinkingModule : LinkingImplementation {
    val name = "Linking"
    private val buffered = ArrayList<String>()
    private var initialUrl: String? = null

    override fun open_url(url: String): Boolean = openUrl(url)
    override fun can_open_url(url: String): Boolean = canOpen(url)
    override fun open_settings(): Boolean = openSettings()

    /** Record a deep link and emit it once Python can receive it. */
    fun onDeepLink(url: String) {
        if (initialUrl == null) initialUrl = url
        buffered.add(url)
        PNBridge.runWhenHostReady { flush() }
    }

    private fun flush() {
        val urls = ArrayList(buffered)
        buffered.clear()
        for (url in urls) LinkingEvents.url(url)
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
class HapticsModule : HapticsImplementation {

    override fun impact(style: String) = buzz(IMPACT_MS[style] ?: 20L)
    override fun notification(type: String) = buzz(NOTIFICATION_MS[type] ?: 30L)
    override fun selection() = buzz(10L)
    override fun vibrate(duration_ms: Long) { if (duration_ms > 0) buzz(duration_ms) }
    override fun cancel() { vibrator()?.cancel() }

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
