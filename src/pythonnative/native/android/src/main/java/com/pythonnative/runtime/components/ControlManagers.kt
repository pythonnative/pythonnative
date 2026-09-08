package com.pythonnative.runtime.components

import android.content.Context
import android.content.res.ColorStateList
import android.view.View
import android.widget.CheckBox
import android.widget.CompoundButton
import android.widget.ProgressBar
import android.widget.SeekBar
import android.widget.Switch
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
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
        val sw = view as Switch
        if (props.has("value")) {
            val state = stateOf(sw)
            state["suppress"] = true
            try {
                sw.isChecked = JsonUtil.truthy(props.value("value"))
            } finally {
                state["suppress"] = false
            }
        }
        if (props.has("disabled")) sw.isEnabled = !JsonUtil.truthy(props.value("disabled"))
        if (props.has("enabled")) sw.isEnabled = JsonUtil.truthy(props.value("enabled"))
        PNColor.parse(props.value("on_tint_color") ?: props.value("tint_color"))?.let {
            sw.thumbTintList = ColorStateList(
                arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()),
                intArrayOf(it, 0xFFFAFAFA.toInt()),
            )
            sw.trackTintList = ColorStateList(
                arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()),
                intArrayOf(PNColor.withAlpha(it, 0.5), 0x61000000),
            )
        }
        PNColor.parse(props.value("thumb_color"))?.let { sw.thumbTintList = ColorStateList.valueOf(it) }
        ViewStyler.applyAccessibility(sw, props)
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
        val cb = view as CheckBox
        if (props.has("label")) cb.text = props.str("label") ?: ""
        if (props.has("value")) {
            val state = stateOf(cb)
            state["suppress"] = true
            try {
                cb.isChecked = JsonUtil.truthy(props.value("value"))
            } finally {
                state["suppress"] = false
            }
        }
        if (props.has("disabled")) cb.isEnabled = !JsonUtil.truthy(props.value("disabled"))
        PNColor.parse(props.value("color"))?.let { cb.buttonTintList = ColorStateList.valueOf(it) }
        ViewStyler.applyAccessibility(cb, props)
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
        val pb = view as ProgressBar
        props.num("value")?.let { pb.progress = (it.coerceIn(0.0, 1.0) * 1000).toInt() }
        PNColor.parse(props.value("color"))?.let { pb.progressTintList = ColorStateList.valueOf(it) }
        PNColor.parse(props.value("track_color"))?.let {
            val track = ColorStateList.valueOf(it)
            pb.progressBackgroundTintList = track
            pb.secondaryProgressTintList = track
        }
        if (props.has("indeterminate")) pb.isIndeterminate = JsonUtil.truthy(props.value("indeterminate"))
        ViewStyler.apply(pb, props)
    }
}

/** `ActivityIndicator` element: an indeterminate spinner. */
class ActivityIndicatorManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = ProgressBar(context)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val pb = view as ProgressBar
        if (props.has("animating")) {
            pb.visibility = if (JsonUtil.truthy(props.value("animating"))) View.VISIBLE else View.GONE
        }
        if (props.has("hides_when_stopped") && !JsonUtil.truthy(props.value("hides_when_stopped"))) {
            pb.visibility = View.VISIBLE
        }
        PNColor.parse(props.value("color"))?.let { pb.indeterminateTintList = ColorStateList.valueOf(it) }
        props.str("size")?.let {
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
                fire(seekBar, "on_change", valueFor(seekBar, progress))
            }

            override fun onStartTrackingTouch(seekBar: SeekBar) {
                fire(seekBar, "on_sliding_start", valueFor(seekBar, seekBar.progress))
            }

            override fun onStopTrackingTouch(seekBar: SeekBar) {
                fire(seekBar, "on_sliding_complete", valueFor(seekBar, seekBar.progress))
            }
        })
        return sb
    }

    private fun range(view: View): Pair<Double, Double> {
        val merged = propsOf(view)
        val mn = merged.num("min_value") ?: merged.num("minimum_value") ?: 0.0
        val mx = merged.num("max_value") ?: merged.num("maximum_value") ?: 1.0
        return Pair(mn, mx)
    }

    private fun valueFor(view: View, progress: Int): Double {
        val (mn, mx) = range(view)
        val span = if (mx != mn) mx - mn else 1.0
        var value = mn + (progress / 1000.0) * span
        propsOf(view).num("step")?.takeIf { it > 0 }?.let { step ->
            value = mn + Math.round((value - mn) / step) * step
        }
        return value
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val sb = view as SeekBar
        val (mn, mx) = range(sb)
        val span = if (mx != mn) mx - mn else 1.0
        props.num("value")?.let { sb.progress = (((it - mn) / span) * 1000).toInt().coerceIn(0, 1000) }
        if (props.has("disabled")) sb.isEnabled = !JsonUtil.truthy(props.value("disabled"))
        PNColor.parse(props.value("minimum_track_tint_color") ?: props.value("tint_color"))?.let {
            sb.progressTintList = ColorStateList.valueOf(it)
        }
        PNColor.parse(props.value("maximum_track_tint_color"))?.let { sb.progressBackgroundTintList = ColorStateList.valueOf(it) }
        PNColor.parse(props.value("thumb_tint_color"))?.let { sb.thumbTintList = ColorStateList.valueOf(it) }
        ViewStyler.applyAccessibility(sb, props)
    }
}
