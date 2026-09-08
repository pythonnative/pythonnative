package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.arr
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject
import kotlin.math.max

/**
 * `SegmentedControl` element: a horizontal `LinearLayout` of equal-width
 * toggle `Button`s. The selected segment is filled with `tint_color`;
 * the rest are outlined. The control owns its subviews, so child
 * inserts are ignored.
 */
class SegmentedControlManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val ll = LinearLayout(context)
        ll.orientation = LinearLayout.HORIZONTAL
        return ll
    }

    override fun insertChild(parent: View, child: View, index: Int) {}

    override fun removeChild(parent: View, child: View) {}

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val ll = view as LinearLayout
        val state = stateOf(ll)
        val merged = propsOf(ll)
        var segmentsChanged = false
        if (props.has("segments") || initial) {
            val segments = JsonUtil.toList(merged.arr("segments")).map { it?.toString() ?: "" }
            if (initial || segments != state["segments"]) {
                state["segments"] = segments
                segmentsChanged = true
            }
        }
        props.value("selected_index")?.let { state["selected_index"] = JsonUtil.toInt(it) }
        if (segmentsChanged) rebuild(ll) else restyle(ll)
        ViewStyler.applyAccessibility(ll, props)
    }

    private fun rebuild(ll: LinearLayout) {
        val state = stateOf(ll)
        ll.removeAllViews()
        @Suppress("UNCHECKED_CAST")
        val segments = state["segments"] as? List<String> ?: emptyList()
        val enabled = propsOf(ll).value("enabled") != false
        segments.forEachIndexed { index, label ->
            val btn = Button(ll.context)
            btn.text = label
            btn.isAllCaps = false
            btn.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1f)
            btn.isEnabled = enabled
            btn.setOnClickListener {
                if (propsOf(ll).value("enabled") == false) return@setOnClickListener
                stateOf(ll)["selected_index"] = index
                restyle(ll)
                fire(ll, "on_change", index)
            }
            ll.addView(btn)
        }
        restyle(ll)
    }

    private fun restyle(ll: LinearLayout) {
        val merged = propsOf(ll)
        val accent = PNColor.parseOr(merged.value("tint_color"), DEFAULT_ACCENT)
        val selected = (stateOf(ll)["selected_index"] as? Int) ?: JsonUtil.toInt(merged.value("selected_index"))
        val enabled = merged.value("enabled") != false
        for (i in 0 until ll.childCount) {
            val btn = ll.getChildAt(i) as? Button ?: continue
            val drawable = GradientDrawable()
            drawable.cornerRadius = pxF(6.0)
            drawable.setStroke(px(1.0), accent)
            if (i == selected) {
                drawable.setColor(accent)
                btn.setTextColor(0xFFFFFFFF.toInt())
            } else {
                drawable.setColor(0x00FFFFFF)
                btn.setTextColor(accent)
            }
            btn.background = drawable
            btn.isEnabled = enabled
        }
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        // Weighted children measure to ~0 under an unspecified spec, so
        // size to the sum of the segments' natural widths instead.
        val ll = view as LinearLayout
        if (ll.childCount == 0) return floatArrayOf(0f, 0f)
        val spec = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        var totalW = 0
        var maxH = 0
        for (i in 0 until ll.childCount) {
            val child = ll.getChildAt(i)
            child.measure(spec, spec)
            totalW += child.measuredWidth
            maxH = max(maxH, child.measuredHeight)
        }
        return floatArrayOf(dp(totalW).toFloat(), dp(maxH).toFloat())
    }

    private companion object {
        val DEFAULT_ACCENT = 0xFF007AFF.toInt()
    }
}
