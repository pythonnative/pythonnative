package com.pythonnative.runtime

import com.pythonnative.runtime.gestures.GestureArbiter
import com.pythonnative.runtime.gestures.GestureConfig
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
        assertEquals(4.0, specs[1].minDistance, 0.0)
        assertEquals(null, specs[1].simultaneous)
    }
}
