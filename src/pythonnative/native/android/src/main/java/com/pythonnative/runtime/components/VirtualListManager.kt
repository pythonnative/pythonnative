package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.content.Context
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.core.PNCore
import org.json.JSONObject
import kotlin.math.roundToInt

/**
 * Keyed native recycling over the core's list dataset; Python prepares
 * logical children asynchronously. Row keys, extents, and sticky flags are
 * read from the core (`PNCore.list*`), which validated and published the
 * dataset patch this list applies when its `dataset` prop changes.
 */
class VirtualListManager : ComponentManager() {
    private class Holder(val container: FrameLayout) : RecyclerView.ViewHolder(container) { var key = "" }
    private inner class ListView(context: Context, val tag: Long) : SwipeRefreshLayout(context) {
        val recycler = RecyclerView(context)
        val content = FrameLayout(context)
        val stickyContainer = FrameLayout(context)
        var revision = 0L
        private var pinnedKey: String? = null
        private var lastWindow = emptyList<Long>()
        val roots = HashMap<String, View>()
        val heights = HashMap<String, Double>()
        val holders = HashMap<String, Holder>()
        var horizontal = false
        val manager = LinearLayoutManager(context)
        val rows = object : RecyclerView.Adapter<Holder>() {
            override fun getItemCount() = PNCore.listCount(tag)
            override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder = Holder(FrameLayout(context))
            override fun onBindViewHolder(holder: Holder, position: Int) {
                holders.remove(holder.key)
                val key = PNCore.listKey(tag, position) ?: return
                holder.key = key
                holders[key] = holder
                attach(holder, key, position)
                if (key !in roots && !PNCore.listSticky(tag, position)) fire(this@ListView, "on_bind_row", JSONObject().put("index", position).put("key", key)
                    .put("revision", revision).put("extent", height / PNBridge.density()).put("width", width / PNBridge.density()).put("sticky", PNCore.listStickyAt(tag, position)))
            }
            override fun onViewRecycled(holder: Holder) {
                holders.remove(holder.key)
                holder.container.removeAllViews()
            }
        }
        init {
            content.addView(recycler, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            content.addView(stickyContainer, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0))
            addView(content, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            manager.initialPrefetchItemCount = 12
            manager.isItemPrefetchEnabled = true
            recycler.layoutManager = manager
            recycler.adapter = rows
            recycler.itemAnimator = null
            isEnabled = false
            setOnRefreshListener { fire(this, "on_refresh") }
            recycler.addOnScrollListener(object : RecyclerView.OnScrollListener() {
                override fun onScrolled(view: RecyclerView, dx: Int, dy: Int) {
                    updateSticky()
                    emitWindow()
                    // App scroll callbacks are independent of window requests.
                    if (!hasEvent(this@ListView, "on_scroll")) return
                    fire(this@ListView, "on_scroll", scrollPayload())
                }
            })
        }
        /**
         * The `ScrollEvent` fields in dp plus the list-window fields the
         * Python `FlatList` layer reads (`first`/`last` visible positions,
         * `extent` and `range` along the scroll axis).
         */
        fun scrollPayload(): JSONObject {
            val density = PNBridge.density()
            val extent = (if (horizontal) width else height) / density
            val range = (if (horizontal) recycler.computeHorizontalScrollRange() else recycler.computeVerticalScrollRange()) / density
            return JSONObject()
                .put("x", recycler.computeHorizontalScrollOffset() / density)
                .put("y", recycler.computeVerticalScrollOffset() / density)
                .put("content_width", if (horizontal) range else width / density)
                .put("content_height", if (horizontal) height / density else range)
                .put("viewport_width", width / density)
                .put("viewport_height", height / density)
                .put("extent", extent)
                .put("range", range)
                .put("first", manager.findFirstVisibleItemPosition())
                .put("last", manager.findLastVisibleItemPosition())
        }
        fun emitWindow() {
            val first = manager.findFirstVisibleItemPosition().coerceAtLeast(0)
            val last = manager.findLastVisibleItemPosition()
            val extent = (if (horizontal) width else height) / PNBridge.density()
            val sticky = PNCore.listStickyAt(tag, first)
            val identity = listOf(first.toLong(), last.toLong(), extent.toLong(), sticky.toLong(), revision)
            if (identity == lastWindow) return
            lastWindow = identity
            fire(this, "on_window", scrollPayload().put("revision", revision).put("sticky", sticky))
        }
        override fun onLayout(changed: Boolean, left: Int, top: Int, right: Int, bottom: Int) {
            super.onLayout(changed, left, top, right, bottom)
            updateSticky(); emitWindow()
        }
        fun updateSticky() {
            val first = manager.findFirstVisibleItemPosition()
            val index = if (horizontal || first < 0) -1 else PNCore.listStickyAt(tag, first)
            val key = if (index >= 0) PNCore.listKey(tag, index) else null
            val natural = if (index >= 0) manager.findViewByPosition(index)?.top else null
            val wanted = key?.takeIf { natural == null || natural < 0 }
            if (wanted != pinnedKey) {
                val old = pinnedKey
                pinnedKey = null
                stickyContainer.removeAllViews()
                if (old != null) holders[old]?.let { holder -> reattach(holder, old) }
                pinnedKey = wanted
            }
            val root = wanted?.let { roots[it] }
            if (root == null) { stickyContainer.visibility = View.GONE; return }
            if (root.parent !== stickyContainer) {
                (root.parent as? ViewGroup)?.removeView(root)
                stickyContainer.addView(root, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            }
            stickyContainer.visibility = View.VISIBLE
            val extent = ((heights[wanted] ?: PNCore.listExtent(tag, index).takeIf { it > 0 } ?: 44.0) * PNBridge.density()).roundToInt()
            if (stickyContainer.layoutParams.height != extent) stickyContainer.layoutParams = stickyContainer.layoutParams.apply { height = extent }
            val next = PNCore.listNextSticky(tag, index).takeIf { it >= 0 }?.let { manager.findViewByPosition(it)?.top }
            stickyContainer.translationY = if (next == null) 0f else (next - extent).coerceAtMost(0).toFloat()
        }
        /** Re-attach a bound row after its root or extent changed. */
        fun reattach(holder: Holder, key: String) {
            val index = PNCore.listIndex(tag, key)
            if (index >= 0) attach(holder, key, index)
        }
        fun attach(holder: Holder, key: String, index: Int) {
            val size = ((heights[key] ?: PNCore.listExtent(tag, index)) * PNBridge.density()).roundToInt().coerceAtLeast(1)
            // Preserve RecyclerView.LayoutParams, which retain the holder identity.
            val params = holder.container.layoutParams as? RecyclerView.LayoutParams
                ?: RecyclerView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, size)
            params.width = if (horizontal) size else ViewGroup.LayoutParams.MATCH_PARENT
            params.height = if (horizontal) ViewGroup.LayoutParams.MATCH_PARENT else size
            holder.container.layoutParams = params
            holder.container.removeAllViews()
            if (key == pinnedKey) return
            roots[key]?.let { root ->
                (root.parent as? ViewGroup)?.removeView(root)
                holder.container.addView(root, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
            }
        }
    }
    override fun createView(context: Context, tag: Long, props: JSONObject): View = ListView(context, tag)
    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        ViewStyler.apply(view, props)
        val list = view as ListView
        val all = PNBridge.registry.recordFor(view)?.props ?: props
        list.horizontal = all.optBoolean("horizontal", false)
        list.manager.orientation = if (list.horizontal) RecyclerView.HORIZONTAL else RecyclerView.VERTICAL
        list.recycler.isVerticalScrollBarEnabled = all.optBoolean("shows_scroll_indicator", true)
        list.recycler.isHorizontalScrollBarEnabled = list.recycler.isVerticalScrollBarEnabled
        val refresh = all.optJSONObject("refresh_control")
        list.isEnabled = refresh != null && !list.horizontal
        list.isRefreshing = refresh?.optBoolean("refreshing", false) == true
        refresh?.optString("tint_color")?.takeIf { it.isNotEmpty() }?.let { color -> PNColor.parse(color)?.let { list.setColorSchemeColors(it) } }
        if (props.has("dataset")) publish(list)
    }

    /** Apply the dataset patch the core published with this mount, keeping the first visible row in place. */
    private fun publish(list: ListView) {
        val first = list.manager.findFirstVisibleItemPosition()
        val anchor = if (first >= 0) PNCore.listKey(list.tag, first) else null
        val anchorView = list.manager.findViewByPosition(first)
        val offset = (if (list.horizontal) anchorView?.left else anchorView?.top) ?: 0
        val patch = PNCore.listApply(list.tag)
        if (patch == null) {
            // A recreated list reads the dataset the core already holds.
            list.revision = PNCore.listRevision(list.tag)
            list.rows.notifyDataSetChanged()
        } else {
            list.revision = patch.optLong("revision", list.revision)
            val edits = patch.optJSONArray("edits") ?: org.json.JSONArray()
            if (patch.optBoolean("reset")) {
                list.heights.clear()
                list.rows.notifyDataSetChanged()
            } else {
                list.heights.keys.removeAll { PNCore.listIndex(list.tag, it) < 0 }
                for (i in 0 until edits.length()) {
                    val edit = edits.optJSONArray(i) ?: continue
                    when (edit.optString(0)) {
                        "i" -> list.rows.notifyItemInserted(edit.optInt(2))
                        "d" -> list.rows.notifyItemRemoved(edit.optInt(1))
                        "m" -> list.rows.notifyItemMoved(edit.optInt(1), edit.optInt(2))
                    }
                }
                if (edits.length() > 0 && anchor != null) {
                    PNCore.listIndex(list.tag, anchor).takeIf { it >= 0 }?.let { list.manager.scrollToPositionWithOffset(it, offset) }
                }
            }
            // Updated rows may have new extents.
            for ((key, holder) in list.holders.toMap()) list.reattach(holder, key)
        }
        list.post { list.updateSticky(); list.emitWindow() }
    }

    override fun insertChild(parent: View, child: View, index: Int) {
        val list = parent as ListView
        val record = PNBridge.registry.recordFor(child) ?: return
        val key = record.props.optString("_pn_list_key")
        list.roots[key] = child
        rowOwners[record.tag] = { width, height ->
            val extent = if (list.horizontal) width else height
            if (extent > 0 && list.heights[key] != extent) {
                list.heights[key] = extent
                list.post {
                    list.holders[key]?.let { holder -> list.reattach(holder, key) }
                    list.updateSticky()
                }
            }
        }
        list.holders[key]?.let { holder -> list.reattach(holder, key) }
        list.updateSticky()
    }
    override fun removeChild(parent: View, child: View) {
        val list = parent as ListView
        PNBridge.registry.recordFor(child)?.let { record ->
            list.roots.remove(record.props.optString("_pn_list_key"))
            rowOwners.remove(record.tag)
        }
        (child.parent as? ViewGroup)?.removeView(child)
    }
    override fun teardown(view: View) {
        val list = view as ListView
        for (root in list.roots.values) PNBridge.registry.recordFor(root)?.let { rowOwners.remove(it.tag) }
        list.recycler.adapter = null
        list.roots.clear()
        list.holders.clear()
    }
    override fun command(view: View, name: String, args: JSONObject): Any? {
        val list = view as ListView
        if (name == "get_scroll_offset") return mapOf(
            "x" to list.recycler.computeHorizontalScrollOffset() / PNBridge.density(),
            "y" to list.recycler.computeVerticalScrollOffset() / PNBridge.density())
        if (name == "flash_scroll_indicators") { list.recycler.isVerticalScrollBarEnabled = true; list.recycler.invalidate(); return null }
        val animated = args.optBoolean("animated", true)
        val index = when (name) {
            "scroll_to_end" -> (list.rows.itemCount - 1).coerceAtLeast(0)
            "scroll_to_index" -> args.optInt("index").coerceIn(0, (list.rows.itemCount - 1).coerceAtLeast(0))
            else -> -1
        }
        if (index >= 0) { if (animated) list.recycler.smoothScrollToPosition(index) else list.manager.scrollToPositionWithOffset(index, 0) }
        if (name == "scroll_to_offset") {
            val delta = (args.optDouble(if (list.horizontal) "x" else "y") * PNBridge.density()).roundToInt() -
                (if (list.horizontal) list.recycler.computeHorizontalScrollOffset() else list.recycler.computeVerticalScrollOffset())
            val x = if (list.horizontal) delta else 0
            val y = if (list.horizontal) 0 else delta
            if (animated) list.recycler.smoothScrollBy(x, y) else list.recycler.scrollBy(x, y)
        }
        return null
    }
    companion object {
        private val rowOwners = HashMap<Long, (Double, Double) -> Unit>()
        fun measured(tag: Long, width: Double, height: Double) { rowOwners[tag]?.invoke(width, height) }
    }
}
