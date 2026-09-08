package com.pythonnative.runtime.gestures

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.hypot
import kotlin.math.max

/** Gesture states reported on event payloads. */
object GestureState {
    const val BEGAN = "began"
    const val CHANGED = "changed"
    const val ENDED = "ended"
    const val CANCELLED = "cancelled"

    /** Internal verdict used by recognizers to tell the arbiter they cannot succeed. */
    const val FAILED = "__failed"
}

/** A pointer position in the view's coordinate space, in dp. */
data class Point(val x: Double, val y: Double)

/** Output channel of recognizers and the arbiter: `(gesture_index, payload)`. */
typealias EmitFn = (Int, Map<String, Any?>) -> Unit

/** Configuration for one leaf gesture, decoded from the serialized `gestures` prop. */
data class GestureConfig(
    val kind: String,
    val nTaps: Int = 1,
    val maxDistance: Double = 12.0,
    val minDurationMs: Double = 500.0,
    val minDistance: Double = 10.0,
    val minPointers: Int = 1,
    val direction: String = "any",
    val minVelocity: Double = 300.0,
    val nPointers: Int = 1,
    /** Indices this gesture may be active alongside; `null` means everything. */
    val simultaneous: Set<Int>? = null,
    /** Indices that must fail before this gesture may activate. */
    val waitFor: Set<Int> = emptySet(),
)

/** Estimate pointer velocity from recent samples (dp per second). */
class VelocityEstimator {
    private data class Sample(val x: Double, val y: Double, val t: Double)

    private val samples = ArrayList<Sample>()

    fun add(x: Double, y: Double, t: Double) {
        samples.add(Sample(x, y, t))
        val cutoff = t - WINDOW_S
        while (samples.size > 2 && samples[0].t < cutoff) samples.removeAt(0)
    }

    fun velocity(): Point {
        if (samples.size < 2) return Point(0.0, 0.0)
        val first = samples.first()
        val last = samples.last()
        val dt = last.t - first.t
        if (dt <= 1e-6) return Point(0.0, 0.0)
        return Point((last.x - first.x) / dt, (last.y - first.y) / dt)
    }

    fun reset() = samples.clear()

    private companion object {
        const val WINDOW_S = 0.1
    }
}

internal fun centroid(pointers: Map<Int, Point>): Point {
    if (pointers.isEmpty()) return Point(0.0, 0.0)
    var xs = 0.0
    var ys = 0.0
    for (p in pointers.values) {
        xs += p.x
        ys += p.y
    }
    return Point(xs / pointers.size, ys / pointers.size)
}

/** Base class for one gesture's state machine. `pointers` maps pointer id to position. */
abstract class Recognizer(val index: Int, val config: GestureConfig, private val emitFn: EmitFn) {
    protected fun emit(state: String, vararg fields: Pair<String, Any?>) {
        val payload = LinkedHashMap<String, Any?>()
        payload["kind"] = config.kind
        payload["state"] = state
        for ((k, v) in fields) payload[k] = v
        emitFn(index, payload)
    }

    /** Report that this gesture can no longer succeed this interaction. */
    protected fun fail() {
        emitFn(index, mapOf("kind" to config.kind, "state" to GestureState.FAILED))
    }

    /** Abandon recognition without emitting anything (lost a race). */
    open fun forceFail(t: Double) = cancel(t)

    open fun down(pointers: Map<Int, Point>, t: Double) {}
    open fun move(pointers: Map<Int, Point>, t: Double) {}
    open fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {}
    open fun cancel(t: Double) {}

    /** Next time `poll` should run, or `null`. */
    open fun deadline(): Double? = null
    open fun poll(t: Double) {}

    companion object {
        /** Build the recognizer for `config.kind`, or `null` for unknown kinds. */
        fun create(index: Int, config: GestureConfig, emit: EmitFn): Recognizer? = when (config.kind) {
            "tap" -> TapRecognizer(index, config, emit)
            "long_press" -> LongPressRecognizer(index, config, emit)
            "pan" -> PanRecognizer(index, config, emit)
            "swipe", "fling" -> SwipeRecognizer(index, config, emit)
            "pinch" -> PinchRecognizer(index, config, emit)
            "rotation" -> RotationRecognizer(index, config, emit)
            else -> null
        }
    }
}

