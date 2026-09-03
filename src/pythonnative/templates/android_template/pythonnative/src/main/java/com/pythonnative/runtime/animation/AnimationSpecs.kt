package com.pythonnative.runtime.animation

import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Pure-Kotlin decoding of animation specs (`pn.Animated.timing`,
 * `spring`, `decay`) and their mapping to Android animator parameters.
 * Kept free of Android types so the math is unit-testable.
 */
object AnimationSpecs {
    /** `FlingAnimation` scales `friction` by this constant internally (`DragForce`). */
    const val FLING_FRICTION_SCALE = 4.2

    /** Easing curves identical to the Python ticker's `_EASINGS`. */
    val EASINGS: Map<String, (Float) -> Float> = mapOf(
        "linear" to { t -> t },
        "ease" to { t -> 3f * t * t - 2f * t * t * t },
        "ease_in" to { t -> t * t },
        "ease_out" to { t -> 1f - (1f - t) * (1f - t) },
        "ease_in_out" to { t -> 3f * t * t - 2f * t * t * t },
        "ease_in_quad" to { t -> t * t },
        "ease_out_quad" to { t -> 1f - (1f - t) * (1f - t) },
        "bounce" to { t -> bounceOut(t) },
    )

    /** Decoded `timing` parameters. */
    data class Timing(val from: Double, val to: Double, val durationMs: Long, val easing: Any?)

    /** Decoded `spring` parameters mapped to `SpringForce` terms. */
    data class Spring(
        val from: Double,
        val to: Double,
        /** `stiffness / mass`, so the natural frequency matches the Python integrator. */
        val stiffness: Double,
        /** `damping / (2 * sqrt(stiffness * mass))`. */
        val dampingRatio: Double,
        /** Units per second. */
        val initialVelocity: Double,
    )

    /** Decoded `decay` parameters mapped to `FlingAnimation` terms. */
    data class Decay(
        val from: Double,
        /** Units per second (Python specs use units per millisecond). */
        val startVelocity: Double,
        /** `FlingAnimation.setFriction` value reproducing `v(t) = v0 * exp(-k * 1000 * t)`. */
        val friction: Double,
        /** Where the value settles: `from + v0 / (k * 1000)`. */
        val projectedFinal: Double,
    )

    fun kind(spec: JSONObject): String = spec.optString("kind", "")

    fun timing(spec: JSONObject): Timing = Timing(
        from = spec.optDouble("from", 0.0),
        to = spec.optDouble("to", 0.0),
        durationMs = max(0L, spec.optDouble("duration_ms", 300.0).toLong()),
        easing = spec.opt("easing"),
    )

    fun spring(spec: JSONObject): Spring {
        val stiffness = max(1e-6, spec.optDouble("stiffness", 100.0))
        val damping = max(0.0, spec.optDouble("damping", 10.0))
        val mass = max(1e-6, spec.optDouble("mass", 1.0))
        return Spring(
            from = spec.optDouble("from", 0.0),
            to = spec.optDouble("to", 0.0),
            stiffness = stiffness / mass,
            dampingRatio = dampingRatio(stiffness, damping, mass),
            initialVelocity = spec.optDouble("initial_velocity", 0.0),
        )
    }

    /** `damping / (2 * sqrt(stiffness * mass))`. */
    fun dampingRatio(stiffness: Double, damping: Double, mass: Double): Double =
        damping / (2.0 * sqrt(max(1e-12, stiffness * mass)))

    fun decay(spec: JSONObject): Decay {
        val v0PerMs = spec.optDouble("velocity", 0.0)
        val k = max(1e-6, spec.optDouble("deceleration", 0.997))
        val from = spec.optDouble("from", 0.0)
        return Decay(
            from = from,
            startVelocity = v0PerMs * 1000.0,
            friction = decayFriction(k),
            projectedFinal = from + v0PerMs / (k * 1000.0),
        )
    }

    /**
     * The Python ticker decays velocity as `exp(-k * dt_ms)`, that is
     * `exp(-k * 1000 * t_s)`. `FlingAnimation` decays as
     * `exp(-4.2 * friction * t_s)`, so `friction = k * 1000 / 4.2`.
     */
    fun decayFriction(deceleration: Double): Double = deceleration * 1000.0 / FLING_FRICTION_SCALE

    /**
     * Resolve an easing value. Names map to [EASINGS]; a four-number
     * array is returned as cubic-bezier control points (`DoubleArray`)
     * for the caller to build a `PathInterpolator`. Unknown names fall
     * back to `ease_in_out` like the Python ticker.
     */
    fun resolveEasing(easing: Any?): Any {
        if (easing is JSONArray && easing.length() == 4) {
            return DoubleArray(4) { easing.optDouble(it, 0.0) }
        }
        if (easing is String) {
            val trimmed = easing.trim()
            if (trimmed.startsWith("cubic-bezier(") || trimmed.startsWith("cubic_bezier(")) {
                val inner = trimmed.substringAfter('(').substringBeforeLast(')')
                val parts = inner.split(',').mapNotNull { it.trim().toDoubleOrNull() }
                if (parts.size == 4) return parts.toDoubleArray()
            }
            return EASINGS[trimmed] ?: EASINGS.getValue("ease_in_out")
        }
        return EASINGS.getValue("ease_in_out")
    }

    private fun bounceOut(t: Float): Float {
        val n1 = 7.5625f
        val d1 = 2.75f
        return when {
            t < 1f / d1 -> n1 * t * t
            t < 2f / d1 -> {
                val u = t - 1.5f / d1
                n1 * u * u + 0.75f
            }
            t < 2.5f / d1 -> {
                val u = t - 2.25f / d1
                n1 * u * u + 0.9375f
            }
            else -> {
                val u = t - 2.625f / d1
                n1 * u * u + 0.984375f
            }
        }
    }
}
