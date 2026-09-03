package com.pythonnative.runtime.animation

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ArgbEvaluator
import android.animation.TimeInterpolator
import android.animation.ValueAnimator
import android.view.View
import android.view.animation.PathInterpolator
import android.widget.TextView
import androidx.dynamicanimation.animation.DynamicAnimation
import androidx.dynamicanimation.animation.FlingAnimation
import androidx.dynamicanimation.animation.FloatPropertyCompat
import androidx.dynamicanimation.animation.SpringAnimation
import androidx.dynamicanimation.animation.SpringForce
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.components.PNColor
import com.pythonnative.runtime.components.ViewStyler
import org.json.JSONObject

/**
 * Native driver for `animate` requests on the animatable props
 * (`opacity`, `background_color`, `translate_x`, `translate_y`,
 * `scale`, `scale_x`, `scale_y`, `rotate`, plus `color` for text).
 *
 * `timing` runs on a `ValueAnimator`, `spring` on a `SpringAnimation`,
 * and `decay` on a `FlingAnimation`. Completion is reported with
 * `callback("animation", 0, "", {"id": n, "finished": bool})`.
 */
object PNAnimator {
    private class Running(val view: View, val prop: String, val cancel: () -> Unit)

    private val running = HashMap<Long, Running>()

    /** Handle one request object; returns the JSON reply string per the spec. */
    fun handle(record: ViewRecord, request: JSONObject): String? {
        val view = record.view
        return when (request.optString("op")) {
            "set" -> {
                record.manager.setAnimatedProperty(view, request.optString("prop"), request.opt("value"))
                null
            }
            "start" -> {
                val id = request.optLong("id")
                val spec = request.optJSONObject("spec") ?: JSONObject()
                val ok = record.manager.startAnimation(view, id, request.optString("prop"), spec)
                JSONObject().put("ok", ok).toString()
            }
            "cancel" -> {
                val value = record.manager.cancelAnimation(view, request.optLong("id"))
                if (value == null) null else JSONObject().put("value", JsonUtil.wrap(value)).toString()
            }
            else -> null
        }
    }

    // ------------------------------------------------------------------
    // Property access
    // ------------------------------------------------------------------

    /** Apply one animation frame to `view`. Unknown props are ignored. */
    fun setProperty(view: View, prop: String, value: Any?) {
        if (JsonUtil.isNull(value)) return
        try {
            when (prop) {
                "opacity" -> view.alpha = JsonUtil.toDouble(value).toFloat()
                "translate_x" -> view.translationX = px(JsonUtil.toDouble(value))
                "translate_y" -> view.translationY = px(JsonUtil.toDouble(value))
                "scale" -> {
                    val s = JsonUtil.toDouble(value).toFloat()
                    view.scaleX = s
                    view.scaleY = s
                }
                "scale_x" -> view.scaleX = JsonUtil.toDouble(value).toFloat()
                "scale_y" -> view.scaleY = JsonUtil.toDouble(value).toFloat()
                "rotate" -> view.rotation = ViewStyler.angleDegrees(value)
                "background_color" -> ViewStyler.setAnimatedBackground(view, value)
                "color" -> (view as? TextView)?.setTextColor(PNColor.parseOr(value, 0xFF000000.toInt()))
            }
        } catch (e: Exception) {
            PNLog.swallowed("PNAnimator.setProperty", e)
        }
    }

    /** Read the current (presentation) value of an animatable prop, or `null`. */
    fun readProperty(view: View, prop: String): Any? = when (prop) {
        "opacity" -> view.alpha.toDouble()
        "translate_x" -> view.translationX / PNBridge.density().toDouble()
        "translate_y" -> view.translationY / PNBridge.density().toDouble()
        "scale", "scale_x" -> view.scaleX.toDouble()
        "scale_y" -> view.scaleY.toDouble()
        "rotate" -> view.rotation.toDouble()
        else -> null
    }

    // ------------------------------------------------------------------
    // Start / cancel
    // ------------------------------------------------------------------

    /** Start a native animation; `false` means Python should tick it instead. */
    fun start(view: View, id: Long, prop: String, spec: JSONObject): Boolean {
        cancelQuietly(id)
        return try {
            when (AnimationSpecs.kind(spec)) {
                "timing" -> startTiming(view, id, prop, spec)
                "spring" -> startSpring(view, id, prop, spec)
                "decay" -> startDecay(view, id, prop, spec)
                else -> false
            }
        } catch (e: Exception) {
            PNLog.rateLimited("anim-start", "native animation failed for '$prop'", e)
            running.remove(id)
            false
        }
    }

    /** Cancel `id` and return the presentation value of its prop, if readable. */
    fun cancel(id: Long): Any? {
        val entry = running.remove(id) ?: return null
        try {
            entry.cancel()
        } catch (e: Exception) {
            PNLog.swallowed("PNAnimator.cancel", e)
        }
        return readProperty(entry.view, entry.prop)
    }

    private fun cancelQuietly(id: Long) {
        running.remove(id)?.let { runCatching { it.cancel() } }
    }