class TapRecognizer(index: Int, config: GestureConfig, emit: EmitFn) : Recognizer(index, config, emit) {
    private val nTaps = max(1, config.nTaps)
    private val slop = config.maxDistance
    private var downPos: Point? = null
    private var downTime = 0.0
    private var tapCount = 0
    private var lastTapTime = 0.0
    private var failed = false
    private var gapDeadline: Double? = null

    override fun down(pointers: Map<Int, Point>, t: Double) {
        if (pointers.size != 1) {
            if (!failed) {
                failed = true
                fail()
            }
            return
        }
        if (tapCount > 0 && t - lastTapTime > MULTI_TAP_GAP_S) tapCount = 0
        failed = false
        gapDeadline = null
        downPos = centroid(pointers)
        downTime = t
    }

    override fun move(pointers: Map<Int, Point>, t: Double) {
        val origin = downPos ?: return
        if (failed) return
        val c = centroid(pointers)
        if (hypot(c.x - origin.x, c.y - origin.y) > slop) {
            failed = true
            fail()
        }
    }

    override fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {
        if (failed || downPos == null) {
            reset()
            return
        }
        if (t - downTime > MAX_TAP_DURATION_S) {
            reset()
            fail()
            return
        }
        tapCount += 1
        lastTapTime = t
        if (tapCount >= nTaps) {
            emit(GestureState.ENDED, "x" to x, "y" to y)
            reset()
        } else {
            gapDeadline = t + MULTI_TAP_GAP_S
        }
        downPos = null
    }

    override fun cancel(t: Double) = reset()

    override fun deadline(): Double? = gapDeadline

    override fun poll(t: Double) {
        val d = gapDeadline ?: return
        if (t >= d) {
            gapDeadline = null
            tapCount = 0
            fail()
        }
    }

    private fun reset() {
        downPos = null
        if (tapCount >= nTaps) tapCount = 0
        failed = false
        gapDeadline = null
    }

    private companion object {
        const val MAX_TAP_DURATION_S = 0.4
        const val MULTI_TAP_GAP_S = 0.3
    }
}

class LongPressRecognizer(index: Int, config: GestureConfig, emit: EmitFn) : Recognizer(index, config, emit) {
    private val durationS = config.minDurationMs / 1000.0
    private val slop = config.maxDistance
    private var downPos: Point? = null
    private var pressDeadline: Double? = null
    private var active = false

    override fun down(pointers: Map<Int, Point>, t: Double) {
        downPos = centroid(pointers)
        pressDeadline = t + durationS
        active = false
    }

    override fun move(pointers: Map<Int, Point>, t: Double) {
        val origin = downPos ?: return
        val c = centroid(pointers)
        if (hypot(c.x - origin.x, c.y - origin.y) > slop) {
            if (active) emit(GestureState.CANCELLED, "x" to c.x, "y" to c.y)
            reset()
            fail()
        }
    }

    override fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {
        if (active) {
            emit(GestureState.ENDED, "x" to x, "y" to y)
        } else if (downPos != null) {
            fail()
        }
        reset()
    }

    override fun cancel(t: Double) {
        if (active) emit(GestureState.CANCELLED)
        reset()
    }

    override fun deadline(): Double? = pressDeadline

    override fun poll(t: Double) {
        val d = pressDeadline ?: return
        val origin = downPos ?: return
        if (active) return
        if (t >= d) {
            active = true
            pressDeadline = null
            emit(GestureState.BEGAN, "x" to origin.x, "y" to origin.y)
        }
    }

    private fun reset() {
        downPos = null
        pressDeadline = null
        active = false
    }
}

