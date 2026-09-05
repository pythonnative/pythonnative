package com.pythonnative.runtime.gestures

import org.json.JSONArray
import org.json.JSONObject

/**
 * Turn a raw pointer-event stream into arbitrated gesture payloads.
 *
 * One arbiter serves one view. Positions are in the view's coordinate
 * space (dp); times are seconds on any monotonic clock. Beyond running
 * each gesture's state machine, the arbiter enforces the relationships
 * serialized by Python:
 *
 * - Two gestures not in each other's `simultaneous` sets race; when
 *   one activates, the other is force-failed for the interaction.
 * - A gesture with a `wait_for` set may only activate after all of
 *   those gestures have failed; its output is buffered meanwhile and
 *   either flushed or discarded.
 *
 * This class is plain Kotlin (no Android types) so it is unit-testable
 * with scripted pointer sequences.
 */
class GestureArbiter(specs: List<GestureConfig>, private val emitOut: EmitFn) {
    private enum class State { POSSIBLE, WAITING, ACTIVE, DONE, FAILED }

    private val pointers = LinkedHashMap<Int, Point>()
    private val recognizers = ArrayList<Recognizer>()
    private val indices = ArrayList<Int>()
    private val sim = HashMap<Int, Set<Int>?>()
    private val waitFor = HashMap<Int, Set<Int>>()
    private val states = HashMap<Int, State>()
    private val buffers = HashMap<Int, ArrayList<Map<String, Any?>>>()
    private var lastT = 0.0

    init {
        specs.forEachIndexed { i, spec ->
            val recognizer = Recognizer.create(i, spec) { index, payload -> mediate(index, payload) } ?: return@forEachIndexed
            recognizers.add(recognizer)
            indices.add(i)
            sim[i] = spec.simultaneous
            waitFor[i] = spec.waitFor
            states[i] = State.POSSIBLE
        }
    }

    // -- pointer input ---------------------------------------------------

    /** Record a pointer press and advance every recognizer. */
    fun pointerDown(pointerId: Int, x: Double, y: Double, t: Double) {
        lastT = t
        if (pointers.isEmpty() && states.values.none { it == State.WAITING }) {
            for (i in indices) states[i] = State.POSSIBLE
            buffers.clear()
        }
        pointers[pointerId] = Point(x, y)
        for (r in recognizers) r.down(pointers, t)
    }

    /** Record pointer travel and advance every recognizer. */
    fun pointerMove(pointerId: Int, x: Double, y: Double, t: Double) {
        lastT = t
        if (!pointers.containsKey(pointerId)) return
        pointers[pointerId] = Point(x, y)
        for (r in recognizers) r.move(pointers, t)
    }

    /** Record a pointer release and advance every recognizer. */
    fun pointerUp(pointerId: Int, x: Double, y: Double, t: Double) {
        lastT = t
        pointers.remove(pointerId)
        for (r in recognizers) r.up(pointers, t, x, y)
    }

    /** Abort every in-flight gesture (for example, touch stolen by a scroll parent). */
    fun cancel(t: Double) {
        lastT = t
        pointers.clear()
        buffers.clear()
        for (i in indices) if (states[i] == State.WAITING) states[i] = State.FAILED
        for (r in recognizers) r.cancel(t)
    }

    /** Advance time-based recognizers (long press, multi-tap windows). */
    fun poll(t: Double) {
        lastT = t
        for (r in recognizers) r.poll(t)
    }

    /** Earliest time [poll] should be called, or `null`. */
    fun nextDeadline(): Double? = recognizers.mapNotNull { it.deadline() }.minOrNull()

    /** Whether a pan gesture is currently activated. */
    fun hasActivePan(): Boolean = recognizers.any { it is PanRecognizer && it.active }

    // -- arbitration -------------------------------------------------------

    private fun recognizerFor(index: Int): Recognizer? = recognizers.firstOrNull { it.index == index }

    private fun isSimultaneous(a: Int, b: Int): Boolean {
        val simA = sim[a] ?: return true
        val simB = sim[b] ?: return true
        return b in simA && a in simB
    }

