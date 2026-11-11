package com.pythonnative.runtime.animation

import android.view.animation.Interpolator
import com.pythonnative.runtime.bridge.JsonUtil
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToLong
import kotlin.math.sqrt

/**
 * The duration, delay, and curve of an animation the platform runs itself
 * (list item animations and shared-element flights, RFC 0009), read from
 * a motion descriptor: `{"duration", "delay", "easing", "spring"}`.
 *
 * `spring` wins over `easing`. A spring with `duration` uses the core's
 * response and damping-ratio model and runs for that duration; a physical
 * spring (`stiffness`, `damping`, `mass`) runs until it settles. Easing is
 * a name (`linear`, `ease`, `ease_in`, `ease_out`, `ease_in_out`, `quad`,
 * `cubic`, `bounce`), four bezier control points, or `{"samples": [...]}`,
 * with the same curves as `pythonnative.motion.Easing`.
 */
class MotionTiming(val durationMs: Long, val delayMs: Long, val interpolator: Interpolator) {
    companion object {
        /** Android's stack transition length, the default flight and preset duration. */
        const val DEFAULT_DURATION_MS = 300L

        /** Read `spec`, falling back to `defaultDurationMs` and ease-in-out. */
        fun of(spec: JSONObject?, defaultDurationMs: Long = DEFAULT_DURATION_MS): MotionTiming {
            val delay = max(0.0, JsonUtil.toDoubleOrNull(spec?.opt("delay")) ?: 0.0).roundToLong()
            val duration = JsonUtil.toDoubleOrNull(spec?.opt("duration"))?.takeIf { it >= 0 }?.roundToLong() ?: defaultDurationMs
            val spring = spec?.opt("spring") as? JSONObject
            if (spring != null) {
                val curve = SpringCurve.of(spring)
                return MotionTiming(curve.durationMs, delay, curve)
            }
            return MotionTiming(duration, delay, easing(spec?.opt("easing")))
        }

        /** The interpolator for an easing descriptor; null and unknown names are ease-in-out. */
        fun easing(value: Any?): Interpolator = when (value) {
            is String -> when (value) {
                "linear" -> Interpolator { it }
                "ease", "ease_in" -> CubicBezier(0.42f, 0f, 1f, 1f)
                "ease_out" -> CubicBezier(0f, 0f, 0.58f, 1f)
                "quad" -> Interpolator { it * it }
                "cubic" -> Interpolator { it * it * it }
                "bounce" -> Interpolator { bounce(it) }
                else -> CubicBezier(0.42f, 0f, 0.58f, 1f)
            }
            is JSONArray -> if (value.length() == 4) {
                CubicBezier(
                    value.optDouble(0).toFloat(), value.optDouble(1).toFloat(),
                    value.optDouble(2).toFloat(), value.optDouble(3).toFloat(),
                )
            } else CubicBezier(0.42f, 0f, 0.58f, 1f)
            is JSONObject -> (value.opt("samples") as? JSONArray)?.takeIf { it.length() >= 2 }?.let { samples ->
                Sampled(FloatArray(samples.length()) { samples.optDouble(it).toFloat() })
            } ?: CubicBezier(0.42f, 0f, 0.58f, 1f)
            else -> CubicBezier(0.42f, 0f, 0.58f, 1f)
        }

        private fun bounce(input: Float): Float {
            var t = input
            if (t < 1 / 2.75f) return 7.5625f * t * t
            if (t < 2 / 2.75f) { t -= 1.5f / 2.75f; return 7.5625f * t * t + 0.75f }
            if (t < 2.5f / 2.75f) { t -= 2.25f / 2.75f; return 7.5625f * t * t + 0.9375f }
            t -= 2.625f / 2.75f
            return 7.5625f * t * t + 0.984375f
        }
    }

    /** A CSS `cubic-bezier(x1, y1, x2, y2)` curve. */
    class CubicBezier(private val x1: Float, private val y1: Float, private val x2: Float, private val y2: Float) : Interpolator {
        private fun component(t: Float, a: Float, b: Float): Float {
            val u = 1 - t
            return 3 * u * u * t * a + 3 * u * t * t * b + t * t * t
        }

        override fun getInterpolation(input: Float): Float {
            if (input <= 0f) return 0f
            if (input >= 1f) return 1f
            var low = 0f
            var high = 1f
            var t = input
            repeat(40) {
                val x = component(t, x1, x2)
                if (abs(x - input) < 1e-5f) return component(t, y1, y2)
                if (x < input) low = t else high = t
                t = (low + high) / 2
            }
            return component(t, y1, y2)
        }
    }

    /** Linear interpolation between evenly spaced samples. */
    class Sampled(private val samples: FloatArray) : Interpolator {
        override fun getInterpolation(input: Float): Float {
            val position = min(1f, max(0f, input)) * (samples.size - 1)
            val index = min(samples.size - 2, position.toInt())
            val fraction = position - index
            return samples[index] + (samples[index + 1] - samples[index]) * fraction
        }
    }

    /** A spring from 0 to 1, simulated once and sampled over its duration. */
    class SpringCurve private constructor(val durationMs: Long, private val samples: Sampled) : Interpolator {
        override fun getInterpolation(input: Float): Float = if (input >= 1f) 1f else samples.getInterpolation(input)

        companion object {
            private const val STEP = 1.0 / 240.0
            private const val LIMIT_SECONDS = 5.0
            private const val SAMPLES = 120

            fun of(spring: JSONObject): SpringCurve {
                val mass = max(0.001, JsonUtil.toDoubleOrNull(spring.opt("mass")) ?: 1.0)
                val response = JsonUtil.toDoubleOrNull(spring.opt("duration"))?.takeIf { it > 0 }?.div(1000.0)
                val ratio = JsonUtil.toDoubleOrNull(spring.opt("damping_ratio"))
                val stiffness: Double
                val damping: Double
                if (response != null) {
                    stiffness = (2 * PI / response).pow(2) * mass
                    damping = 4 * PI * (ratio ?: 1.0) * mass / response
                } else {
                    stiffness = JsonUtil.toDoubleOrNull(spring.opt("stiffness")) ?: 100.0
                    damping = if (ratio != null && ratio >= 0) 2 * ratio * sqrt(stiffness * mass)
                    else JsonUtil.toDoubleOrNull(spring.opt("damping")) ?: 10.0
                }
                val clamp = JsonUtil.truthy(spring.opt("overshoot_clamping"))
                // Integrate x'' = (-k (x - 1) - c x') / m from rest at 0.
                val positions = ArrayList<Double>()
                var x = 0.0
                var v = 0.0
                var time = 0.0
                positions.add(x)
                while (time < LIMIT_SECONDS) {
                    val a = (-stiffness * (x - 1) - damping * v) / mass
                    v += a * STEP
                    x += v * STEP
                    time += STEP
                    if (clamp && x > 1) x = 1.0
                    positions.add(x)
                    if (response != null && time >= response) break
                    if (response == null && abs(x - 1) < 0.001 && abs(v) < 0.01) break
                }
                val total = positions.size - 1
                val sampled = FloatArray(SAMPLES + 1) { index ->
                    val position = index.toDouble() / SAMPLES * total
                    val low = position.toInt().coerceAtMost(total)
                    val high = (low + 1).coerceAtMost(total)
                    val fraction = position - low
                    (positions[low] + (positions[high] - positions[low]) * fraction).toFloat()
                }
                sampled[SAMPLES] = 1f
                return SpringCurve(max(1L, (time * 1000).roundToLong()), Sampled(sampled))
            }
        }
    }
}
