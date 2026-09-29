package com.pythonnative.runtime.modules

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.database.ContentObserver
import android.os.Build
import android.provider.Settings
import android.view.View
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager
import androidx.core.os.LocaleListCompat
import androidx.core.text.TextUtilsCompat
import androidx.core.view.ViewCompat
import androidx.core.view.accessibility.AccessibilityNodeInfoCompat
import com.pythonnative.generated.AccessibilityInfoEvents
import com.pythonnative.generated.AccessibilityInfoImplementation
import com.pythonnative.generated.KeyboardEvents
import com.pythonnative.generated.KeyboardImplementation
import com.pythonnative.generated.LocalizationEvents
import com.pythonnative.generated.LocalizationImplementation
import com.pythonnative.generated.PNJSONValue
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.screens.PNKeyboard
import java.util.Locale
import java.util.TimeZone

/**
 * `Keyboard`: `dismiss()`, `is_visible()`, and `change` events
 * `{height, visible, duration_ms}` (height in dp) forwarded from the
 * shared [PNKeyboard] observer.
 */
class KeyboardModule : KeyboardImplementation {
    private var unsubscribe: (() -> Unit)? = null

    override fun dismiss() = PNKeyboard.dismiss()
    override fun is_visible(): Boolean = PNKeyboard.isVisible

    /** Start forwarding keyboard transitions as `change` events (idempotent). */
    fun attach() {
        if (unsubscribe != null) return
        unsubscribe = PNKeyboard.addListener { height, visible, durationMs ->
            KeyboardEvents.change(payload(height, visible, durationMs))
        }
    }

    fun detach() {
        unsubscribe?.invoke()
        unsubscribe = null
    }

    companion object {
        /** The `change` payload for a keyboard transition. */
        fun payload(heightDp: Double, visible: Boolean, durationMs: Long): Map<String, PNJSONValue> = mapOf(
            "height" to PNJSONValue(heightDp),
            "visible" to PNJSONValue(visible),
            "duration_ms" to PNJSONValue(durationMs.toDouble()),
        )
    }
}

/**
 * `AccessibilityInfo`: screen-reader and reduce-motion queries, spoken
 * announcements, focus moves, and `change` events
 * `{screen_reader, reduce_motion}`.
 *
 * `is_screen_reader_enabled` is TalkBack-style touch exploration (or
 * any enabled accessibility service when touch exploration is off).
 * `is_reduce_motion_enabled` reads `Settings.Global.ANIMATOR_DURATION_SCALE`
 * (`0` means the user removed animations) and, on Android 14+, the
 * "remove animations" transition setting. `announce` speaks through
 * `View.announceForAccessibility` on the activity's content view;
 * `set_accessibility_focus` moves TalkBack's focus to a PythonNative
 * view by tag. Changes come from the `AccessibilityManager` listeners
 * and a settings `ContentObserver`.
 */
class AccessibilityInfoModule : AccessibilityInfoImplementation {
    private var stateListener: AccessibilityManager.AccessibilityStateChangeListener? = null
    private var touchListener: AccessibilityManager.TouchExplorationStateChangeListener? = null
    private var observer: ContentObserver? = null
    private var last: Pair<Boolean, Boolean>? = null

    private fun manager(): AccessibilityManager? =
        PNBridge.activity()?.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager

    override fun is_screen_reader_enabled(): Boolean {
        val manager = manager() ?: return false
        return try {
            manager.isTouchExplorationEnabled || (manager.isEnabled && manager.getEnabledAccessibilityServiceList(
                android.accessibilityservice.AccessibilityServiceInfo.FEEDBACK_SPOKEN,
            ).isNotEmpty())
        } catch (_: Exception) {
            manager.isTouchExplorationEnabled
        }
    }

    override fun is_reduce_motion_enabled(): Boolean {
        val ctx = PNBridge.activity() ?: return false
        return isReduceMotion(ctx)
    }

    override fun announce(message: String) {
        val activity = PNBridge.activity() ?: return
        val root = activity.findViewById<View>(android.R.id.content) ?: activity.window?.decorView ?: return
        MainThread.runOnMain { root.announceForAccessibility(message) }
    }

