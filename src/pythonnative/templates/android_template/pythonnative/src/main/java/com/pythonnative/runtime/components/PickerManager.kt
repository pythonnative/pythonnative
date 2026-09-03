package com.pythonnative.runtime.components

import android.content.Context
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Spinner
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONArray
import org.json.JSONObject

/** `Picker` element: a native `Spinner` dropdown over `items` of `{label, value}`. */
class PickerManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val spinner = Spinner(context)
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>, view: View?, position: Int, id: Long) {
                if (stateOf(parent)["suppress"] == true) return
                val items = propsOf(parent).value("items") as? JSONArray ?: return
                if (position < 0 || position >= items.length()) return
                fire(parent, "on_change", itemValue(items.opt(position)))
            }

            override fun onNothingSelected(parent: AdapterView<*>) {}
        }
        return spinner
    }

    private fun itemValue(item: Any?): Any? = when (item) {
        is JSONObject -> item.value("value")
        JSONObject.NULL -> null
        else -> item
    }

    private fun itemLabel(item: Any?): String = when (item) {
        is JSONObject -> item.str("label") ?: item.str("value") ?: ""
        null, JSONObject.NULL -> ""
        else -> item.toString()
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val spinner = view as Spinner
        val state = stateOf(spinner)
        val merged = propsOf(spinner)
        val items = merged.value("items") as? JSONArray ?: JSONArray()
        if (props.has("items") || initial) {
            val labels = (0 until items.length()).map { itemLabel(items.opt(it)) }
            val adapter = ArrayAdapter(spinner.context, android.R.layout.simple_spinner_item, labels)
            adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            state["suppress"] = true
            try {
                spinner.adapter = adapter
            } finally {
                state["suppress"] = false
            }
        }
        if (props.has("value") || props.has("selected_value") || initial) {
            val value = merged.value("value") ?: merged.value("selected_value")
            var target = -1
            for (i in 0 until items.length()) {
                if (valuesEqual(itemValue(items.opt(i)), value)) {
                    target = i
                    break
                }
            }
            if (target >= 0 && spinner.selectedItemPosition != target) {
                state["suppress"] = true
                try {
                    spinner.setSelection(target, false)
                } finally {
                    state["suppress"] = false
                }
            }
        }
        if (props.has("enabled")) spinner.isEnabled = JsonUtil.truthy(props.value("enabled"))
        if (props.has("disabled")) spinner.isEnabled = !JsonUtil.truthy(props.value("disabled"))
        ViewStyler.apply(spinner, props)
    }

    private fun valuesEqual(a: Any?, b: Any?): Boolean {
        if (a == b) return true
        if (a is Number && b is Number) return a.toDouble() == b.toDouble()
        return a != null && b != null && a.toString() == b.toString()
    }
}