class PanRecognizer(index: Int, config: GestureConfig, emit: EmitFn) : Recognizer(index, config, emit) {
    private val minDistance = config.minDistance
    private val minPointers = max(1, config.minPointers)
    private var origin: Point? = null
    private var anchor: Point? = null
    private val velocity = VelocityEstimator()
    private var lastTranslation = Point(0.0, 0.0)

    /** Whether the pan has activated (hosts use this to block parent interception). */
    var active = false
        private set

    override fun down(pointers: Map<Int, Point>, t: Double) {
        if (pointers.size < minPointers) return
        if (origin == null) {
            val c = centroid(pointers)
            origin = c
            velocity.reset()
            velocity.add(c.x, c.y, t)
        } else {
            rebase(pointers)
        }
    }

    override fun move(pointers: Map<Int, Point>, t: Double) {
        val o = origin ?: return
        if (pointers.size < minPointers) return
        val c = centroid(pointers)
        velocity.add(c.x, c.y, t)
        if (!active) {
            if (hypot(c.x - o.x, c.y - o.y) < minDistance) return
            active = true
            anchor = c
            emit(GestureState.BEGAN, "x" to c.x, "y" to c.y, "pointer_count" to pointers.size)
            return
        }
        val a = anchor ?: return
        val v = velocity.velocity()
        lastTranslation = Point(c.x - a.x, c.y - a.y)
        emit(
            GestureState.CHANGED,
            "x" to c.x,
            "y" to c.y,
            "translation_x" to lastTranslation.x,
            "translation_y" to lastTranslation.y,
            "velocity_x" to v.x,
            "velocity_y" to v.y,
            "pointer_count" to pointers.size,
        )
    }

    override fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {
        if (active && pointers.size < minPointers) {
            val v = velocity.velocity()
            val a = anchor ?: Point(x, y)
            emit(
                GestureState.ENDED,
                "x" to x,
                "y" to y,
                "translation_x" to x - a.x,
                "translation_y" to y - a.y,
                "velocity_x" to v.x,
                "velocity_y" to v.y,
                "pointer_count" to pointers.size,
            )
            reset()
        } else if (pointers.isEmpty()) {
            if (!active && origin != null) fail()
            reset()
        } else if (active) {
            rebase(pointers)
        }
    }

    override fun cancel(t: Double) {
        if (active) emit(GestureState.CANCELLED)
        reset()
    }

    private fun rebase(pointers: Map<Int, Point>) {
        val a = anchor
        if (!active || a == null) {
            origin = centroid(pointers)
            return
        }
        val c = centroid(pointers)
        anchor = Point(c.x - lastTranslation.x, c.y - lastTranslation.y)
    }

    private fun reset() {
        origin = null
        anchor = null
        active = false
        velocity.reset()
        lastTranslation = Point(0.0, 0.0)
    }
}

/** Directional flick recognizer; also serves `fling` (adds a pointer-count requirement). */
class SwipeRecognizer(index: Int, config: GestureConfig, emit: EmitFn) : Recognizer(index, config, emit) {
    private val direction = config.direction
    private val minVelocity = config.minVelocity
    private val nPointers = max(1, config.nPointers)
    private val velocity = VelocityEstimator()
    private var tracking = false
    private var maxPointers = 0

    override fun down(pointers: Map<Int, Point>, t: Double) {
        if (!tracking) {
            velocity.reset()
            tracking = true
            maxPointers = 0
        }
        maxPointers = max(maxPointers, pointers.size)
        val c = centroid(pointers)
        velocity.add(c.x, c.y, t)
    }

    override fun move(pointers: Map<Int, Point>, t: Double) {
        if (!tracking) return
        maxPointers = max(maxPointers, pointers.size)
        val c = centroid(pointers)
        velocity.add(c.x, c.y, t)
    }

