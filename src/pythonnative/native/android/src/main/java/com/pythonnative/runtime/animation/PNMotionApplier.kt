package com.pythonnative.runtime.animation

import android.view.View
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.components.ViewStyler
import org.json.JSONObject

/**
 * Applies the core's motion `prop` writes (RFC 0009) to views.
 *
 * The core runs every animation (shared values, animated styles, and
 * entering, exiting, and layout animations); [FrameClock] ticks it and
 * `PNCore.applyWrites` hands each write here. A write goes through the
 * same code as a static update that changed only that key, and a null
 * value resets the key like a removed one. While that update runs, the
 * view's merged props carry the written value, so managers that read
 * merged props (shadows, text shadows) see it. `opacity` and `transform`
 * take a fast path; a `transform` write replaces the static transform.
 *
 * A motion value wins over the static one until the core writes the key
 * again. The core re-sends motion values after a commit changes the same
 * key, so nothing here remembers overrides.
 */
object PNMotionApplier {
    /** Apply one written `prop` to `view`. */
    fun apply(view: View, prop: String, value: Any?) {
        when (prop) {
            "opacity" -> view.alpha = (JsonUtil.toDoubleOrNull(value) ?: 1.0).toFloat()
            "transform" -> ViewStyler.applyTransformValue(view, if (JsonUtil.isNull(value)) null else value)
            else -> applyAsUpdate(view, prop, value)
        }
    }

    private fun applyAsUpdate(view: View, prop: String, value: Any?) {
        val written = if (JsonUtil.isNull(value)) JSONObject.NULL else value
        val changed = JSONObject().put(prop, written)
        val record = PNBridge.registry.recordFor(view)
        if (record == null) {
            ViewStyler.apply(view, changed)
            return
        }
        val props = record.props
        val had = props.has(prop)
        val previous = props.opt(prop)
        props.put(prop, written)
        try {
            record.manager.update(view, changed)
        } finally {
            if (had) props.put(prop, previous) else props.remove(prop)
        }
    }
}
