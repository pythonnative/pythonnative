package com.pythonnative.runtime

import com.pythonnative.runtime.animation.AnimationSpecs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.ln
import kotlin.math.pow
import kotlin.math.sqrt

class AnimationSpecsTest {
    @Test
    fun springDampingRatio() {
        // Critically damped when damping = 2 * sqrt(k * m).
        val k = 100.0
        val m = 2.0
        val critical = 2 * sqrt(k * m)
        assertEquals(1.0, AnimationSpecs.dampingRatio(k, critical, m), 1e-9)
        val spec = JSONObject("""{"kind":"spring","from":0,"to":1,"stiffness":100,"damping":10,"mass":1}""")
        val spring = AnimationSpecs.spring(spec)
        assertEquals(100.0, spring.stiffness, 1e-9)
        assertEquals(0.5, spring.dampingRatio, 1e-9)
        // Mass scales the effective stiffness so the natural frequency matches.
        val heavy = AnimationSpecs.spring(JSONObject("""{"kind":"spring","stiffness":100,"damping":10,"mass":4}"""))
        assertEquals(25.0, heavy.stiffness, 1e-9)
        assertEquals(10.0 / (2 * sqrt(400.0)), heavy.dampingRatio, 1e-9)
    }

    @Test
    fun decayFollowsReactNativeClosedForm() {
        // v(t) = v0 * d^t, x(t) = x0 + v0 * (1 - d^t) / (1 - d), final = x0 + v0 / (1 - d).
        val decay = AnimationSpecs.decay(JSONObject("""{"kind":"decay","from":10,"velocity":2,"deceleration":0.998}"""))
        assertEquals(10.0, decay.from, 0.0)
        assertEquals(2.0, decay.velocity, 0.0)
        assertEquals(0.998, decay.deceleration, 0.0)
        assertEquals(10.0 + 2.0 / 0.002, decay.projectedFinal, 1e-9)
        for (t in listOf(0.0, 16.0, 250.0, 1000.0, 5000.0)) {
            val expectedVelocity = 2.0 * 0.998.pow(t)
            val expectedValue = 10.0 + 2.0 * (1.0 - 0.998.pow(t)) / (1.0 - 0.998)
            assertEquals(expectedVelocity, decay.velocityAt(t), 1e-9)
            assertEquals(expectedValue, decay.valueAt(t), 1e-9)
        }
        assertEquals(10.0, decay.valueAt(0.0), 0.0)
        assertTrue(decay.valueAt(1e6) <= decay.projectedFinal + 1e-9)
    }

    @Test
    fun decayStopsAtRestVelocityOrWithinRestDistance() {
        val decay = AnimationSpecs.Decay(from = 0.0, velocity = 2.0, deceleration = 0.998)
        assertFalse(decay.isFinished(0.0))
        assertFalse(decay.isFinished(1000.0))
        // |v| < 0.001 pt/ms after ln(0.0005) / ln(0.998) ~ 3797 ms.
        val restAt = ln(AnimationSpecs.DECAY_REST_VELOCITY / 2.0) / ln(0.998)
        assertFalse(decay.isFinished(restAt - 50.0))
        assertTrue(decay.isFinished(restAt + 1.0))
        // A tiny fling is within 0.1 of its final value immediately.
        assertTrue(AnimationSpecs.Decay(from = 0.0, velocity = 0.0001, deceleration = 0.998).isFinished(0.0))
        // Zero velocity rests at once and settles exactly at `from`.
        val still = AnimationSpecs.decay(JSONObject("""{"kind":"decay","from":5,"velocity":0}"""))
        assertTrue(still.isFinished(0.0))
        assertEquals(5.0, still.projectedFinal, 0.0)
    }

