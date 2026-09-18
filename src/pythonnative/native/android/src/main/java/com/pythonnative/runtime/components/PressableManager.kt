package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.annotation.SuppressLint
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.Drawable
import android.graphics.drawable.RippleDrawable
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.gestures.GestureCoordinator
import com.pythonnative.runtime.views.PNFrameLayout
import org.json.JSONObject
import kotlin.math.hypot

/**
 * `Pressable` element: a container dispatching press events from one
 * touch stream. `on_press_in` at finger-down (plus an opacity dip),
 * `on_long_press` after the long-press timeout, `on_press` on a clean
 * release, and `on_press_out` when the finger lifts or the touch
 * cancels. The same stream feeds the gesture coordinator so press
 * feedback and pan/pinch recognition coexist on one view.
 */
class PressableManager : ViewManager() {
    private class Press(val downX: Double, val downY: Double, val seq: Int) {
        var moved = false
        var longFired = false
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val view = PNFrameLayout(context)
        view.isClickable = true
        view.isFocusable = true
        view.setOnTouchListener { v, event -> onTouch(v, event) }
        return view
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = PressableProps(props)
        // Press handling owns the touch listener; gesture specs are fed from inside it.
        stateOf(view)["gestures_bound"] = true
        super.applyProps(view, props, initial)
        val merged = propsOf(view)
        if (typed.has_android_ripple || props.has("ripple") || (merged.has("android_ripple") && ViewStyler.touchesBackground(props))) {
            applyRipple(view, merged)
        }
        if (typed.has_disabled) view.isEnabled = typed.disabled != true
    }

    private fun applyRipple(view: View, merged: JSONObject) {
        val state = stateOf(view)
        val ripple = runCatching { PressableProps(merged).android_ripple }.getOrNull()
        val legacy = merged.value("ripple")
        // Undo a background-mode ripple so the styled background can be re-wrapped or restored.
        (view.background as? RippleDrawable)?.let { existing ->
            if (state["ripple_background"] === existing) view.background = state["ripple_content"] as? Drawable
        }
        state.remove("ripple_background")
        state.remove("ripple_content")
        if (ripple == null && (legacy == null || legacy == false)) {
            view.foreground = null
            return
        }
        val color = ripple?.let { PNColor.parse(PNValues.encode(it.color)) }
            ?: (legacy as? JSONObject)?.let { PNColor.parse(it.value("color")) } ?: PNColor.parse(legacy) ?: 0x33000000
        val borderless = ripple?.borderless ?: ((legacy as? JSONObject)?.let { JsonUtil.truthy(it.value("borderless")) } ?: false)
        val foreground = ripple?.foreground ?: true
        val mask = if (borderless) null else ColorDrawable(0xFFFFFFFF.toInt())
        if (foreground) {
            val drawable = RippleDrawable(ColorStateList.valueOf(color), null, mask)
            ripple?.radius?.let { drawable.radius = px(it) }
            view.foreground = drawable
        } else {
            view.foreground = null
            val content = view.background
            val drawable = RippleDrawable(ColorStateList.valueOf(color), content, mask ?: content)
            ripple?.radius?.let { drawable.radius = px(it) }
            state["ripple_content"] = content
            state["ripple_background"] = drawable
            view.background = drawable
        }
    }

    private fun onTouch(view: View, event: MotionEvent): Boolean {
        if (ViewStyler.pointerEventsBlocked(view)) return false
        val record = recordOf(view) ?: return false
        GestureCoordinator.feed(record, event)
        if (!view.isEnabled) return true
        val state = record.state
        val merged = record.props
        val density = view.resources.displayMetrics.density
        val x = event.x / density
        val y = event.y / density
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                val seq = ((state["press_seq"] as? Int) ?: 0) + 1
                val press = Press(x.toDouble(), y.toDouble(), seq)
                state["press"] = press
                state["press_seq"] = seq
                fire(view, "on_press_in")
                val opacity = merged.num("pressed_opacity") ?: merged.num("active_opacity") ?: 0.6
                if (opacity < 1.0) view.animate().alpha(opacity.toFloat()).setDuration(50).start()
                if (hasEvent(view, "on_long_press")) {
                    val delay = merged.num("delay_long_press")?.toLong() ?: ViewConfiguration.getLongPressTimeout().toLong().coerceAtLeast(500L)
                    MainThread.postDelayed({
                        val live = recordOf(view)?.state?.get("press") as? Press ?: return@postDelayed
                        if (live.seq != seq || live.moved || live.longFired) return@postDelayed
                        live.longFired = true
                        fire(view, "on_long_press")
                    }, delay)
                }
                view.isPressed = true
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val press = state["press"] as? Press ?: return true
                val slop = merged.num("tap_slop") ?: TAP_SLOP_DP
                if (hypot(x - press.downX, y - press.downY) > slop) press.moved = true
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                val press = state["press"] as? Press
                state["press"] = null
                view.isPressed = false
                if (press == null) return true
                fire(view, "on_press_out")
                view.animate().alpha(1f).setDuration(100).start()
                if (event.actionMasked == MotionEvent.ACTION_UP && !press.moved && !press.longFired) {
                    view.performClick()
                    fire(view, "on_press")
                }
                return true
            }
        }
        return true
    }

    private companion object {
        const val TAP_SLOP_DP = 12.0
    }
}
