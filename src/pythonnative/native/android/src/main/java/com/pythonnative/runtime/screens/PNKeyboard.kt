package com.pythonnative.runtime.screens

import android.app.Activity
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsAnimationCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import kotlin.math.max

/**
 * The shared on-screen keyboard observer.
 *
 * Watches the activity's decor view for IME window insets and keeps
 * [heightDp] / [isVisible] current, notifying [addListener] callbacks
 * with `(heightDp, visible, durationMs)` whenever either changes. The
 * duration is the IME inset animation's length when the platform
 * reports one (API 30+ or the compat callback), otherwise `0`.
 *
 * `PNScreenFragment` republishes its viewport from these changes, and
 * the `Keyboard` module (`dismiss`, `is_visible`, `change` events) is a
 * thin wrapper over [dismiss], [isVisible], and [addListener].
 */
object PNKeyboard {
    /** Listener signature: keyboard height in dp, visibility, and the transition duration in ms. */
    fun interface Listener {
        fun onKeyboardChanged(heightDp: Double, visible: Boolean, durationMs: Long)
    }

    /** Current keyboard height in dp (`0.0` when hidden). */
    var heightDp: Double = 0.0
        private set

    /** Whether the keyboard is showing. */
    var isVisible: Boolean = false
        private set

    private val listeners = ArrayList<Listener>()
    private var observed: View? = null
    private var pendingDurationMs = 0L

    /** Register `listener`; returns a function that removes it. */
    fun addListener(listener: Listener): () -> Unit {
        listeners.add(listener)
        return { listeners.remove(listener) }
    }

    /**
     * Start observing `activity`'s decor view (idempotent per view).
     *
     * The decor view sees the window's insets before any view consumes
     * them. Under `adjustResize` the window applies the IME inset as
     * padding above the content view, which then reads a zero keyboard
     * height, so observing the content view never saw the keyboard. The
     * listener hands the insets on to the decor view's own handling.
     */
    fun attach(activity: Activity) {
        val root = activity.window?.decorView ?: return
        if (observed === root) return
        observed?.let { detachView(it) }
        observed = root
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            update(insets)
            ViewCompat.onApplyWindowInsets(view, insets)
        }
        ViewCompat.setWindowInsetsAnimationCallback(root, object : WindowInsetsAnimationCompat.Callback(DISPATCH_MODE_CONTINUE_ON_SUBTREE) {
            override fun onPrepare(animation: WindowInsetsAnimationCompat) {
                if (animation.typeMask and WindowInsetsCompat.Type.ime() != 0) pendingDurationMs = animation.durationMillis
            }
            override fun onProgress(insets: WindowInsetsCompat, running: MutableList<WindowInsetsAnimationCompat>): WindowInsetsCompat = insets
            override fun onEnd(animation: WindowInsetsAnimationCompat) {
                if (animation.typeMask and WindowInsetsCompat.Type.ime() != 0) {
                    ViewCompat.getRootWindowInsets(root)?.let { update(it) }
                    pendingDurationMs = 0L
                }
            }
        })
        ViewCompat.getRootWindowInsets(root)?.let { update(it) }
        root.requestApplyInsets()
    }

    /** Stop observing `activity` (called from `Activity.onDestroy`). */
    fun detach(activity: Activity) {
        val root = observed ?: return
        if (root !== activity.window?.decorView) return
        detachView(root)
        observed = null
    }

    /** Read the keyboard state from `insets` and notify listeners when it changed. */
    fun update(insets: WindowInsetsCompat) {
        val density = PNBridge.density()
        val ime = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom
        val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom
        val height = max(0, ime - bars) / density.toDouble()
        val visible = insets.isVisible(WindowInsetsCompat.Type.ime()) && height > 0.0
        if (height == heightDp && visible == isVisible) return
        heightDp = height
        isVisible = visible
        val duration = pendingDurationMs
        for (listener in ArrayList(listeners)) {
            try {
                listener.onKeyboardChanged(height, visible, duration)
            } catch (error: Exception) {
                PNLog.swallowed("PNKeyboard.listener", error)
            }
        }
    }

    /** Hide the keyboard if it is showing. */
    fun dismiss() {
        val activity = PNBridge.activity() ?: return
        val window = activity.window ?: return
        try {
            WindowInsetsControllerCompat(window, window.decorView).hide(WindowInsetsCompat.Type.ime())
            activity.currentFocus?.clearFocus()
        } catch (error: Exception) {
            PNLog.swallowed("PNKeyboard.dismiss", error)
        }
    }

    private fun detachView(view: View) {
        ViewCompat.setOnApplyWindowInsetsListener(view, null)
        ViewCompat.setWindowInsetsAnimationCallback(view, null)
    }
}
