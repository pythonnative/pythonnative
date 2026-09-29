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
        var constraints = floatArrayOf()
        fun calculate(width: Float, height: Float) {
            val next = floatArrayOf(width, height)
            if (next.contentEquals(constraints) && !yoga.isDirty(yoga.ptr)) return
            yoga.calculate(yoga.ptr, width, height)
            constraints = next
        }
    }
    private val requestedFrames = HashSet<Long>()
    private val nodes = HashMap<Long, Entry>()
    private val portals = HashSet<Long>()
    private val detachedRoots = HashSet<Long>()
    private var viewport = JSONObject()
    private val detached = setOf("VirtualList", "Modal", "ScreenStack")
    private val containers = detached + setOf("View", "Row", "Column", "ScrollView", "Screen", "Portal")
    private var scheduled = false
    var visitedNodes = 0; private set
    var layoutNanos = 0L; private set

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
        requestedFrames.clear()
        nodes.clear()
        portals.clear()
        detachedRoots.clear()
        viewport = JSONObject()
    }

    fun parent(tag: Long): Long? = nodes[tag]?.parent
    fun children(tag: Long): List<Long> = nodes[tag]?.children?.toList() ?: emptyList()

    fun observe(ops: List<Op>) {
        for (op in ops) when (op) {
            is Op.Create -> {
                val entry = Entry(YogaNode(op.tag))
                nodes[op.tag] = entry
                if (op.typeName == "Portal") portals.add(op.tag)
                update(entry, op.props)
            }
            is Op.Update -> nodes[op.tag]?.let { update(it, op.changed, op.removed) }
            is Op.Insert -> {
                val parent = nodes[op.parent] ?: continue
                val child = nodes[op.child] ?: continue
                child.parent?.let { old -> nodes[old]?.let { previous ->
                    previous.children.remove(op.child)
                    if (child.attached) previous.yoga.remove(previous.yoga.ptr, child.yoga.ptr)
                } }
                child.parent = op.parent
                parent.children.add(op.index.coerceAtMost(parent.children.size), op.child)
                child.attached = PNBridge.registry.get(op.parent)?.typeName !in detached && !child.props.has("_pn_header_slot")
                if (child.attached) {
                    detachedRoots.remove(op.child)
                    parent.yoga.insert(parent.yoga.ptr, child.yoga.ptr, op.index)
                } else detachedRoots.add(op.child)
            }
            is Op.Destroy -> nodes.remove(op.tag)?.let { child ->
                requestedFrames.remove(op.tag)
                portals.remove(op.tag)
                detachedRoots.remove(op.tag)
                child.parent?.let { old -> nodes[old]?.let { parent ->
                    parent.children.remove(op.tag)
                    if (child.attached) parent.yoga.remove(parent.yoga.ptr, child.yoga.ptr)
                } }
                child.yoga.close()
            }
            is Op.Frame -> Unit
        }
    }

    private fun update(entry: Entry, changed: JSONObject, removed: List<String> = emptyList()) {
        for (key in changed.keys()) {
            if (changed.isNull(key)) entry.props.remove(key) else entry.props.put(key, changed.get(key))
        }
        for (key in removed) entry.props.remove(key)
        val yoga = entry.yoga
        val type = PNBridge.registry.get(yoga.tag)?.typeName
        if (changed.optBoolean("_pn_layout", false)) requestedFrames.add(yoga.tag)
        val touched = changed.keys().asSequence().toSet() + removed
        if (type != null && entry.frame.isNotEmpty() && com.pythonnative.generated.PNContracts.changes(type, touched) and com.pythonnative.generated.PNContracts.LAYOUT == 0) return
        val direct = touched.toMutableSet()
        for (family in listOf("margin", "padding")) if (touched.any { it == family || it.startsWith("${family}_") }) {
            val resolved = HashMap<String, Any>()
            val value = entry.props.opt(family)
            if (value is JSONObject) for (edge in value.keys()) resolved[if (edge == "all") family else "${family}_$edge"] = value.get(edge)
            else if (value != null && value != JSONObject.NULL) resolved[family] = value
            for (edge in listOf("left", "top", "right", "bottom", "start", "end", "horizontal", "vertical")) {
                val key = "${family}_$edge"
                entry.props.opt(key)?.let { resolved[key] = it }
            }
            for (suffix in listOf("", "_left", "_top", "_right", "_bottom", "_start", "_end", "_horizontal", "_vertical")) {
                val key = family + suffix
                yoga.style(yoga.ptr, key, resolved[key]?.toString() ?: "")
                direct.remove(key)
            }
        }
        if ("gap" in touched || "spacing" in touched) {
            val value = entry.props.opt("gap") ?: entry.props.opt("spacing")
            yoga.style(yoga.ptr, "gap", value?.toString() ?: "")
            direct.remove("gap"); direct.remove("spacing")
        }
        for (key in direct) yoga.style(yoga.ptr, key, entry.props.opt(key)?.toString() ?: "")
        if (type in setOf("ScrollView", "VirtualList", "ScreenStack") && !entry.props.has("flex_shrink")) yoga.style(yoga.ptr, "flex_shrink", "1")
        yoga.measureLeaf(yoga.ptr, entry.children.isEmpty() && type !in containers)
    }

    fun compute(request: JSONObject): JSONArray {
        val started = System.nanoTime()
        visitedNodes = 0
        viewport = request
        val width = request.optDouble("width").toFloat()
        val height = request.optDouble("height").toFloat()
        if (!width.isFinite() || !height.isFinite() || width <= 0 || height <= 0) return JSONArray()
        val roots = request.optJSONArray("roots") ?: JSONArray()
        val rootTags = (0 until roots.length()).map { roots.getLong(it) }.toSet()
        for (tag in rootTags) nodes[tag]?.calculate(width, height)
        // Portals have no on-screen parent. Their own Yoga node supplies the
        // viewport for all children, including absolute insets and sibling layout.
        for (tag in portals) {
            val entry = nodes[tag] ?: continue
            val record = PNBridge.registry.get(tag) ?: continue
            val containerWidth = record.view.width / PNBridge.density()
            val containerHeight = record.view.height / PNBridge.density()
            val portalWidth = if (containerWidth > 0) containerWidth else width
            val portalHeight = if (containerHeight > 0) containerHeight else height
            entry.yoga.style(entry.yoga.ptr, "width", portalWidth.toString())
            entry.yoga.style(entry.yoga.ptr, "height", portalHeight.toString())
            entry.calculate(portalWidth, portalHeight)
        }
        for (tag in detachedRoots) {
            val entry = nodes[tag] ?: continue
            val parent = PNBridge.registry.get(entry.parent!!)
            val record = PNBridge.registry.get(entry.yoga.tag)
            val container = if (record?.typeName == "Screen") record.view else parent?.view
            val availableWidth = (container?.width ?: 0) / PNBridge.density()
            val availableHeight = (container?.height ?: 0) / PNBridge.density()
            if (entry.props.has("_pn_header_slot")) {
                entry.calculate(Float.NaN, 44f)
                continue
            }
            val isList = parent?.typeName == "VirtualList"
            val horizontal = parent?.props?.optBoolean("horizontal", false) ?: false
            entry.calculate(if (isList && horizontal) Float.NaN else if (availableWidth > 0) availableWidth else width,
                if (isList && !horizontal) Float.NaN else if (availableHeight > 0) availableHeight else height)
        }
        val frames = JSONArray()
        fun collect(tag: Long) {
            val entry = nodes[tag] ?: return
            if (!entry.yoga.takeNewLayout(entry.yoga.ptr)) return
            visitedNodes += 1
            val frame = entry.yoga.frame(entry.yoga.ptr)
            if (!frame.contentEquals(entry.frame)) {
                entry.frame = frame
                if (tag !in rootTags) PNBridge.registry.get(tag)?.let { record ->
                    record.frame = frame.map { it.toDouble() }.toDoubleArray()
                    record.manager.setFrame(record.view, frame[0].toDouble(), frame[1].toDouble(), frame[2].toDouble(), frame[3].toDouble())
                }
                com.pythonnative.runtime.components.VirtualListManager.measured(tag, frame[2].toDouble(), frame[3].toDouble())
                if (!request.optBoolean("selective", false) || entry.props.optBoolean("_pn_layout", false)) frames.put(JSONArray().put(tag).put(frame[0]).put(frame[1]).put(frame[2]).put(frame[3]))
                requestedFrames.remove(tag)
            }
            for (child in entry.children) if (nodes[child]?.attached == true) collect(child)
        }
        for (tag in rootTags + portals + detachedRoots) collect(tag)
        for (tag in requestedFrames) nodes[tag]?.let { entry ->
            if (entry.frame.isNotEmpty() && entry.props.optBoolean("_pn_layout", false)) {
                val frame = entry.frame
                frames.put(JSONArray().put(tag).put(frame[0]).put(frame[1]).put(frame[2]).put(frame[3]))
            }
        }
        requestedFrames.clear()
        layoutNanos = System.nanoTime() - started
        return frames
    }

    fun invalidate(tag: Long) {
        val entry = nodes[tag] ?: return
        if (entry.children.isNotEmpty()) return
        entry.yoga.measureLeaf(entry.yoga.ptr, true)
        containerDidLayout()
    }
}