    override fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {
        if (!tracking || pointers.isNotEmpty()) return
        tracking = false
        velocity.add(x, y, t)
        val v = velocity.velocity()
        val speed = hypot(v.x, v.y)
        if (speed < minVelocity || maxPointers < nPointers) {
            fail()
            return
        }
        val resolved = if (abs(v.x) >= abs(v.y)) {
            if (v.x > 0) "right" else "left"
        } else {
            if (v.y > 0) "down" else "up"
        }
        if (direction != "any" && direction != resolved) {
            fail()
            return
        }
        emit(
            GestureState.ENDED,
            "x" to x,
            "y" to y,
            "velocity_x" to v.x,
            "velocity_y" to v.y,
            "direction" to resolved,
            "pointer_count" to maxPointers,
        )
    }

    override fun cancel(t: Double) {
        tracking = false
        maxPointers = 0
        velocity.reset()
    }
}

class PinchRecognizer(index: Int, config: GestureConfig, emit: EmitFn) : Recognizer(index, config, emit) {
    private var initial: Double? = null
    private var active = false
    private var scale = 1.0

    private fun span(pointers: Map<Int, Point>): Double? {
        if (pointers.size < 2) return null
        val pts = pointers.values.take(2)
        return hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y)
    }

    override fun down(pointers: Map<Int, Point>, t: Double) {
        val s = span(pointers)
        if (s != null && s > 0 && initial == null) {
            initial = s
            active = true
            val c = centroid(pointers)
            emit(GestureState.BEGAN, "x" to c.x, "y" to c.y, "scale" to 1.0, "pointer_count" to pointers.size)
        }
    }

    override fun move(pointers: Map<Int, Point>, t: Double) {
        val i = initial ?: return
        if (!active) return
        val s = span(pointers) ?: return
        if (s <= 0) return
        scale = s / i
        val c = centroid(pointers)
        emit(GestureState.CHANGED, "x" to c.x, "y" to c.y, "scale" to scale, "pointer_count" to pointers.size)
    }

    override fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {
        if (active && pointers.size < 2) {
            emit(GestureState.ENDED, "x" to x, "y" to y, "scale" to scale, "pointer_count" to pointers.size)
            reset()
        } else if (!active && pointers.isEmpty()) {
            fail()
        }
    }

    override fun cancel(t: Double) {
        if (active) emit(GestureState.CANCELLED, "scale" to scale)
        reset()
    }

    private fun reset() {
        initial = null
        active = false
        scale = 1.0
    }
}

class RotationRecognizer(index: Int, config: GestureConfig, emit: EmitFn) : Recognizer(index, config, emit) {
    private var initial: Double? = null
    private var active = false
    private var rotation = 0.0

    private fun angle(pointers: Map<Int, Point>): Double? {
        if (pointers.size < 2) return null
        val pts = pointers.values.take(2)
        return atan2(pts[1].y - pts[0].y, pts[1].x - pts[0].x)
    }

    override fun down(pointers: Map<Int, Point>, t: Double) {
        val a = angle(pointers)
        if (a != null && initial == null) {
            initial = a
            active = true
            val c = centroid(pointers)
            emit(GestureState.BEGAN, "x" to c.x, "y" to c.y, "rotation" to 0.0, "pointer_count" to pointers.size)
        }
    }

    override fun move(pointers: Map<Int, Point>, t: Double) {
        val i = initial ?: return
        if (!active) return
        val a = angle(pointers) ?: return
        var delta = a - i
        while (delta > Math.PI) delta -= 2 * Math.PI
        while (delta < -Math.PI) delta += 2 * Math.PI
        rotation = delta
        val c = centroid(pointers)
        emit(GestureState.CHANGED, "x" to c.x, "y" to c.y, "rotation" to rotation, "pointer_count" to pointers.size)
    }

    override fun up(pointers: Map<Int, Point>, t: Double, x: Double, y: Double) {
        if (active && pointers.size < 2) {
            emit(GestureState.ENDED, "x" to x, "y" to y, "rotation" to rotation, "pointer_count" to pointers.size)
            reset()
        } else if (!active && pointers.isEmpty()) {
            fail()
        }
    }

    override fun cancel(t: Double) {
        if (active) emit(GestureState.CANCELLED, "rotation" to rotation)
        reset()
    }

    private fun reset() {
        initial = null
        active = false
        rotation = 0.0
    }
}