    override fun set_accessibility_focus(tag: Long) {
        val view = PNBridge.registry.get(tag)?.view ?: return
        MainThread.runOnMain {
            try {
                view.sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED)
                ViewCompat.performAccessibilityAction(view, AccessibilityNodeInfoCompat.ACTION_ACCESSIBILITY_FOCUS, null)
            } catch (error: Exception) {
                PNLog.swallowed("AccessibilityInfo.focus", error)
            }
        }
    }

    /** Subscribe to accessibility state and animation-scale changes. */
    fun attach(activity: Activity) {
        val manager = activity.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager
        if (manager != null && stateListener == null) {
            val state = AccessibilityManager.AccessibilityStateChangeListener { changed() }
            val touch = AccessibilityManager.TouchExplorationStateChangeListener { changed() }
            manager.addAccessibilityStateChangeListener(state)
            manager.addTouchExplorationStateChangeListener(touch)
            stateListener = state
            touchListener = touch
        }
        if (observer == null) {
            val obs = object : ContentObserver(MainThread.handler()) {
                override fun onChange(selfChange: Boolean) = changed()
            }
            try {
                activity.contentResolver.registerContentObserver(Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE), false, obs)
                activity.contentResolver.registerContentObserver(Settings.Global.getUriFor(Settings.Global.TRANSITION_ANIMATION_SCALE), false, obs)
                observer = obs
            } catch (error: Exception) {
                PNLog.swallowed("AccessibilityInfo.observe", error)
            }
        }
        last = is_screen_reader_enabled() to is_reduce_motion_enabled()
    }

    fun detach(activity: Activity) {
        val manager = activity.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager
        stateListener?.let { manager?.removeAccessibilityStateChangeListener(it) }
        touchListener?.let { manager?.removeTouchExplorationStateChangeListener(it) }
        stateListener = null
        touchListener = null
        observer?.let { runCatching { activity.contentResolver.unregisterContentObserver(it) } }
        observer = null
    }

    private fun changed() {
        MainThread.runOnMain {
            val current = is_screen_reader_enabled() to is_reduce_motion_enabled()
            if (current == last) return@runOnMain
            last = current
            AccessibilityInfoEvents.change(payload(current.first, current.second))
        }
    }

    companion object {
        /** Whether the system asks for reduced motion (animator scale `0`, or Android 14+ "remove animations"). */
        fun isReduceMotion(ctx: Context): Boolean {
            val scale = try {
                Settings.Global.getFloat(ctx.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
            } catch (_: Exception) {
                1f
            }
            if (scale == 0f) return true
            if (Build.VERSION.SDK_INT >= 34) {
                val transitions = try {
                    Settings.Global.getFloat(ctx.contentResolver, Settings.Global.TRANSITION_ANIMATION_SCALE, 1f)
                } catch (_: Exception) {
                    1f
                }
                if (transitions == 0f) return true
            }
            return false
        }

        fun payload(screenReader: Boolean, reduceMotion: Boolean): Map<String, PNJSONValue> = mapOf(
            "screen_reader" to PNJSONValue(screenReader),
            "reduce_motion" to PNJSONValue(reduceMotion),
        )
    }
}

/**
 * `Localization`: `get_locales()` (the user's preferred-language list
 * as `[{language_tag, language_code, region_code, is_rtl}]`),
 * `get_timezone()` (an IANA id), and `change` events `{locales, timezone}`
 * on `ACTION_LOCALE_CHANGED` / `ACTION_TIMEZONE_CHANGED`.
 */
class LocalizationModule : LocalizationImplementation {
    private var receiver: BroadcastReceiver? = null

    override fun get_locales(): List<Map<String, PNJSONValue>> = locales().map { describe(it) }
    override fun get_timezone(): String = TimeZone.getDefault().id

    fun attach(activity: Activity) {
        if (receiver != null) return
        val r = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                MainThread.runOnMain {
                    LocalizationEvents.change(mapOf("locales" to PNJSONValue(get_locales()), "timezone" to PNJSONValue(get_timezone())))
                }
            }
        }
        try {
            val filter = IntentFilter().apply {
                addAction(Intent.ACTION_LOCALE_CHANGED)
                addAction(Intent.ACTION_TIMEZONE_CHANGED)
            }
            activity.registerReceiver(r, filter)
            receiver = r
        } catch (error: Exception) {
            PNLog.swallowed("Localization.attach", error)
        }
    }

    fun detach(activity: Activity) {
        receiver?.let { runCatching { activity.unregisterReceiver(it) } }
        receiver = null
    }

    companion object {
        /** The preferred locales, most preferred first (never empty). */
        fun locales(): List<Locale> {
            val list = LocaleListCompat.getDefault()
            val out = ArrayList<Locale>()
            for (index in 0 until list.size()) list.get(index)?.let { out.add(it) }
            if (out.isEmpty()) out.add(Locale.getDefault())
            return out
        }

        /** One `Locale` record as the Python `Locale` dataclass expects it. */
        fun describe(locale: Locale): Map<String, PNJSONValue> = mapOf(
            "language_tag" to PNJSONValue(locale.toLanguageTag()),
            "language_code" to PNJSONValue(locale.language),
            "region_code" to PNJSONValue(locale.country),
            "is_rtl" to PNJSONValue(isRtl(locale)),
        )

        fun isRtl(locale: Locale): Boolean =
            TextUtilsCompat.getLayoutDirectionFromLocale(locale) == View.LAYOUT_DIRECTION_RTL
    }
}
