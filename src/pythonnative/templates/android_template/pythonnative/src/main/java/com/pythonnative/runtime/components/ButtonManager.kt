package com.pythonnative.runtime.components

import android.content.Context
import android.view.View
import android.widget.Button
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject

/** `Button` element: a platform `Button` firing `on_press`. */
class ButtonManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val button = Button(context)
        button.setOnClickListener { fire(it, "on_press") }
        return button
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val button = view as Button
        if (props.has("title")) button.text = props.str("title") ?: ""
        props.num("font_size")?.let { button.textSize = it.toFloat() }
        PNColor.parse(props.value("color"))?.let { button.setTextColor(it) }
        if (props.has("enabled")) button.isEnabled = JsonUtil.truthy(props.value("enabled"))
        if (props.has("disabled")) button.isEnabled = !JsonUtil.truthy(props.value("disabled"))
        if (props.has("all_caps")) button.isAllCaps = JsonUtil.truthy(props.value("all_caps"))
        if (listOf("font_family", "font_weight", "italic", "bold").any { props.has(it) }) {
            TextStyle.applyTypeface(button, propsOf(button))
        }
        ViewStyler.apply(button, props)
    }
}
