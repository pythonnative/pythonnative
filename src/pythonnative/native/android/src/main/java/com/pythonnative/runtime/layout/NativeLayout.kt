package com.pythonnative.runtime.layout

import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.Op
import org.json.JSONArray
import org.json.JSONObject

/** Native layout and measurement, with one result containing changed geometry. */
object NativeLayout {
    private class Entry(val yoga: YogaNode) {
        val props = JSONObject()
        val children = ArrayList<Long>()
        var parent: Long? = null
        var attached = false
        var frame = floatArrayOf()
    }
    private val nodes = HashMap<Long, Entry>()
    private var viewport = JSONObject()
    private val detached = setOf("VirtualList", "Modal", "Portal", "ScreenStack")
    private val containers = detached + setOf("View", "Row", "Column", "ScrollView", "Screen")
    private var scheduled = false

    fun containerDidLayout() {
        if (scheduled) return
        scheduled = true
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            scheduled = false
            val frames = compute(viewport)
            if (frames.length() > 0) PNBridge.callPython("layout", 0, "", frames.toString())
        }
    }

    fun reset() {
        for (entry in nodes.values) if (entry.attached) entry.parent?.let { parent ->
            nodes[parent]?.yoga?.let { it.remove(it.ptr, entry.yoga.ptr) }
        }
        for (entry in nodes.values) entry.yoga.close()
        nodes.clear()
        viewport = JSONObject()
    }

    fun parent(tag: Long): Long? = nodes[tag]?.parent

    fun observe(ops: List<Op>) {
        for (op in ops) when (op) {
            is Op.Create -> {
                val entry = Entry(YogaNode(op.tag))
                nodes[op.tag] = entry
                update(entry, op.props)
            }
            is Op.Update -> nodes[op.tag]?.let { update(it, op.changed) }
            is Op.Insert -> {
                val parent = nodes[op.parent] ?: continue
                val child = nodes[op.child] ?: continue
                child.parent?.let { old -> nodes[old]?.let { previous ->
                    previous.children.remove(op.child)
                    if (child.attached) previous.yoga.remove(previous.yoga.ptr, child.yoga.ptr)
                } }
                child.parent = op.parent
                parent.children.add(op.index.coerceAtMost(parent.children.size), op.child)
                child.attached = PNBridge.registry.get(op.parent)?.typeName !in detached
                if (child.attached) parent.yoga.insert(parent.yoga.ptr, child.yoga.ptr, op.index)
            }
            is Op.Destroy -> nodes.remove(op.tag)?.let { child ->
                child.parent?.let { old -> nodes[old]?.let { parent ->
                    parent.children.remove(op.tag)
                    if (child.attached) parent.yoga.remove(parent.yoga.ptr, child.yoga.ptr)
                } }
                child.yoga.close()
            }
            is Op.Frame -> Unit
        }
    }

    private fun update(entry: Entry, changed: JSONObject) {
        for (key in changed.keys()) {
            if (changed.isNull(key)) entry.props.remove(key) else entry.props.put(key, changed.get(key))
        }
        val yoga = entry.yoga
        yoga.resetStyle(yoga.ptr)
        for (key in entry.props.keys()) {
            val value = entry.props.get(key)
            if (value is JSONObject && key in setOf("margin", "padding")) {
                for (edge in value.keys()) yoga.style(yoga.ptr, if (edge == "all") key else "${key}_$edge", value.get(edge).toString())
            } else yoga.style(yoga.ptr, key, value.toString())
        }
        val type = PNBridge.registry.get(yoga.tag)?.typeName
        if (type in setOf("ScrollView", "VirtualList", "ScreenStack")) yoga.style(yoga.ptr, "flex_shrink", "1")
        yoga.measureLeaf(yoga.ptr, entry.children.isEmpty() && type !in containers)
    }

    fun compute(request: JSONObject): JSONArray {
        viewport = request
        val width = request.optDouble("width").toFloat()
        val height = request.optDouble("height").toFloat()
        val roots = request.optJSONArray("roots") ?: JSONArray()
        val rootTags = (0 until roots.length()).map { roots.getLong(it) }.toSet()
        for (tag in rootTags) nodes[tag]?.yoga?.let { it.calculate(it.ptr, width, height) }
        for (entry in nodes.values) if (entry.parent != null && !entry.attached) {
            val parent = PNBridge.registry.get(entry.parent!!)
            val record = PNBridge.registry.get(entry.yoga.tag)
            val container = if (record?.typeName == "Screen") record.view else parent?.view
            val availableWidth = (container?.width ?: 0) / PNBridge.density()
            val availableHeight = (container?.height ?: 0) / PNBridge.density()
            val isList = parent?.typeName == "VirtualList"
            val horizontal = parent?.props?.optBoolean("horizontal", false) ?: false
            entry.yoga.calculate(entry.yoga.ptr, if (isList && horizontal) Float.NaN else if (availableWidth > 0) availableWidth else width,
                if (isList && !horizontal) Float.NaN else if (availableHeight > 0) availableHeight else height)
        }
        val frames = JSONArray()
        for ((tag, entry) in nodes) {
            val frame = entry.yoga.frame(entry.yoga.ptr)
            if (frame.contentEquals(entry.frame)) continue
            entry.frame = frame
            if (tag !in rootTags) PNBridge.registry.get(tag)?.let { record ->
                record.frame = frame.map { it.toDouble() }.toDoubleArray()
                record.manager.setFrame(record.view, frame[0].toDouble(), frame[1].toDouble(), frame[2].toDouble(), frame[3].toDouble())
            }
            com.pythonnative.runtime.components.VirtualListManager.measured(tag, frame[2].toDouble(), frame[3].toDouble())
            frames.put(JSONArray().put(tag).put(frame[0]).put(frame[1]).put(frame[2]).put(frame[3]))
        }
        return frames
    }

    fun invalidate(tag: Long) {
        val entry = nodes[tag] ?: return
        if (entry.children.isNotEmpty()) return
        entry.yoga.measureLeaf(entry.yoga.ptr, true)
        PNBridge.callPython("layout", 0, "", compute(viewport).toString())
    }
}