    private fun mediate(index: Int, payload: Map<String, Any?>) {
        val state = payload["state"]
        val current = states[index] ?: State.POSSIBLE
        if (state == GestureState.FAILED) {
            if (current == State.POSSIBLE || current == State.WAITING) setFailed(index)
            return
        }
        when (current) {
            State.FAILED -> return
            State.ACTIVE -> {
                emitOut(index, payload)
                if (state == GestureState.ENDED) {
                    states[index] = State.DONE
                    onResolved(index, succeeded = true)
                } else if (state == GestureState.CANCELLED) {
                    states[index] = State.FAILED
                    onResolved(index, succeeded = false)
                }
            }
            State.WAITING -> buffers.getOrPut(index) { ArrayList() }.add(payload)
            State.DONE -> {}
            State.POSSIBLE -> requestActivation(index, payload)
        }
    }

    private fun requestActivation(index: Int, payload: Map<String, Any?>) {
        for (j in indices) {
            if (j == index) continue
            val s = states[j]
            if ((s == State.ACTIVE || s == State.DONE) && !isSimultaneous(index, j)) {
                setFailed(index)
                return
            }
        }
        val targets = (waitFor[index] ?: emptySet()).filter { states.containsKey(it) }
        if (targets.any { states[it] == State.ACTIVE || states[it] == State.DONE }) {
            setFailed(index)
            return
        }
        if (targets.any { states[it] == State.POSSIBLE || states[it] == State.WAITING }) {
            states[index] = State.WAITING
            buffers.getOrPut(index) { ArrayList() }.add(payload)
            return
        }
        activate(index, listOf(payload))
    }

    private fun activate(index: Int, payloads: List<Map<String, Any?>>) {
        val last = payloads.lastOrNull()?.get("state")
        val discreteDone = last == GestureState.ENDED || last == GestureState.CANCELLED
        states[index] = if (discreteDone) State.DONE else State.ACTIVE
        for (j in indices) {
            if (j == index) continue
            val s = states[j]
            if ((s == State.POSSIBLE || s == State.WAITING) && !isSimultaneous(index, j)) {
                recognizerFor(j)?.forceFail(lastT)
                setFailed(j)
            }
        }
        for (p in payloads) emitOut(index, p)
        if (states[index] == State.DONE) onResolved(index, succeeded = true)
    }

    private fun setFailed(index: Int) {
        if (states[index] == State.FAILED) return
        states[index] = State.FAILED
        buffers.remove(index)
        onResolved(index, succeeded = false)
    }

    private fun onResolved(index: Int, succeeded: Boolean) {
        for (waiter in indices) {
            if (states[waiter] != State.WAITING) continue
            val wf = waitFor[waiter] ?: emptySet()
            if (index !in wf) continue
            if (succeeded) {
                recognizerFor(waiter)?.forceFail(lastT)
                setFailed(waiter)
                continue
            }
            val targets = wf.filter { states.containsKey(it) }
            if (targets.any { states[it] == State.POSSIBLE || states[it] == State.WAITING }) continue
            if (targets.any { states[it] == State.ACTIVE || states[it] == State.DONE }) {
                recognizerFor(waiter)?.forceFail(lastT)
                setFailed(waiter)
                continue
            }
            val payloads = buffers.remove(waiter) ?: ArrayList()
            states[waiter] = State.POSSIBLE
            activate(waiter, payloads)
        }
    }

    companion object {
        /** Decode the serialized `gestures` prop (a JSON array of spec objects). */
        fun decodeSpecs(specs: JSONArray?): List<GestureConfig> {
            if (specs == null) return emptyList()
            val out = ArrayList<GestureConfig>(specs.length())
            for (i in 0 until specs.length()) {
                val spec = specs.optJSONObject(i)
                out.add(if (spec == null) GestureConfig(kind = "") else decodeSpec(spec))
            }
            return out
        }

        /** Decode one spec object. */
        fun decodeSpec(spec: JSONObject): GestureConfig {
            return GestureConfig(
                kind = spec.optString("kind", ""),
                nTaps = spec.optInt("n_taps", 1),
                maxDistance = spec.optDouble("max_distance", 12.0),
                minDurationMs = spec.optDouble("min_duration_ms", 500.0),
                minDistance = spec.optDouble("min_distance", 10.0),
                minPointers = spec.optInt("min_pointers", 1),
                direction = spec.optString("direction", "any"),
                minVelocity = spec.optDouble("min_velocity", 300.0),
                nPointers = spec.optInt("n_pointers", 1),
                simultaneous = spec.optJSONArray("simultaneous")?.let { intSet(it) },
                waitFor = spec.optJSONArray("wait_for")?.let { intSet(it) } ?: emptySet(),
            )
        }

        private fun intSet(array: JSONArray): Set<Int> {
            val out = HashSet<Int>()
            for (i in 0 until array.length()) out.add(array.optInt(i))
            return out
        }
    }
}
