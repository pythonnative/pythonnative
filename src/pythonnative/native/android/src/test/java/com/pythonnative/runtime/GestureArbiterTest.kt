package com.pythonnative.runtime

import com.pythonnative.runtime.gestures.GestureArbiter
import com.pythonnative.runtime.gestures.GestureConfig
import com.pythonnative.runtime.gestures.Offset
import com.pythonnative.runtime.gestures.PanRecognizer
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GestureArbiterTest {
    private class Recorder {
        val events = ArrayList<Pair<Int, Map<String, Any?>>>()
        fun emit(index: Int, payload: Map<String, Any?>) {
            events.add(index to payload)
        }
        fun states(index: Int) = events.filter { it.first == index }.map { it.second["state"] }
    }

    private fun tap(nTaps: Int = 1, sim: Set<Int>? = null, waitFor: Set<Int> = emptySet()) =
        GestureConfig(kind = "tap", nTaps = nTaps, simultaneous = sim, waitFor = waitFor)

    @Test
    fun singleTapEmitsEnded() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(tap()), rec::emit)
        arbiter.pointerDown(0, 10.0, 10.0, 0.0)
        arbiter.pointerUp(0, 11.0, 10.0, 0.1)
        assertEquals(listOf<Any?>("ended"), rec.states(0))
        assertEquals(11.0, rec.events[0].second["x"])
    }

    @Test
    fun tapFailsWhenPointerTravels() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(tap()), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 50.0, 0.0, 0.05)
        arbiter.pointerUp(0, 50.0, 0.0, 0.1)
        assertTrue(rec.events.isEmpty())
    }

    @Test
    fun doubleTapNeedsTwoTapsInsideTheWindow() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(tap(nTaps = 2)), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerUp(0, 0.0, 0.0, 0.05)
        assertTrue(rec.events.isEmpty())
        arbiter.pointerDown(0, 0.0, 0.0, 0.2)
        arbiter.pointerUp(0, 0.0, 0.0, 0.25)
        assertEquals(listOf<Any?>("ended"), rec.states(0))
    }

    @Test
    fun exclusiveSingleTapWaitsForDoubleTapWindow() {
        // Exclusive(double_tap, single_tap): index 1 waits for index 0.
        val rec = Recorder()
        val specs = listOf(
            tap(nTaps = 2, sim = emptySet()),
            tap(nTaps = 1, sim = emptySet(), waitFor = setOf(0)),
        )
        val arbiter = GestureArbiter(specs, rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerUp(0, 0.0, 0.0, 0.05)
        // Single tap is buffered until the double-tap gap expires.
        assertTrue(rec.events.isEmpty())
        val deadline = arbiter.nextDeadline()
        assertTrue(deadline != null && deadline > 0.05)
        arbiter.poll(deadline!! + 0.001)
        assertEquals(listOf<Any?>("ended"), rec.states(1))
        assertTrue(rec.states(0).isEmpty())
    }

    @Test
    fun exclusiveDoubleTapSuppressesSingleTap() {
        val rec = Recorder()
        val specs = listOf(
            tap(nTaps = 2, sim = emptySet()),
            tap(nTaps = 1, sim = emptySet(), waitFor = setOf(0)),
        )
        val arbiter = GestureArbiter(specs, rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerUp(0, 0.0, 0.0, 0.05)
        arbiter.pointerDown(0, 0.0, 0.0, 0.15)
        arbiter.pointerUp(0, 0.0, 0.0, 0.2)
        assertEquals(listOf<Any?>("ended"), rec.states(0))
        assertTrue(rec.states(1).isEmpty())
    }

    @Test
    fun longPressActivatesOnPollAndEndsOnRelease() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(GestureConfig(kind = "long_press", minDurationMs = 500.0)), rec::emit)
        arbiter.pointerDown(0, 5.0, 5.0, 0.0)
        assertEquals(0.5, arbiter.nextDeadline()!!, 1e-9)
        arbiter.poll(0.3)
        assertTrue(rec.events.isEmpty())
        arbiter.poll(0.5)
        assertEquals(listOf<Any?>("began"), rec.states(0))
        arbiter.pointerUp(0, 5.0, 5.0, 0.7)
        assertEquals(listOf<Any?>("began", "ended"), rec.states(0))
    }

    @Test
    fun panReportsTranslationAndVelocity() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(GestureConfig(kind = "pan", minDistance = 10.0)), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 5.0, 0.0, 0.01)
        assertTrue(rec.events.isEmpty())
        arbiter.pointerMove(0, 20.0, 0.0, 0.02)
        assertEquals(listOf<Any?>("began"), rec.states(0))
        assertTrue(arbiter.hasActivePan())
        arbiter.pointerMove(0, 30.0, 5.0, 0.03)
        val changed = rec.events.last().second
        assertEquals("changed", changed["state"])
        assertEquals(10.0, changed["translation_x"] as Double, 1e-9)
        assertEquals(5.0, changed["translation_y"] as Double, 1e-9)
        assertTrue((changed["velocity_x"] as Double) > 0)
        arbiter.pointerUp(0, 40.0, 5.0, 0.04)
        val ended = rec.events.last().second
        assertEquals("ended", ended["state"])
        assertEquals(20.0, ended["translation_x"] as Double, 1e-9)
        assertFalse(arbiter.hasActivePan())
    }

    @Test
    fun raceLetsFirstActivationWin() {
        // Pan and long press not simultaneous: the pan activates first, long press never fires.
        val rec = Recorder()
        val specs = listOf(
            GestureConfig(kind = "pan", minDistance = 10.0, simultaneous = emptySet()),
            GestureConfig(kind = "long_press", minDurationMs = 500.0, simultaneous = emptySet()),
        )
        val arbiter = GestureArbiter(specs, rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 3.0, 0.0, 0.05)
        arbiter.pointerMove(0, 6.0, 0.0, 0.1)
        arbiter.pointerMove(0, 20.0, 0.0, 0.15)
        assertEquals(listOf<Any?>("began"), rec.states(0))
        arbiter.poll(0.6)
        assertTrue(rec.states(1).isEmpty())
    }

    @Test
    fun simultaneousGesturesBothRun() {
        val rec = Recorder()
        val specs = listOf(
            GestureConfig(kind = "pan", minDistance = 5.0, simultaneous = setOf(1)),
            GestureConfig(kind = "pinch", simultaneous = setOf(0)),
        )
        val arbiter = GestureArbiter(specs, rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerDown(1, 100.0, 0.0, 0.01)
        assertEquals(listOf<Any?>("began"), rec.states(1))
        arbiter.pointerMove(1, 120.0, 0.0, 0.02)
        assertEquals(listOf<Any?>("began"), rec.states(0))
        assertEquals(listOf<Any?>("began", "changed"), rec.states(1))
        assertEquals(1.2, rec.events.last().second["scale"] as Double, 1e-9)
    }

    @Test
    fun swipeResolvesDirectionAndVelocity() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(GestureConfig(kind = "swipe", direction = "right", minVelocity = 300.0)), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 50.0, 0.0, 0.05)
        arbiter.pointerUp(0, 100.0, 0.0, 0.1)
        val ended = rec.events.single().second
        assertEquals("ended", ended["state"])
        assertEquals("right", ended["direction"])
        assertEquals(1000.0, ended["velocity_x"] as Double, 1e-6)
    }

    @Test
    fun cancelAbortsActiveGestures() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(GestureConfig(kind = "pan", minDistance = 1.0)), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 10.0, 0.0, 0.01)
        arbiter.cancel(0.02)
        assertEquals(listOf<Any?>("began", "cancelled"), rec.states(0))
    }

    @Test
    fun decodesSerializedSpecs() {
        val specs = GestureArbiter.decodeSpecs(
            JSONArray("""[{"kind":"tap","n_taps":2,"simultaneous":[1],"wait_for":[]},{"kind":"pan","min_distance":4}]"""),
        )
        assertEquals(2, specs.size)
        assertEquals(2, specs[0].nTaps)
        assertEquals(setOf(1), specs[0].simultaneous)
        assertEquals(4.0, specs[1].minDistance!!, 0.0)
        assertEquals(null, specs[1].simultaneous)
        assertTrue(specs[0].enabled)
    }

    @Test
    fun decodesPanActivationFields() {
        val spec = GestureArbiter.decodeSpec(
            JSONObject("""{"kind":"pan","enabled":true,"min_distance":null,"min_pointers":1,"max_pointers":2,
                "active_offset_x":[-20,20],"active_offset_y":null,"fail_offset_x":null,"fail_offset_y":[null,15],"min_velocity":null}"""),
        )
        assertNull(spec.minDistance)
        assertEquals(2, spec.maxPointers)
        assertEquals(Offset(-20.0, 20.0), spec.activeOffsetX)
        assertNull(spec.activeOffsetY)
        assertEquals(Offset(null, 15.0), spec.failOffsetY)
        assertNull(spec.minVelocity)
        // A pan without any criteria keeps the 10dp default and no velocity rule; swipes keep 300 dp/s.
        val plain = GestureArbiter.decodeSpec(JSONObject("""{"kind":"pan"}"""))
        assertEquals(10.0, plain.minDistance!!, 0.0)
        assertNull(plain.minVelocity)
        assertNull(plain.maxPointers)
        val swipe = GestureArbiter.decodeSpec(JSONObject("""{"kind":"swipe","direction":"left"}"""))
        assertEquals(300.0, swipe.minVelocity!!, 0.0)
        assertEquals("left", swipe.direction)
        assertNull(GestureArbiter.decodeSpec(JSONObject("""{"kind":"swipe","direction":null}""")).direction)
        assertNull(GestureArbiter.decodeSpec(JSONObject("""{"kind":"swipe"}""")).direction)
        // One-sided numeric offsets.
        assertEquals(Offset(null, 5.0), GestureArbiter.offset(5))
        assertEquals(Offset(-5.0, null), GestureArbiter.offset(-5))
        assertFalse(GestureArbiter.decodeSpec(JSONObject("""{"kind":"tap","enabled":false}""")).enabled)
    }

    @Test
    fun panActivationRules() {
        val offsets = GestureConfig(kind = "pan", minDistance = null, minVelocity = null, activeOffsetX = Offset(-20.0, 20.0), failOffsetY = Offset(-15.0, 15.0))
        // Failing wins over activating; crossing is strict.
        assertEquals(PanRecognizer.Verdict.FAIL, PanRecognizer.activation(offsets, 30.0, 16.0, 0.0))
        assertEquals(PanRecognizer.Verdict.FAIL, PanRecognizer.activation(offsets, 0.0, -15.5, 0.0))
        assertEquals(PanRecognizer.Verdict.WAIT, PanRecognizer.activation(offsets, 20.0, 15.0, 0.0))
        assertEquals(PanRecognizer.Verdict.ACTIVATE, PanRecognizer.activation(offsets, 20.5, 0.0, 0.0))
        assertEquals(PanRecognizer.Verdict.ACTIVATE, PanRecognizer.activation(offsets, -21.0, 14.0, 0.0))
        // Distance only when set; velocity only when set.
        val distance = GestureConfig(kind = "pan", minDistance = 10.0, minVelocity = null)
        assertEquals(PanRecognizer.Verdict.WAIT, PanRecognizer.activation(distance, 6.0, 6.0, 5000.0))
        assertEquals(PanRecognizer.Verdict.ACTIVATE, PanRecognizer.activation(distance, 8.0, 6.0, 0.0))
        val velocity = GestureConfig(kind = "pan", minDistance = null, minVelocity = 400.0)
        assertEquals(PanRecognizer.Verdict.WAIT, PanRecognizer.activation(velocity, 100.0, 100.0, 399.0))
        assertEquals(PanRecognizer.Verdict.ACTIVATE, PanRecognizer.activation(velocity, 1.0, 0.0, 400.0))
        // One-sided offsets ignore the unbounded direction.
        val oneSided = GestureConfig(kind = "pan", minDistance = null, minVelocity = null, activeOffsetY = Offset(null, 10.0))
        assertEquals(PanRecognizer.Verdict.WAIT, PanRecognizer.activation(oneSided, 0.0, -500.0, 0.0))
        assertEquals(PanRecognizer.Verdict.ACTIVATE, PanRecognizer.activation(oneSided, 0.0, 10.5, 0.0))
    }

    @Test
    fun panWithFailOffsetFailsForTheInteraction() {
        val rec = Recorder()
        val config = GestureConfig(kind = "pan", minDistance = null, minVelocity = null, activeOffsetX = Offset(-20.0, 20.0), failOffsetY = Offset(-15.0, 15.0))
        val arbiter = GestureArbiter(listOf(config), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 5.0, 20.0, 0.01)
        arbiter.pointerMove(0, 40.0, 20.0, 0.02)
        arbiter.pointerUp(0, 40.0, 20.0, 0.03)
        assertTrue(rec.events.isEmpty())
        // A fresh touch starts over and activates horizontally.
        arbiter.pointerDown(0, 0.0, 0.0, 1.0)
        arbiter.pointerMove(0, 25.0, 2.0, 1.01)
        assertEquals(listOf<Any?>("began"), rec.states(0))
    }

    @Test
    fun exceedingMaxPointersFailsOrCancelsThePan() {
        val rec = Recorder()
        val config = GestureConfig(kind = "pan", minDistance = 5.0, minVelocity = null, maxPointers = 1)
        val arbiter = GestureArbiter(listOf(config), rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerMove(0, 10.0, 0.0, 0.01)
        assertEquals(listOf<Any?>("began"), rec.states(0))
        arbiter.pointerDown(1, 50.0, 0.0, 0.02)
        assertEquals(listOf<Any?>("began", "cancelled"), rec.states(0))
        // Inactive pan: a second pointer fails it silently.
        val rec2 = Recorder()
        val arbiter2 = GestureArbiter(listOf(config), rec2::emit)
        arbiter2.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter2.pointerDown(1, 50.0, 0.0, 0.01)
        arbiter2.pointerMove(0, 30.0, 0.0, 0.02)
        arbiter2.pointerMove(1, 80.0, 0.0, 0.02)
        assertTrue(rec2.events.isEmpty())
    }

    @Test
    fun disabledSpecsKeepTheirIndex() {
        val rec = Recorder()
        val specs = listOf(tap().copy(enabled = false), GestureConfig(kind = "pan", minDistance = 5.0, minVelocity = null))
        val arbiter = GestureArbiter(specs, rec::emit)
        arbiter.pointerDown(0, 0.0, 0.0, 0.0)
        arbiter.pointerUp(0, 0.0, 0.0, 0.05)
        assertTrue(rec.states(0).isEmpty())
        arbiter.pointerDown(0, 0.0, 0.0, 1.0)
        arbiter.pointerMove(0, 10.0, 0.0, 1.01)
        assertEquals(listOf<Any?>("began"), rec.states(1))
    }

    @Test
    fun positionedPayloadsCarryWindowCoordinates() {
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(tap()), rec::emit)
        arbiter.pointerDown(0, 10.0, 10.0, 0.0, absX = 110.0, absY = 210.0)
        arbiter.pointerUp(0, 11.0, 10.0, 0.1, absX = 111.0, absY = 210.0)
        val ended = rec.events.single().second
        assertEquals(11.0, ended["x"])
        assertEquals(111.0, ended["absolute_x"])
        assertEquals(210.0, ended["absolute_y"])
    }

    @Test
    fun panWithOffsetsActivatesOnAHorizontalSwipeFromTheWire() {
        // The exact spec Python sends for the e2e pan demo.
        val spec = org.json.JSONObject(
            """{"kind":"pan","enabled":true,"min_distance":null,"min_pointers":1,"max_pointers":1,
               "active_offset_x":[-20.0,20.0],"active_offset_y":null,"fail_offset_x":null,
               "fail_offset_y":[-40.0,40.0],"min_velocity":null,"simultaneous":[],"wait_for":[]}"""
        )
        val rec = Recorder()
        val arbiter = GestureArbiter(listOf(GestureArbiter.decodeSpec(spec)), rec::emit)
        arbiter.pointerDown(0, 180.0, 60.0, 0.0)
        var x = 180.0
        var t = 0.0
        while (x > 20.0) {
            x -= 12.0
            t += 0.016
            arbiter.pointerMove(0, x, 60.0, t)
        }
        arbiter.pointerUp(0, x, 60.0, t + 0.016)
        assertEquals(listOf("began", "changed"), rec.states(0).take(2))
        assertEquals("ended", rec.states(0).last())
    }
}
