package com.pythonnative.runtime.animation

import android.view.View
import android.widget.TextView
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.components.PNColor
import com.pythonnative.runtime.components.ViewStyler

/**
 * Applies animated prop values to views: `opacity`, `background_color`,
 * `translate_x`, `translate_y`, `scale`, `scale_x`, `scale_y`, `rotate`,
 * `rotate_x`, `rotate_y`, plus `color` for text.
 *
 * The renderer core runs every timing, spring, and decay driver and every
 * animation graph; [FrameClock] ticks it and `PNCore.applyWrites` hands
 * each frame's values here.
 */
object PNAnimator {
    /** Apply one animated value to `view`. Unknown props are ignored. */
    fun setProperty(view: View, prop: String, value: Any?) {
        if (JsonUtil.isNull(value)) return
        try {
            when (prop) {
                "opacity" -> view.alpha = JsonUtil.toDouble(value).toFloat()
                "translate_x" -> view.translationX = px(JsonUtil.toDouble(value))
                "translate_y" -> view.translationY = px(JsonUtil.toDouble(value))
                "scale" -> {
                    val s = JsonUtil.toDouble(value).toFloat()
                    view.scaleX = s
                    view.scaleY = s
                }
                "scale_x" -> view.scaleX = JsonUtil.toDouble(value).toFloat()
                "scale_y" -> view.scaleY = JsonUtil.toDouble(value).toFloat()
                "rotate" -> view.rotation = ViewStyler.angleDegrees(value)
                "rotate_x" -> view.rotationX = ViewStyler.angleDegrees(value)
                "rotate_y" -> view.rotationY = ViewStyler.angleDegrees(value)
                "background_color" -> ViewStyler.setAnimatedBackground(view, value)
                "color" -> (view as? TextView)?.setTextColor(PNColor.parseOr(value, 0xFF000000.toInt()))
            }
        } catch (e: Exception) {
            PNLog.swallowed("PNAnimator.setProperty", e)
        }
    }

    private fun px(dp: Double): Float = (dp * PNBridge.density()).toFloat()
}
