package com.pythonnative.runtime.gestures

import android.annotation.SuppressLint
import android.os.Build
import android.view.MotionEvent
import android.view.View
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.components.ViewStyler
import com.pythonnative.runtime.core.PNCore
import org.json.JSONArray
import kotlin.math.max

/**
 * Forwards `MotionEvent`s on views with `gestures` to the core's gesture
 * engine (`pn_core_pointer`), which recognizes them and emits
 * `gesture:<index>` events. Time-based recognizers (long press, multi-tap
 * windows) are polled with the main `Handler` at the engine's next
 * deadline. While a pan is active the parent is asked not to intercept, so
 * an enclosing scroll view can't steal the drag.
 */
object TouchForwarder {
    private const val KEY_BOUND = "gestures_bound"
    private const val KEY_POLL_DEADLINE = "poll_deadline"
    private const val KEY_POLL_TOKEN = "poll_token"
    private const val FIELDS = 7

    /** Install the touch stream for `record` when its `gestures` prop is non-empty. */
    fun bind(record: ViewRecord) {
        val specs = record.props.opt("gestures") as? JSONArray
        if (specs == null || specs.length() == 0 || record.state[KEY_BOUND] == true) return
        record.state[KEY_BOUND] = true
        listen(record.view)
    }

    /** Drop any pending poll for `record`. */
    fun unbind(record: ViewRecord) {
        record.state[KEY_POLL_DEADLINE] = null
        record.state[KEY_POLL_TOKEN] = ((record.state[KEY_POLL_TOKEN] as? Int) ?: 0) + 1
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun listen(view: View) {
        view.setOnTouchListener { v, event ->
            if (ViewStyler.pointerEventsBlocked(v)) return@setOnTouchListener false
            feed(v, event)
        }
    }

    /** For managers that own their own touch listener (Pressable). */
    fun feed(view: View, event: MotionEvent): Boolean {
        val record = PNBridge.registry.recordFor(view) ?: return false
        return feed(record, event)
    }

    /**
     * Forward one `MotionEvent`. Returns `true` while the view has gestures
     * (to keep receiving the stream), `false` when there is nothing to feed.
     */
    fun feed(record: ViewRecord, event: MotionEvent): Boolean {
        if (!PNCore.hasGestures(record.tag)) return false
        try {
            val (values, count) = pack(event, PNBridge.density())
            if (PNCore.pointer(record.tag, values, count)) record.view.parent?.requestDisallowInterceptTouchEvent(true)
            schedulePoll(record)
        } catch (error: Exception) {
            PNLog.rateLimited("gesture-feed", "gesture feed failed", error)
        }
        return true
    }

    /** Pack `event` as `(phase, pointer, x, y, windowX, windowY, seconds)` rows in dp. */
    fun pack(event: MotionEvent, density: Float): Pair<DoubleArray, Int> {
        val time = event.eventTime / 1000.0
        val pointers = when (event.actionMasked) {
            MotionEvent.ACTION_MOVE, MotionEvent.ACTION_CANCEL -> (0 until event.pointerCount).toList()
            else -> listOf(event.actionIndex)
        }
        val phase = when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> 0
            MotionEvent.ACTION_MOVE -> 1
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> 2
            MotionEvent.ACTION_CANCEL -> 3
            else -> return DoubleArray(0) to 0
        }
        val values = DoubleArray(pointers.size * FIELDS)
        for ((row, index) in pointers.withIndex()) {
            val base = row * FIELDS
            values[base] = phase.toDouble()
            values[base + 1] = event.getPointerId(index).toDouble()
            values[base + 2] = (event.getX(index) / density).toDouble()
            values[base + 3] = (event.getY(index) / density).toDouble()
            values[base + 4] = rawX(event, index) / density
            values[base + 5] = rawY(event, index) / density
            values[base + 6] = time
        }
        return values to pointers.size
    }

    /** Window x of pointer `index` in px (per-pointer raw coordinates need API 29; older releases offset from pointer 0). */
    private fun rawX(event: MotionEvent, index: Int): Double =
        if (Build.VERSION.SDK_INT >= 29) event.getRawX(index).toDouble()
        else (event.rawX - event.getX(0) + event.getX(index)).toDouble()

    private fun rawY(event: MotionEvent, index: Int): Double =
        if (Build.VERSION.SDK_INT >= 29) event.getRawY(index).toDouble()
        else (event.rawY - event.getY(0) + event.getY(index)).toDouble()

    private fun schedulePoll(record: ViewRecord) {
        val state = record.state
        val deadline = PNCore.gestureDeadline(record.tag)
        if (deadline < 0) return
        val pending = state[KEY_POLL_DEADLINE] as? Double
        if (pending != null && pending <= deadline + 0.001) return
        val delayMs = max(1L, ((deadline - PNCore.now()) * 1000.0).toLong())
        val token = ((state[KEY_POLL_TOKEN] as? Int) ?: 0) + 1
        state[KEY_POLL_TOKEN] = token
        state[KEY_POLL_DEADLINE] = deadline
        MainThread.postDelayed({
            if (state[KEY_POLL_TOKEN] != token) return@postDelayed
            state[KEY_POLL_DEADLINE] = null
            if (PNBridge.registry.get(record.tag) !== record) return@postDelayed
            PNCore.gesturePoll(record.tag, PNCore.now())
            schedulePoll(record)
        }, delayMs)
    }
}
