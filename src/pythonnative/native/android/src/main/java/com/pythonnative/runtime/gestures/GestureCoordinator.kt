package com.pythonnative.runtime.gestures

import android.annotation.SuppressLint
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.components.PNEvents
import com.pythonnative.runtime.components.ViewStyler
import org.json.JSONArray
import kotlin.math.max

/**
 * Binds `MotionEvent` streams on PythonNative views to a
 * [GestureArbiter] and forwards its output as `gesture:<index>`
 * events. Time-based deadlines (long press, multi-tap windows) are
 * polled with the main `Handler`, scheduled at the arbiter's next
 * deadline. When a pan activates, the parent is asked not to intercept
 * so an enclosing scroll view can't steal the drag.
 */
object GestureCoordinator {
    private const val KEY_ARBITER = "arbiter"
    private const val KEY_BOUND = "gestures_bound"
    private const val KEY_POLL_DEADLINE = "poll_deadline"
    private const val KEY_POLL_TOKEN = "poll_token"

    /** Install (or replace) the arbiter for `record` from its `gestures` prop value. */
    fun bind(record: ViewRecord, specs: Any?) {
        val state = record.state
        val array = specs as? JSONArray
        if (array == null || array.length() == 0) {
            state[KEY_ARBITER] = null
            return
        }
        val tag = record.tag
        val arbiter = GestureArbiter(GestureArbiter.decodeSpecs(array)) { index, payload ->
            PNEvents.fireTag(tag, "gesture:$index", JsonUtil.args(payload))
        }
        state[KEY_ARBITER] = arbiter
        if (state[KEY_BOUND] == true) return
        state[KEY_BOUND] = true
        bindTouchStream(record)
    }

    /** Drop the arbiter and any pending poll for `record`. */
    fun unbind(record: ViewRecord) {
        record.state[KEY_ARBITER] = null
        record.state[KEY_POLL_DEADLINE] = null
        record.state[KEY_POLL_TOKEN] = ((record.state[KEY_POLL_TOKEN] as? Int) ?: 0) + 1
    }

    /** Whether `record` currently has gestures wired. */
    fun hasArbiter(record: ViewRecord): Boolean = record.state[KEY_ARBITER] is GestureArbiter

    @SuppressLint("ClickableViewAccessibility")
    private fun bindTouchStream(record: ViewRecord) {
        record.view.setOnTouchListener { v, event ->
            if (ViewStyler.pointerEventsBlocked(v)) return@setOnTouchListener false
            feed(record, event)
        }
    }

    /**
     * Translate one `MotionEvent` into arbiter pointer calls. Returns
     * `true` while any gesture spec is wired (to keep receiving the
     * stream), `false` when there is nothing to feed.
     */
    fun feed(record: ViewRecord, event: MotionEvent): Boolean {
        val arbiter = record.state[KEY_ARBITER] as? GestureArbiter ?: return false
        try {
            val t = now()
            val density = PNBridge.density()
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> {
                    val idx = event.actionIndex
                    arbiter.pointerDown(event.getPointerId(idx), (event.getX(idx) / density).toDouble(), (event.getY(idx) / density).toDouble(), t)
                }
                MotionEvent.ACTION_MOVE -> {
                    for (i in 0 until event.pointerCount) {
                        arbiter.pointerMove(event.getPointerId(i), (event.getX(i) / density).toDouble(), (event.getY(i) / density).toDouble(), t)
                    }
                    if (arbiter.hasActivePan()) record.view.parent?.requestDisallowInterceptTouchEvent(true)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> {
                    val idx = event.actionIndex
                    arbiter.pointerUp(event.getPointerId(idx), (event.getX(idx) / density).toDouble(), (event.getY(idx) / density).toDouble(), t)
                }
                MotionEvent.ACTION_CANCEL -> arbiter.cancel(t)
            }
            schedulePoll(record)
        } catch (e: Exception) {
            PNLog.rateLimited("gesture-feed", "gesture feed failed", e)
        }
        return true
    }

    /** Seconds on the monotonic uptime clock. */
    private fun now(): Double = SystemClock.uptimeMillis() / 1000.0

    private fun schedulePoll(record: ViewRecord) {
        val state = record.state
        val arbiter = state[KEY_ARBITER] as? GestureArbiter ?: return
        val deadline = arbiter.nextDeadline() ?: return
        val pending = state[KEY_POLL_DEADLINE] as? Double
        if (pending != null && pending <= deadline + 0.001) return
        val delayMs = max(1L, ((deadline - now()) * 1000.0).toLong())
        val token = ((state[KEY_POLL_TOKEN] as? Int) ?: 0) + 1
        state[KEY_POLL_TOKEN] = token
        state[KEY_POLL_DEADLINE] = deadline
        MainThread.postDelayed({
            if (state[KEY_POLL_TOKEN] == token) state[KEY_POLL_DEADLINE] = null
            val live = state[KEY_ARBITER] as? GestureArbiter ?: return@postDelayed
            live.poll(now())
            schedulePoll(record)
        }, delayMs)
    }

    /** Convenience for managers that own their own touch listener (Pressable). */
    fun feed(view: View, event: MotionEvent): Boolean {
        val record = PNBridge.registry.recordFor(view) ?: return false
        return feed(record, event)
    }
}