    private fun complete(id: Long, finished: Boolean) {
        if (running.remove(id) == null) return
        PNBridge.callPython("animation", 0, "", JSONObject().put("id", id).put("finished", finished).toString())
    }

    private fun startTiming(view: View, id: Long, prop: String, spec: JSONObject): Boolean {
        val timing = AnimationSpecs.timing(spec)
        val animator: ValueAnimator
        if (prop == "background_color") {
            val from = PNColor.parse(spec.opt("from")) ?: return false
            val to = PNColor.parse(spec.opt("to")) ?: return false
            animator = ValueAnimator.ofObject(ArgbEvaluator(), from, to)
            animator.addUpdateListener { ViewStyler.setAnimatedBackground(view, it.animatedValue as Int) }
        } else if (prop == "color") {
            val from = PNColor.parse(spec.opt("from")) ?: return false
            val to = PNColor.parse(spec.opt("to")) ?: return false
            animator = ValueAnimator.ofObject(ArgbEvaluator(), from, to)
            animator.addUpdateListener { (view as? TextView)?.setTextColor(it.animatedValue as Int) }
        } else {
            if (!isFloatProp(prop)) return false
            animator = ValueAnimator.ofFloat(timing.from.toFloat(), timing.to.toFloat())
            animator.addUpdateListener { setProperty(view, prop, it.animatedValue as Float) }
        }
        animator.duration = timing.durationMs
        animator.interpolator = interpolator(timing.easing)
        var cancelled = false
        animator.addListener(object : AnimatorListenerAdapter() {
            override fun onAnimationCancel(animation: Animator) {
                cancelled = true
            }

            override fun onAnimationEnd(animation: Animator) {
                complete(id, !cancelled)
            }
        })
        running[id] = Running(view, prop) { animator.cancel() }
        animator.start()
        return true
    }

    private fun startSpring(view: View, id: Long, prop: String, spec: JSONObject): Boolean {
        val params = AnimationSpecs.spring(spec)
        val property = floatProperty(prop) ?: return false
        val scale = unitScale(prop)
        val anim = SpringAnimation(view, property, (params.to * scale).toFloat())
        anim.spring = SpringForce((params.to * scale).toFloat())
            .setStiffness(params.stiffness.toFloat())
            .setDampingRatio(params.dampingRatio.toFloat())
        anim.setStartValue((params.from * scale).toFloat())
        anim.setStartVelocity((params.initialVelocity * scale).toFloat())
        anim.addEndListener { _, canceled, _, _ -> complete(id, !canceled) }
        running[id] = Running(view, prop) { anim.cancel() }
        anim.start()
        return true
    }

    private fun startDecay(view: View, id: Long, prop: String, spec: JSONObject): Boolean {
        val params = AnimationSpecs.decay(spec)
        val property = floatProperty(prop) ?: return false
        val scale = unitScale(prop)
        val anim = FlingAnimation(view, property)
        anim.setStartValue((params.from * scale).toFloat())
        anim.setStartVelocity((params.startVelocity * scale).toFloat())
        anim.friction = params.friction.toFloat()
        anim.addEndListener { _, canceled, _, _ -> complete(id, !canceled) }
        running[id] = Running(view, prop) { anim.cancel() }
        anim.start()
        return true
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private fun px(dp: Double): Float = (dp * PNBridge.density()).toFloat()

    private fun isFloatProp(prop: String): Boolean =
        prop in setOf("opacity", "translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate")

    /** Multiplier from spec units to native units (dp to px for translations). */
    private fun unitScale(prop: String): Double =
        if (prop == "translate_x" || prop == "translate_y") PNBridge.density().toDouble() else 1.0

    /** A `FloatPropertyCompat` for physics animations; `null` for unsupported props. */
    private fun floatProperty(prop: String): FloatPropertyCompat<View>? = when (prop) {
        "opacity" -> DynamicAnimation.ALPHA
        "translate_x" -> DynamicAnimation.TRANSLATION_X
        "translate_y" -> DynamicAnimation.TRANSLATION_Y
        "scale_x" -> DynamicAnimation.SCALE_X
        "scale_y" -> DynamicAnimation.SCALE_Y
        "rotate" -> DynamicAnimation.ROTATION
        "scale" -> object : FloatPropertyCompat<View>("pnScale") {
            override fun getValue(v: View): Float = v.scaleX
            override fun setValue(v: View, value: Float) {
                v.scaleX = value
                v.scaleY = value
            }
        }
        // Color props are not floats; physics specs on them fall back to the Python ticker.
        else -> null
    }

    private fun interpolator(easing: Any?): TimeInterpolator {
        return when (val resolved = AnimationSpecs.resolveEasing(easing)) {
            is DoubleArray -> PathInterpolator(
                resolved[0].toFloat(), resolved[1].toFloat(), resolved[2].toFloat(), resolved[3].toFloat(),
            )
            else -> {
                @Suppress("UNCHECKED_CAST")
                val fn = resolved as (Float) -> Float
                TimeInterpolator { t -> fn(t) }
            }
        }
    }
}