    @Test
    fun decayDefaultsAndClampsDeceleration() {
        val defaults = AnimationSpecs.decay(JSONObject("""{"kind":"decay","velocity":1}"""))
        assertEquals(AnimationSpecs.DEFAULT_DECELERATION, defaults.deceleration, 0.0)
        assertEquals(1.0 / (1.0 - 0.998), defaults.projectedFinal, 1e-9)
        // A deceleration of 1 would never settle; it is clamped below 1.
        val clamped = AnimationSpecs.decay(JSONObject("""{"kind":"decay","velocity":1,"deceleration":1}"""))
        assertTrue(clamped.deceleration < 1.0)
        assertTrue(clamped.projectedFinal.isFinite())
        // Negative velocity travels the other way.
        val backwards = AnimationSpecs.decay(JSONObject("""{"kind":"decay","from":100,"velocity":-0.5}"""))
        assertEquals(100.0 - 0.5 / 0.002, backwards.projectedFinal, 1e-9)
        assertTrue(backwards.valueAt(500.0) < 100.0)
    }

    @Test
    fun timingDefaults() {
        val timing = AnimationSpecs.timing(JSONObject("""{"kind":"timing","from":0,"to":1}"""))
        assertEquals(300L, timing.durationMs)
        assertEquals(1.0, timing.to, 0.0)
    }

    @Test
    fun easingNamesMatchPythonCurves() {
        @Suppress("UNCHECKED_CAST")
        val linear = AnimationSpecs.resolveEasing("linear") as (Float) -> Float
        assertEquals(0.3f, linear(0.3f), 1e-6f)
        @Suppress("UNCHECKED_CAST")
        val quad = AnimationSpecs.resolveEasing("quad") as (Float) -> Float
        assertEquals(0.25f, quad(0.5f), 1e-6f)
        @Suppress("UNCHECKED_CAST")
        val cubic = AnimationSpecs.resolveEasing("cubic") as (Float) -> Float
        assertEquals(0.125f, cubic(0.5f), 1e-6f)
        @Suppress("UNCHECKED_CAST")
        val bounce = AnimationSpecs.resolveEasing("bounce") as (Float) -> Float
        assertEquals(1f, bounce(1f), 1e-6f)
        assertTrue(bounce(0.5f) in 0f..1f)
        // The CSS-style names are cubic beziers shared with the Python ticker.
        assertArrayEquals(doubleArrayOf(0.42, 0.0, 1.0, 1.0), AnimationSpecs.resolveEasing("ease") as DoubleArray, 1e-9)
        assertArrayEquals(doubleArrayOf(0.42, 0.0, 1.0, 1.0), AnimationSpecs.resolveEasing("ease_in") as DoubleArray, 1e-9)
        assertArrayEquals(doubleArrayOf(0.0, 0.0, 0.58, 1.0), AnimationSpecs.resolveEasing("ease_out") as DoubleArray, 1e-9)
        assertArrayEquals(doubleArrayOf(0.42, 0.0, 0.58, 1.0), AnimationSpecs.resolveEasing("ease_in_out") as DoubleArray, 1e-9)
        assertEquals(setOf("linear", "quad", "cubic", "bounce", "ease", "ease_in", "ease_out", "ease_in_out"), AnimationSpecs.EASING_NAMES)
    }

    @Test
    fun unknownEasingsAreDeclinedNotGuessed() {
        assertNull(AnimationSpecs.resolveEasing("does-not-exist"))
        assertNull(AnimationSpecs.resolveEasing("custom"))
        assertNull(AnimationSpecs.resolveEasing("cubic-bezier(0.42, 0, 1, 1)"))
        assertNull(AnimationSpecs.resolveEasing(JSONArray("[0.1, 0.2]")))
        assertNull(AnimationSpecs.resolveEasing(JSONArray("[1.5, 0, 1, 1]")))
        // A missing easing keeps the timing default.
        assertArrayEquals(doubleArrayOf(0.42, 0.0, 0.58, 1.0), AnimationSpecs.resolveEasing(null) as DoubleArray, 1e-9)
    }

    @Test
    fun cubicBezierArraysAreControlPoints() {
        val pts = AnimationSpecs.resolveEasing(JSONArray("[0.25, 0.1, 0.25, 1.0]")) as DoubleArray
        assertArrayEquals(doubleArrayOf(0.25, 0.1, 0.25, 1.0), pts, 1e-9)
    }
}
