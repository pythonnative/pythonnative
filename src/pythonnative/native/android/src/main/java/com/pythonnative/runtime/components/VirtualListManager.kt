package com.pythonnative.runtime.components

import android.content.Context
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.ViewRecord
import org.json.JSONObject
import kotlin.math.roundToInt

/** Keyed native recycling; Python prepares logical children asynchronously. */
class VirtualListManager : ComponentManager() {
    private data class Item(val key: String, val revision: Int, val estimate: Double)
    private class Holder(val container: FrameLayout) : RecyclerView.ViewHolder(container) { var key = "" }
    private inner class ListView(context: Context) : SwipeRefreshLayout(context) {
        val recycler = RecyclerView(context)
        val roots = HashMap<String, View>()
        val heights = HashMap<String, Double>()
        val holders = HashMap<String, Holder>()
        var horizontal = false
        val manager = LinearLayoutManager(context)
        val rows = object : ListAdapter<Item, Holder>(object : DiffUtil.ItemCallback<Item>() {
            override fun areItemsTheSame(a: Item, b: Item) = a.key == b.key
            override fun areContentsTheSame(a: Item, b: Item) = a == b
        }) {
            override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder = Holder(FrameLayout(context))
            override fun onBindViewHolder(holder: Holder, position: Int) {
                holders.remove(holder.key)
                val item = getItem(position)
                holder.key = item.key
                holders[item.key] = holder
                attach(holder, item)
                fire(this@ListView, "on_bind_row", JSONObject().put("index", position).put("key", item.key)
                    .put("revision", item.revision).put("width", width / PNBridge.density()))
            }
            override fun onViewRecycled(holder: Holder) {
                holders.remove(holder.key)
                holder.container.removeAllViews()
            }
        }
        init {
            addView(recycler, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            recycler.layoutManager = manager
            recycler.adapter = rows
            recycler.itemAnimator = null
            isEnabled = false
            setOnRefreshListener { fire(this, "on_refresh") }
            recycler.addOnScrollListener(object : RecyclerView.OnScrollListener() {
                override fun onScrolled(view: RecyclerView, dx: Int, dy: Int) {
                    fire(this@ListView, "on_scroll", JSONObject().put("x", recycler.computeHorizontalScrollOffset() / PNBridge.density())
                        .put("y", recycler.computeVerticalScrollOffset() / PNBridge.density())
                        .put("extent", (if (horizontal) width else height) / PNBridge.density())
                        .put("range", (if (horizontal) recycler.computeHorizontalScrollRange() else recycler.computeVerticalScrollRange()) / PNBridge.density())
                        .put("first", manager.findFirstVisibleItemPosition()).put("last", manager.findLastVisibleItemPosition()))
                }
            })
        }
        fun attach(holder: Holder, item: Item) {
            val size = ((heights[item.key] ?: item.estimate) * PNBridge.density()).roundToInt().coerceAtLeast(1)
            // Preserve RecyclerView.LayoutParams, which retain the holder identity.
            val params = holder.container.layoutParams as? RecyclerView.LayoutParams
                ?: RecyclerView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, size)
            params.width = if (horizontal) size else ViewGroup.LayoutParams.MATCH_PARENT
            params.height = if (horizontal) ViewGroup.LayoutParams.MATCH_PARENT else size
            holder.container.layoutParams = params
            holder.container.removeAllViews()
            roots[item.key]?.let { root ->
                (root.parent as? ViewGroup)?.removeView(root)
                holder.container.addView(root, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
            }
        }
    }
    override fun createView(context: Context, tag: Long, props: JSONObject): View = ListView(context)
    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        ViewStyler.apply(view, props)
        val list = view as ListView
        val all = PNBridge.registry.recordFor(view)?.props ?: props
        list.horizontal = all.optBoolean("horizontal", false)
        list.manager.orientation = if (list.horizontal) RecyclerView.HORIZONTAL else RecyclerView.VERTICAL
        list.recycler.isVerticalScrollBarEnabled = all.optBoolean("shows_scroll_indicator", true)
        val refresh = all.optJSONObject("refresh_control")
        list.isEnabled = refresh != null && !list.horizontal
        list.isRefreshing = refresh?.optBoolean("refreshing", false) == true
        refresh?.optString("tint_color")?.takeIf { it.isNotEmpty() }?.let { color -> PNColor.parse(color)?.let { list.setColorSchemeColors(it) } }
        if (initial || props.has("keys") || props.has("revision") || props.has("row_heights")) {
            val keys = all.optJSONArray("keys")
            val heights = all.optJSONArray("row_heights")
            val items = (0 until (keys?.length() ?: 0)).map { Item(keys!!.getString(it), all.optInt("revision"), heights?.optDouble(it, 44.0) ?: 44.0) }
            val first = list.manager.findFirstVisibleItemPosition()
            val anchor = list.rows.currentList.getOrNull(first)?.key
            val anchorView = list.manager.findViewByPosition(first)
            val offset = (if (list.horizontal) anchorView?.left else anchorView?.top) ?: 0
            list.rows.submitList(items) {
                val position = items.indexOfFirst { it.key == anchor }
                if (position >= 0) list.manager.scrollToPositionWithOffset(position, offset)
            }
            list.heights.keys.retainAll(items.map { it.key }.toSet())
        }
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
                list.holders[key]?.let { holder -> list.rows.currentList.find { it.key == key }?.let { list.attach(holder, it) } }
            }
        }
        list.holders[key]?.let { holder -> list.rows.currentList.find { it.key == key }?.let { list.attach(holder, it) } }
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
    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray =
        floatArrayOf(if (maxWidth < 1e6) maxWidth.toFloat() else 0f, if (maxHeight < 1e6) maxHeight.toFloat() else 0f)
    override fun command(view: View, name: String, args: JSONObject): Any? {
        val list = view as ListView
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
