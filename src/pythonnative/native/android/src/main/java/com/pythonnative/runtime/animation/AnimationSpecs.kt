package com.pythonnative.runtime.animation

import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Pure-Kotlin decoding of animation specs (`pn.Animated.timing`,
 * `spring`, `decay`) and their mapping to Android animator parameters.
 * Kept free of Android types so the math is unit-testable. `decay`
 * follows React Native's model and is evaluated in closed form by
 * [Decay] so the Choreographer-driven animator reproduces the Python
 * ticker and the browser preview exactly.
 */
object AnimationSpecs {
    /** React Native's default `deceleration` for `Animated.decay`. */
    const val DEFAULT_DECELERATION = 0.998

    /** A decay stops once its velocity drops below this many points per millisecond. */
    const val DECAY_REST_VELOCITY = 0.001

    /** A decay also stops once its value sits within this distance of the projected final value. */
    const val DECAY_REST_DISTANCE = 0.1

    /**
     * Cubic-bezier control points for the named CSS-style curves, shared
     * with the Python ticker (`animated._NAMED_EASING_BEZIERS`) and the
     * browser preview.
     */
    val NAMED_BEZIERS: Map<String, DoubleArray> = mapOf(
        "ease" to doubleArrayOf(0.42, 0.0, 1.0, 1.0),
        "ease_in" to doubleArrayOf(0.42, 0.0, 1.0, 1.0),
        "ease_out" to doubleArrayOf(0.0, 0.0, 0.58, 1.0),
        "ease_in_out" to doubleArrayOf(0.42, 0.0, 0.58, 1.0),
    )

    /** Polynomial and bounce easings evaluated directly (`t` in `0..1`). */
    val EASINGS: Map<String, (Float) -> Float> = mapOf(
        "linear" to { t -> t },
        "quad" to { t -> t * t },
        "cubic" to { t -> t * t * t },
        "bounce" to { t -> bounceOut(t) },
    )

    /** Every easing name `Animated.timing` may send. */
    val EASING_NAMES: Set<String> = EASINGS.keys + NAMED_BEZIERS.keys

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

    /**
     * Decoded `decay` parameters in React Native's model.
     *
     * Velocity is in spec units per millisecond and decays as
     * `v(t) = v0 * deceleration^t` (`t` in milliseconds), so the value is
     * `x(t) = from + v0 * (1 - deceleration^t) / (1 - deceleration)` and
     * the animation settles at `from + v0 / (1 - deceleration)`.
     */
    data class Decay(
        val from: Double,
        /** Initial velocity in units per millisecond. */
        val velocity: Double,
        /** Per-millisecond velocity multiplier in `(0, 1)`; `0.998` by default. */
        val deceleration: Double,
    ) {
        /** Where the value settles: `from + v0 / (1 - deceleration)`. */
        val projectedFinal: Double get() = from + velocity / (1.0 - deceleration)

        /** Velocity after `elapsedMs` milliseconds. */
        fun velocityAt(elapsedMs: Double): Double = velocity * deceleration.pow(max(0.0, elapsedMs))

        /** Value after `elapsedMs` milliseconds. */
        fun valueAt(elapsedMs: Double): Double =
            from + velocity * (1.0 - deceleration.pow(max(0.0, elapsedMs))) / (1.0 - deceleration)

        /**
         * Whether the decay has come to rest after `elapsedMs`: the velocity
         * fell below [DECAY_REST_VELOCITY] or the value is within
         * [DECAY_REST_DISTANCE] of [projectedFinal].
         */
        fun isFinished(elapsedMs: Double): Boolean =
            abs(velocityAt(elapsedMs)) < DECAY_REST_VELOCITY || abs(projectedFinal - valueAt(elapsedMs)) < DECAY_REST_DISTANCE
    }

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

    fun decay(spec: JSONObject): Decay = Decay(
        from = spec.optDouble("from", 0.0),
        velocity = spec.optDouble("velocity", 0.0).takeIf { it.isFinite() } ?: 0.0,
        deceleration = spec.optDouble("deceleration", DEFAULT_DECELERATION).takeIf { it.isFinite() }?.coerceIn(1e-6, 1.0 - 1e-6)
            ?: DEFAULT_DECELERATION,
    )

    /**
     * Resolve an easing value: a name from [EASING_NAMES] or a bare
     * four-number array of cubic-bezier control points. Beziers (named or
     * literal) come back as a `DoubleArray` for a `PathInterpolator`; the
     * polynomial curves as a `(Float) -> Float`. Anything else, including
     * the Python ticker's `"custom"` marker, yields `null` so the caller
     * declines the native drive and Python ticks the animation instead;
     * there is no silent fallback curve.
     */
    fun resolveEasing(easing: Any?): Any? {
        if (easing == null || easing == JSONObject.NULL) return NAMED_BEZIERS.getValue("ease_in_out")
        if (easing is JSONArray && easing.length() == 4) {
            val points = DoubleArray(4) { easing.optDouble(it, Double.NaN) }
            return if (points.all { it.isFinite() } && points[0] in 0.0..1.0 && points[2] in 0.0..1.0) points else null
        }
        if (easing is String) {
            val name = easing.trim()
            NAMED_BEZIERS[name]?.let { return it }
            return EASINGS[name]
        }
        return null
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
