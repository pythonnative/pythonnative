package com.pythonnative.runtime

import com.pythonnative.runtime.animation.AnimationSpecs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.exp
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
    fun decayFrictionReproducesPythonDecay() {
        val k = 0.002
        val friction = AnimationSpecs.decayFriction(k)
        // FlingAnimation: v(t) = v0 * exp(-4.2 * friction * t); Python: v0 * exp(-k * 1000 * t).
        val t = 0.25
        assertEquals(exp(-k * 1000 * t), exp(-AnimationSpecs.FLING_FRICTION_SCALE * friction * t), 1e-9)
        val decay = AnimationSpecs.decay(JSONObject("""{"kind":"decay","from":10,"velocity":2,"deceleration":0.002}"""))
        assertEquals(2000.0, decay.startVelocity, 1e-9)
        assertEquals(10.0 + 2.0 / (0.002 * 1000.0), decay.projectedFinal, 1e-9)
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
        val easeInOut = AnimationSpecs.resolveEasing("ease_in_out") as (Float) -> Float
        assertEquals(0.5f, easeInOut(0.5f), 1e-6f)
        assertEquals(0.15625f, easeInOut(0.25f), 1e-6f)
        @Suppress("UNCHECKED_CAST")
        val linear = AnimationSpecs.resolveEasing("linear") as (Float) -> Float
        assertEquals(0.3f, linear(0.3f), 1e-6f)
        @Suppress("UNCHECKED_CAST")
        val fallback = AnimationSpecs.resolveEasing("does-not-exist") as (Float) -> Float
        assertEquals(easeInOut(0.3f), fallback(0.3f), 1e-6f)
        @Suppress("UNCHECKED_CAST")
        val bounce = AnimationSpecs.resolveEasing("bounce") as (Float) -> Float
        assertEquals(1f, bounce(1f), 1e-6f)
        assertTrue(bounce(0.5f) in 0f..1f)
    }

    @Test
    fun cubicBezierArraysAreControlPoints() {
        val pts = AnimationSpecs.resolveEasing(JSONArray("[0.25, 0.1, 0.25, 1.0]")) as DoubleArray
        assertArrayEquals(doubleArrayOf(0.25, 0.1, 0.25, 1.0), pts, 1e-9)
        val css = AnimationSpecs.resolveEasing("cubic-bezier(0.42, 0, 1, 1)") as DoubleArray
        assertArrayEquals(doubleArrayOf(0.42, 0.0, 1.0, 1.0), css, 1e-9)
    }
}
