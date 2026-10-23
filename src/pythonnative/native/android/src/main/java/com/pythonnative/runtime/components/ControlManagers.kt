package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.content.Context
import android.content.res.ColorStateList
import android.view.View
import android.widget.CheckBox
import android.widget.CompoundButton
import android.widget.ProgressBar
import android.widget.SeekBar
import android.widget.Switch
import org.json.JSONObject

/** Base for `CompoundButton` widgets: `on_change` wiring with a suppress guard. */
abstract class CheckedManager : ComponentManager() {
    protected fun bindChecked(button: CompoundButton) {
        button.setOnCheckedChangeListener { b, checked ->
            if (stateOf(b)["suppress"] == true) return@setOnCheckedChangeListener
            fire(b, "on_change", checked)
        }
    }
}

/** `Switch` element. */
class SwitchManager : CheckedManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val sw = Switch(context)
        bindChecked(sw)
        return sw
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = SwitchProps(props)

        val sw = view as Switch
        if (typed.has_value) {
            val state = stateOf(sw)
            state["suppress"] = true
            try {
                sw.isChecked = (typed.value ?: false)
            } finally {
                state["suppress"] = false
            }
        }
        if (typed.has_disabled) sw.isEnabled = !(typed.disabled ?: false)
        if (typed.has_on_tint_color || typed.has_tint_color || typed.has_thumb_color) {
            val all = SwitchProps(propsOf(sw))
            val track = (all.on_tint_color ?: all.tint_color)?.let { PNColor.parse(PNValues.encode(it)) }
            sw.trackTintList = track?.let { ColorStateList(
                arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()),
                intArrayOf(PNColor.withAlpha(it, 0.5), 0x61000000)) }
            sw.thumbTintList = all.thumb_color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        }
        ViewStyler.apply(sw, props)
    }
}

/** `Checkbox` element with an optional inline label. */
class CheckboxManager : CheckedManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val cb = CheckBox(context)
        bindChecked(cb)
        return cb
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = CheckboxProps(props)

        val cb = view as CheckBox
        if (typed.has_label) cb.text = typed.label ?: ""
        if (typed.has_value) {
            val state = stateOf(cb)
            state["suppress"] = true
            try {
                cb.isChecked = (typed.value ?: false)
            } finally {
                state["suppress"] = false
            }
        }
        if (typed.has_disabled) cb.isEnabled = !(typed.disabled ?: false)
        if (typed.has_color) cb.buttonTintList = typed.color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        ViewStyler.apply(cb, props)
    }
}

/** `ProgressBar` element: a horizontal determinate bar with a 0..1 `value`. */
class ProgressBarManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val pb = ProgressBar(context, null, android.R.attr.progressBarStyleHorizontal)
        pb.max = 1000
        return pb
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = ProgressBarProps(props)

        val pb = view as ProgressBar
        typed.value?.let { pb.progress = (it.coerceIn(0.0, 1.0) * 1000).toInt() }
        if (typed.has_color) pb.progressTintList = typed.color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        if (typed.has_track_color) {
            val track = typed.track_color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
            pb.progressBackgroundTintList = track
            pb.secondaryProgressTintList = track
        }
        if (typed.has_indeterminate) pb.isIndeterminate = (typed.indeterminate ?: false)
        ViewStyler.apply(pb, props)
    }
}

/** `ActivityIndicator` element: an indeterminate spinner. */
class ActivityIndicatorManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = ProgressBar(context)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = ActivityIndicatorProps(props)

        val pb = view as ProgressBar
        if (typed.has_animating) {
            pb.visibility = if ((typed.animating ?: false)) View.VISIBLE else View.GONE
        }
        if (typed.has_color) pb.indeterminateTintList = typed.color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        typed.size?.rawValue?.let {
            // The framework ProgressBar has no runtime size switch; scale "large".
            val scale = if (it == "large") 1.5f else 1f
            pb.scaleX = scale
            pb.scaleY = scale
        }
        ViewStyler.apply(pb, props)
    }
}

/** `Slider` element: a `SeekBar` mapped onto `min_value..max_value`. */
class SliderManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val sb = SeekBar(context)
        sb.max = 1000
        sb.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar, progress: Int, fromUser: Boolean) {
                if (!fromUser) return
                PNComponentEvents.Slider.on_change(seekBar, valueFor(seekBar, progress))
            }

            override fun onStartTrackingTouch(seekBar: SeekBar) {
                PNComponentEvents.Slider.on_sliding_start(seekBar, valueFor(seekBar, seekBar.progress))
            }

            override fun onStopTrackingTouch(seekBar: SeekBar) {
                PNComponentEvents.Slider.on_sliding_complete(seekBar, valueFor(seekBar, seekBar.progress))
            }
        })
        return sb
    }

    private fun range(view: View): Pair<Double, Double> {
        val merged = propsOf(view)
        val mn = SliderProps(merged).min_value ?: 0.0
        val mx = SliderProps(merged).max_value ?: 1.0
        return Pair(mn, mx)
    }

    private fun valueFor(view: View, progress: Int): Double {
        val (mn, mx) = range(view)
        val span = if (mx != mn) mx - mn else 1.0
        var value = mn + (progress / 1000.0) * span
        SliderProps(propsOf(view)).step?.takeIf { it > 0 }?.let { step ->
            value = mn + Math.round((value - mn) / step) * step
        }
        return value.coerceIn(minOf(mn, mx), maxOf(mn, mx))
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = SliderProps(props)

        val sb = view as SeekBar
        val (mn, mx) = range(sb)
        val span = if (mx != mn) mx - mn else 1.0
        if (typed.has_value || typed.has_min_value || typed.has_max_value) {
            val value = SliderProps(propsOf(sb)).value ?: 0.0
            sb.progress = (((value - mn) / span) * 1000).toInt().coerceIn(0, 1000)
        }
        if (typed.has_disabled) sb.isEnabled = !(typed.disabled ?: false)
        if (typed.has_minimum_track_color || typed.has_tint_color) {
            val all = SliderProps(propsOf(sb))
            sb.progressTintList = (all.minimum_track_color ?: all.tint_color)?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        }
        if (typed.has_maximum_track_color) sb.progressBackgroundTintList = typed.maximum_track_color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        if (typed.has_thumb_color) sb.thumbTintList = typed.thumb_color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        ViewStyler.apply(sb, props)
    }
}
