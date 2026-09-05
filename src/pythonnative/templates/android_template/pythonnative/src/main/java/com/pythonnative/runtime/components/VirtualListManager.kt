package com.pythonnative.runtime.components

import android.content.Context
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.arr
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.views.PNVirtualListView
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.max

/**
 * `VirtualList` element: a `RecyclerView` (via [PNVirtualListView])
 * whose rows are rendered lazily by Python.
 *
 * Binding a row is a synchronous round trip: `on_bind_row` is sent with
 * `{container, index, width, height}` (the container key is its
 * identity hash) and Python answers `{"root": tag}`; the tag's view is
 * detached from any previous parent and added to the row container.
 * Recycling emits `on_unbind_row` with the same key.
 */
class VirtualListManager : ComponentManager() {
    private class Info {
        var count = 0
        var rowHeight = 44.0
        var rowHeights: JSONArray? = null
        var list: PNVirtualListView? = null
        val mounted = HashMap<Int, View>()
    }

    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val info = Info()
        info.count = JsonUtil.toInt(props.value("count"))
        info.rowHeight = props.num("row_height") ?: 44.0
        info.rowHeights = props.arr("row_heights")
        val delegate = object : PNVirtualListView.Delegate {
            override fun getCount(): Int = info.count

            override fun getRowHeightDp(position: Int): Float {
                val heights = info.rowHeights
                if (heights != null && position in 0 until heights.length()) {
                    return JsonUtil.toDouble(heights.opt(position), info.rowHeight).toFloat()
                }
                return info.rowHeight.toFloat()
            }

            override fun bindRow(position: Int, container: FrameLayout, widthDp: Float, heightDp: Float) {
                val list = info.list ?: return
                val key = System.identityHashCode(container)
                val payload = JSONObject()
                    .put("container", key)
                    .put("index", position)
                    .put("width", widthDp.toDouble())
                    .put("height", heightDp.toDouble())
                val reply = fireForResult(list, "on_bind_row", payload) ?: return
                val rootTag = try {
                    JSONObject(reply).optLong("root", -1L)
                } catch (e: Exception) {
                    PNLog.rateLimited("vlist-bind", "on_bind_row returned invalid JSON: $reply", e)
                    return
                }
                if (rootTag < 0) return
                val root = PNBridge.registry.get(rootTag)?.view ?: run {
                    PNLog.rateLimited("vlist-root", "on_bind_row root tag $rootTag is unknown")
                    return
                }
                (root.parent as? ViewGroup)?.let { if (it !== container) it.removeView(root) }
                if (root.parent !== container) {
                    container.addView(root, 0)
                }
                // The layout engine frames only the descendants of a subtree
                // root, so the root itself must fill the cell.
                root.layoutParams = FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                )
                info.mounted[key] = root
            }

            override fun onRowPress(position: Int) {
                info.list?.let { fire(it, "on_row_press", position) }
            }

            override fun onRowRecycled(container: FrameLayout) {
                val list = info.list ?: return
                val key = System.identityHashCode(container)
                info.mounted.remove(key)
                fire(list, "on_unbind_row", JSONObject().put("container", key))
            }

            override fun onScrolled(offsetDp: Float, extentDp: Float, rangeDp: Float) {
                val list = info.list ?: return
                if (!hasEvent(list, "on_scroll")) return
                fire(
                    list,
                    "on_scroll",
                    mapOf(
                        "x" to 0.0,
                        "y" to offsetDp.toDouble(),
                        "extent" to extentDp.toDouble(),
                        "range" to rangeDp.toDouble(),
                    ),
                )
            }
        }
        val list = PNVirtualListView(context, delegate)
        info.list = list
        infos[list] = info
        return list
    }

    private val infos = java.util.IdentityHashMap<View, Info>()

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        ViewStyler.apply(view, props)
        val list = view as PNVirtualListView
        val info = infos[list] ?: return
        var dataChanged = false
        if (props.has("count")) {
            info.count = JsonUtil.toInt(props.value("count"))
            dataChanged = true
        }
        props.num("row_height")?.let {
            info.rowHeight = it
            dataChanged = true
        }
        if (props.has("row_heights")) {
            info.rowHeights = props.arr("row_heights")
            dataChanged = true
        }
        if (props.has("shows_scroll_indicator")) {
            list.isVerticalScrollBarEnabled = props.value("shows_scroll_indicator") != false
        }
        if (dataChanged && !initial) list.notifyDataChanged()
    }

    override fun insertChild(parent: View, child: View, index: Int) {
        // Row roots are attached through the bind protocol, not the tree ops.
    }

    override fun removeChild(parent: View, child: View) {
        (child.parent as? ViewGroup)?.removeView(child)
    }

    override fun teardown(view: View) {
        val info = infos.remove(view) ?: return
        info.mounted.clear()
        info.list = null
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        // Fill the available space; collapse to 0 on an unbounded axis
        // (nested inside another scroll view), like React Native.
        val w = if (maxWidth.isFinite() && maxWidth < 1e6) maxWidth else 0.0
        val h = if (maxHeight.isFinite() && maxHeight < 1e6) maxHeight else 0.0
        return floatArrayOf(max(0.0, w).toFloat(), max(0.0, h).toFloat())
    }

    override fun command(view: View, name: String, args: JSONObject): Any? {
        val list = view as PNVirtualListView
        val animated = args.value("animated") != false
        when (name) {
            "scroll_to_offset" -> list.scrollToOffsetDp(JsonUtil.toDouble(args.opt("y")).toFloat(), animated)
            "scroll_to_index" -> list.scrollToIndex(JsonUtil.toInt(args.opt("index")), animated)
            "scroll_to_end" -> {
                val count = infos[list]?.count ?: 0
                list.scrollToIndex(max(0, count - 1), animated)
            }
            "get_scroll_offset" -> return mapOf("x" to 0.0, "y" to dp(list.computeVerticalScrollOffset()))
        }
        return null
    }
}
