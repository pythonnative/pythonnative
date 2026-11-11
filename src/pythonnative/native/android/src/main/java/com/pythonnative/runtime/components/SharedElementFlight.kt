package com.pythonnative.runtime.components

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.graphics.RectF
import android.view.View
import android.view.ViewGroup
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.animation.MotionTiming
import com.pythonnative.runtime.animation.PNMotionApplier
import com.pythonnative.runtime.bridge.JsonUtil
import org.json.JSONArray
import org.json.JSONObject

/**
 * One shared element flying between two stack screens (RFC 0009).
 *
 * `pair` is one entry of `pn_core_shared_elements`: `{"name", "source",
 * "target", "transition", "source_style", "target_style"}`. The flight
 * hides the source, lifts the target view into `host`'s overlay at the
 * source's window rect, and moves and resizes it to its own rect with
 * `timing` while blending the transition's `props` (by default
 * `border_radius`, `background_color`, and `opacity`) from the source's
 * style to the target's. At the end the target returns to its parent at
 * its index with its layout params, and the source shows again.
 */
class SharedElementFlight(private val host: ViewGroup, private val pair: JSONObject, private val timing: MotionTiming) {
    private var animator: ValueAnimator? = null

    /** Start flying; returns false when either view is missing or not laid out. */
    fun start(): Boolean {
        val registry = PNBridge.registry
        val source = registry.get(pair.optLong("source"))?.view ?: return false
        val target = registry.get(pair.optLong("target"))?.view ?: return false
        val parent = target.parent as? ViewGroup ?: return false
        if (source.width <= 0 || source.height <= 0 || target.width <= 0 || target.height <= 0) return false
        val from = windowRect(source)
        val to = windowRect(target)
        val origin = IntArray(2).also { host.getLocationInWindow(it) }
        val index = parent.indexOfChild(target)
        val params = target.layoutParams
        val sourceAlpha = source.alpha
        val blends = blends()
        source.alpha = 0f
        // Adding to the overlay detaches the view from its parent.
        host.overlay.add(target)
        fun step(fraction: Float) {
            place(target, lerp(from, to, fraction), origin)
            for ((prop, blend) in blends) apply(target, prop, blend(fraction))
        }
        step(0f)
        val animation = ValueAnimator.ofFloat(0f, 1f)
        animation.duration = timing.durationMs
        animation.interpolator = timing.interpolator
        animation.addUpdateListener { step(it.animatedValue as Float) }
        animation.addListener(object : AnimatorListenerAdapter() {
            private var ended = false
            override fun onAnimationEnd(animation: Animator) {
                if (ended) return
                ended = true
                host.overlay.remove(target)
                if (target.parent == null && PNBridge.registry.recordFor(target) != null) {
                    parent.addView(target, index.coerceIn(0, parent.childCount), params)
                }
                val style = pair.optJSONObject("target_style")
                for ((prop, _) in blends) apply(target, prop, style?.opt(prop)?.takeUnless { JsonUtil.isNull(it) })
                target.requestLayout()
                source.alpha = sourceAlpha
            }
        })
        animator = animation
        animation.start()
        return true
    }

    /** Jump to the end (the flight's views are back where they belong). */
    fun end() {
        animator?.end()
    }

    private fun apply(view: View, prop: String, value: Any?) {
        try {
            PNMotionApplier.apply(view, prop, value)
        } catch (error: Exception) {
            com.pythonnative.runtime.bridge.PNLog.swallowed("SharedElementFlight.apply", error)
        }
    }

    /** Per-prop blends from the source style to the target style. */
    private fun blends(): List<Pair<String, (Float) -> Any?>> {
        val transition = pair.optJSONObject("transition")
        val props = (transition?.opt("props") as? JSONArray)?.let { list -> List(list.length()) { list.optString(it) } }
            ?: DEFAULT_PROPS
        val from = pair.optJSONObject("source_style") ?: JSONObject()
        val to = pair.optJSONObject("target_style") ?: JSONObject()
        return props.filter { it.isNotEmpty() }.mapNotNull { prop -> blend(prop, from.opt(prop), to.opt(prop))?.let { prop to it } }
    }

    companion object {
        /** Props blended when the transition doesn't list its own. */
        val DEFAULT_PROPS = listOf("border_radius", "background_color", "opacity")

        /** A blend for one prop, or null when neither side sets it. */
        fun blend(prop: String, from: Any?, to: Any?): ((Float) -> Any?)? {
            val a = from?.takeUnless { JsonUtil.isNull(it) }
            val b = to?.takeUnless { JsonUtil.isNull(it) }
            if (a == null && b == null) return null
            if (prop.endsWith("color")) {
                val start = PNColor.parse(a)
                val end = PNColor.parse(b)
                if (start == null && end == null) return null
                // A missing side is the other color, fully transparent.
                val first = start ?: (end!! and 0x00FFFFFF)
                val last = end ?: (start!! and 0x00FFFFFF)
                return { fraction -> String.format("#%08X", mix(first, last, fraction)) }
            }
            val fallback = if (prop == "opacity") 1.0 else 0.0
            val start = JsonUtil.toDoubleOrNull(a) ?: fallback
            val end = JsonUtil.toDoubleOrNull(b) ?: fallback
            return { fraction -> start + (end - start) * fraction }
        }

        /** ARGB interpolation, clamped per channel. */
        fun mix(from: Int, to: Int, fraction: Float): Int {
            fun channel(shift: Int): Int {
                val a = (from ushr shift) and 0xFF
                val b = (to ushr shift) and 0xFF
                return (a + (b - a) * fraction).toInt().coerceIn(0, 255) shl shift
            }
            return channel(24) or channel(16) or channel(8) or channel(0)
        }

        fun lerp(from: RectF, to: RectF, fraction: Float): RectF = RectF(
            from.left + (to.left - from.left) * fraction,
            from.top + (to.top - from.top) * fraction,
            from.right + (to.right - from.right) * fraction,
            from.bottom + (to.bottom - from.bottom) * fraction,
        )

        /** A view's rect in window pixels (its scroll position and ancestors' transforms included). */
        fun windowRect(view: View): RectF {
            val location = IntArray(2)
            view.getLocationInWindow(location)
            return RectF(location[0].toFloat(), location[1].toFloat(), (location[0] + view.width).toFloat(), (location[1] + view.height).toFloat())
        }

        /** Lay `view` out at window rect `rect`, relative to an overlay host at window `origin`. */
        fun place(view: View, rect: RectF, origin: IntArray) {
            val left = Math.round(rect.left) - origin[0]
            val top = Math.round(rect.top) - origin[1]
            val width = Math.round(rect.width()).coerceAtLeast(0)
            val height = Math.round(rect.height()).coerceAtLeast(0)
            view.measure(View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(height, View.MeasureSpec.EXACTLY))
            view.layout(left, top, left + width, top + height)
        }
    }
}
