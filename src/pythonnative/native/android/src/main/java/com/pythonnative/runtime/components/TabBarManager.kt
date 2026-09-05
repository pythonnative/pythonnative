package com.pythonnative.runtime.components

import android.content.Context
import android.content.res.ColorStateList
import android.view.View
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.navigation.NavigationBarView
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONArray
import org.json.JSONObject

/**
 * `TabBar` element backed by Material's `BottomNavigationView`.
 *
 * `items` is a list of `{name, title, icon}`; `active_tab` names the
 * selected item (an integer `active_index` is also accepted). Selecting
 * a tab fires `on_tab_select(name)` and `on_select(index)` when wired.
 */
class TabBarManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val bnv = BottomNavigationView(context)
        bnv.setBackgroundColor(0xFFFFFFFF.toInt())
        bnv.labelVisibilityMode = NavigationBarView.LABEL_VISIBILITY_LABELED
        bnv.setOnItemSelectedListener { item ->
            if (stateOf(bnv)["suppress"] == true) return@setOnItemSelectedListener true
            val items = propsOf(bnv).value("items") as? JSONArray
            val index = item.itemId
            val spec = items?.optJSONObject(index)
            if (spec != null) {
                fire(bnv, "on_tab_select", spec.str("name") ?: "")
                if (hasEvent(bnv, "on_select")) fire(bnv, "on_select", index)
            }
            true
        }
        return bnv
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val bnv = view as BottomNavigationView
        val merged = propsOf(bnv)
        if (props.has("items")) setMenu(bnv, merged.value("items") as? JSONArray)
        if (props.has("active_tab") || props.has("active_index") || props.has("items")) {
            setActive(bnv, merged)
        }
        val active = PNColor.parse(props.value("active_tint_color") ?: props.value("tint_color"))
        val inactive = PNColor.parse(props.value("inactive_tint_color"))
        if (active != null || inactive != null) {
            val a = active ?: PNColor.parse(merged.value("active_tint_color")) ?: 0xFF1976D2.toInt()
            val i = inactive ?: PNColor.parse(merged.value("inactive_tint_color")) ?: 0xFF757575.toInt()
            val list = ColorStateList(arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()), intArrayOf(a, i))
            bnv.itemIconTintList = list
            bnv.itemTextColor = list
        }
        PNColor.parse(props.value("background_color"))?.let { bnv.setBackgroundColor(it) }
        if (props.has("shows_labels")) {
            bnv.labelVisibilityMode = if (JsonUtil.truthy(props.value("shows_labels"))) {
                NavigationBarView.LABEL_VISIBILITY_LABELED
            } else {
                NavigationBarView.LABEL_VISIBILITY_UNLABELED
            }
        }
        ViewStyler.apply(bnv, JSONObject(props.toString()).apply { remove("background_color") })
    }

    private fun setMenu(bnv: BottomNavigationView, items: JSONArray?) {
        val state = stateOf(bnv)
        state["suppress"] = true
        try {
            val menu = bnv.menu
            menu.clear()
            if (items == null) return
            for (i in 0 until items.length()) {
                val item = items.optJSONObject(i) ?: continue
                val title = item.str("title") ?: item.str("name") ?: ""
                val menuItem = menu.add(0, i, i, title)
                val icon = resolveIcon(bnv.context, item.value("icon"))
                if (icon != 0) menuItem.setIcon(icon)
                item.str("badge")?.let { badge ->
                    val b = bnv.getOrCreateBadge(i)
                    badge.toIntOrNull()?.let { b.number = it }
                }
            }
        } catch (e: Exception) {
            PNLog.swallowed("TabBarManager.setMenu", e)
        } finally {
            state["suppress"] = false
        }
    }

    /** Resolve an icon spec (`"ic_menu_home"` or `{"android": ...}`) to a drawable id. */
    private fun resolveIcon(context: Context, icon: Any?): Int {
        val name = when (icon) {
            is String -> icon
            is JSONObject -> icon.str("android")
            else -> null
        } ?: return 0
        return try {
            val field = android.R.drawable::class.java.getField(name)
            field.getInt(null)
        } catch (e: Exception) {
            context.resources.getIdentifier(name, "drawable", context.packageName)
        }
    }

    private fun setActive(bnv: BottomNavigationView, merged: JSONObject) {
        val items = merged.value("items") as? JSONArray ?: return
        val active = merged.str("active_tab")
        var target = -1
        if (active != null) {
            for (i in 0 until items.length()) {
                if (items.optJSONObject(i)?.str("name") == active) {
                    target = i
                    break
                }
            }
        }
        if (target < 0) target = merged.value("active_index")?.let { JsonUtil.toInt(it, -1) } ?: -1
        if (target < 0 || target >= items.length()) return
        if (bnv.selectedItemId == target) return
        val state = stateOf(bnv)
        state["suppress"] = true
        try {
            bnv.selectedItemId = target
        } finally {
            state["suppress"] = false
        }
    }
}
