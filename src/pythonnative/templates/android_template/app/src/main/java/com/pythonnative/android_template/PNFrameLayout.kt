package com.pythonnative.android_template

import android.content.Context
import android.view.MotionEvent
import android.widget.FrameLayout

/**
 * Container `FrameLayout` with React Native-style `pointer_events`
 * semantics. Python's Android view handlers create these for flex
 * containers and drive the mode via [setPointerEventsMode]:
 *
 * - `"auto"` (default): normal dispatch; the view and its children
 *   both receive touches.
 * - `"none"`: neither the view nor its children receive touches; the
 *   event falls through to whatever sits underneath.
 * - `"box_none"`: children receive touches, but the view itself never
 *   intercepts or consumes them (the Python side also mutes the
 *   view's own touch listeners).
 * - `"box_only"`: the view receives touches and its children don't;
 *   every event in the subtree is intercepted at this level.
 *
 * Interception can't be expressed from Python because Chaquopy can't
 * subclass `ViewGroup`, so this class owns the two overrides and
 * exposes the mode as a plain setter.
 */
class PNFrameLayout(context: Context) : FrameLayout(context) {
    private var pointerEventsMode: String = "auto"

    /** Set the pointer-events mode; `null` restores `"auto"`. */
    fun setPointerEventsMode(mode: String?) {
        pointerEventsMode = mode ?: "auto"
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        if (pointerEventsMode == "none") {
            // Declining the whole dispatch lets the event pass through
            // to views underneath, matching RN's "none".
            return false
        }
        return super.dispatchTouchEvent(ev)
    }

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        return when (pointerEventsMode) {
            "box_only" -> true
            "box_none" -> false
            else -> super.onInterceptTouchEvent(ev)
        }
    }
}
