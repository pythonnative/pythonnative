package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.RectF
import android.graphics.drawable.BitmapDrawable
import android.graphics.drawable.Drawable
import android.view.View
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.navigation.NavigationBarView
import com.pythonnative.runtime.assets.PNAssets
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
        val typed = TabBarProps(props)

        val bnv = view as BottomNavigationView
        val merged = propsOf(bnv)
        if (typed.has_items) setMenu(bnv, merged.value("items") as? JSONArray)
        if (typed.has_active_tab || props.has("active_index") || typed.has_items) {
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
                icon(bnv.context, item.value("icon"))?.let { menuItem.icon = it }
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

    companion object {
        /** The size tab bar icons are rasterized at, in dp. */
        const val ICON_SIZE_DP = 24f

        /**
         * Resolve an icon spec to a tintable drawable.
         *
         * `{"shapes": [...], "view_box": "..."}` is drawn with the SVG
         * renderer (Lucide icons resolved by Python); `{"uri": "asset://..."}`
         * decodes a bundled image. Anything else yields no icon.
         */
        fun icon(context: Context, spec: Any?): Drawable? {
            val dict = spec as? JSONObject ?: return null
            val density = context.resources.displayMetrics.density
            val raw = dict.optJSONArray("shapes")
            if (raw != null && raw.length() > 0) {
                val shapes = (0 until raw.length()).mapNotNull { index ->
                    runCatching { PNSvgShape.decode(raw.get(index)) }.getOrNull()
                }
                val viewBox = SvgView.parseViewBox(dict.str("view_box")) ?: RectF(0f, 0f, 24f, 24f)
                val paint = SvgPaint(fill = "none", stroke = "currentColor", strokeWidth = 2f, lineCap = "round", lineJoin = "round")
                // Drawn white so the tab bar's icon tint list recolors it.
                val bitmap = SvgRenderer.bitmap(shapes, viewBox, ICON_SIZE_DP, paint, Color.WHITE, density)
                return BitmapDrawable(context.resources, bitmap)
            }
            val uri = dict.str("uri")
            if (!uri.isNullOrEmpty() && PNAssets.isAssetUri(uri)) {
                val resolved = PNAssets.resolve(uri) ?: return null
                val px = (ICON_SIZE_DP * density).toInt()
                val bitmap = ImageLoader.decodeStream({ resolved.open() }, px, px, resolved.scale) ?: return null
                return BitmapDrawable(context.resources, bitmap)
            }
            return null
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
