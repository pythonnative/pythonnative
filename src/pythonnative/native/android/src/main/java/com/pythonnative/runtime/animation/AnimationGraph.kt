package com.pythonnative.runtime.animation

import android.view.Choreographer
import com.pythonnative.runtime.PNBridge
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.*

/** Expressions and input bindings live on the UI thread, independent of Python. */
object AnimationGraph {
    private data class Graph(val nodes: List<JSONObject>, val bindings: JSONArray)
    private val graphs = HashMap<Long, Graph>()
    private val values = HashMap<Long, Double>()
    private val previous = HashMap<Long, Double>()
    private val output = HashMap<Long, Any>()
    private val membership = HashMap<Long, MutableSet<Long>>()
    private val pending = HashSet<Long>()
    private var scheduled = false
    private val applied = HashMap<Pair<Long, String>, Pair<Int, Any>>()
    var evaluatedNodes = 0; private set
    var evaluatedGraphs = 0; private set
    var frameCount = 0; private set
    private val frameCallback = Choreographer.FrameCallback {
        scheduled = false
        flushFrame()
    }

    fun flushFrame() {
        if (pending.isEmpty()) return
        val changed = pending.toSet()
        pending.clear()
        frameCount++
        evaluate(changed)
    }

    fun setFrame(id: Long, value: Double) {
        if (!value.isFinite() || values[id] == value) return
        values[id] = value
        pending.add(id)
        if (!scheduled) {
            scheduled = true
            Choreographer.getInstance().postFrameCallback(frameCallback)
        }
    }

    fun install(spec: JSONObject) {
        val id = spec.getLong("id")
        val bindings = spec.getJSONArray("bindings")
        val raw = spec.getJSONArray("nodes")
        val nodes = (0 until raw.length()).map { raw.getJSONObject(it) }
        val ids = nodes.map { it.getLong("id") }.toSet()
        graphs.entries.removeAll { (_, graph) -> graph.nodes.any { it.getLong("id") in ids } }
        if (bindings.length() == 0) { collect(); return }
        for (node in nodes) {
            val key = node.getLong("id")
            values.putIfAbsent(key, node.optDouble("value", 0.0))
            previous.putIfAbsent(key, node.optDouble("previous", 0.0))
        }
        graphs[id] = Graph(nodes, bindings)
        collect()
        evaluate()
    }
    fun value(id: Long): Double = values[id] ?: 0.0
    fun set(id: Long, value: Double) { if (value.isFinite() && values[id] != value) { values[id] = value; evaluate(setOf(id)) } }
    fun event(tag: Long, name: String, args: JSONArray) {
        val payload = args.optJSONObject(0) ?: return
        val props = PNBridge.registry.get(tag)?.props ?: return
        val fields = if (name.startsWith("gesture:")) {
            val index = name.removePrefix("gesture:").toIntOrNull() ?: return
            props.optJSONArray("gestures")?.optJSONObject(index)?.optJSONObject("animated_events")?.optJSONObject(payload.optString("state"))
        } else props.optJSONObject("_pn_animated_events")?.optJSONObject(name)
        if (fields == null) return
        val changed = HashSet<Long>()
        for (field in fields.keys()) if (payload.opt(field) is Number) {
            val id = fields.getLong(field); val value = payload.getDouble(field)
            if (value.isFinite() && values[id] != value) { values[id] = value; changed.add(id) }
        }
        evaluate(changed)
    }
    fun forget(tag: Long) {
        applied.keys.removeAll { it.first == tag }
        for ((id, graph) in graphs.toMap()) {
            val kept = JSONArray()
            for (i in 0 until graph.bindings.length()) if (graph.bindings.getJSONArray(i).getLong(0) != tag) kept.put(graph.bindings.getJSONArray(i))
            if (kept.length() == 0) graphs.remove(id) else graphs[id] = Graph(graph.nodes, kept)
        }
        collect()
    }
    private fun collect() {
        membership.clear()
        for ((graphID, graph) in graphs) for (node in graph.nodes) membership.getOrPut(node.getLong("id")) { HashSet() }.add(graphID)
        val live = graphs.values.flatMap { it.nodes }.map { it.getLong("id") }.toSet()
        values.keys.retainAll(live); previous.keys.retainAll(live); output.keys.retainAll(live)
        pending.retainAll(live)
        if (pending.isEmpty() && scheduled) {
            Choreographer.getInstance().removeFrameCallback(frameCallback)
            scheduled = false
        }
    }
    private fun input(node: JSONObject): Double = if (node.has("node")) values[node.getLong("node")] ?: 0.0 else node.optDouble("constant", 0.0)
    private fun evaluate(changed: Set<Long>? = null) {
        val affected = changed?.flatMap { membership[it] ?: emptySet() }?.toSet() ?: graphs.keys
        for (graphID in affected) {
            val graph = graphs[graphID] ?: continue
            evaluatedGraphs++
            val dirty = changed?.toMutableSet() ?: graph.nodes.map { it.getLong("id") }.toMutableSet()
            for (node in graph.nodes) {
                val id = node.getLong("id")
                val raw = node.optJSONArray("inputs") ?: JSONArray()
                if (id !in dirty && (0 until raw.length()).none { raw.getJSONObject(it).optLong("node") in dirty }) continue
                dirty.add(id)
                evaluatedNodes++
                val inputs = (0 until raw.length()).map { input(raw.getJSONObject(it)) }
                val a = inputs.getOrElse(0) { 0.0 }; val b = inputs.getOrElse(1) { 0.0 }
                val value = when (node.getString("kind")) {
                    "value" -> values[id] ?: 0.0
                    "add" -> a + b; "subtract" -> a - b; "multiply" -> a * b
                    "divide" -> if (b == 0.0) 0.0 else a / b
                    "modulo" -> if (b == 0.0) 0.0 else a % b
                    "negate" -> -a
                    "diff_clamp" -> {
                        val next = ((values[id] ?: 0.0) + a - (previous[id] ?: a)).coerceIn(node.getDouble("minimum"), node.getDouble("maximum"))
                        previous[id] = a; next
                    }
                    "interpolate" -> interpolate(node, a, id)
                    else -> 0.0
                }
                values[id] = if (value.isFinite()) value else 0.0
                if (!node.optBoolean("color")) output[id] = values[id]!!
            }
            for (i in 0 until graph.bindings.length()) {
                val binding = graph.bindings.getJSONArray(i)
                val record = PNBridge.registry.get(binding.getLong(0)) ?: continue
                val value = output[binding.getLong(2)] ?: continue
                val key = record.tag to binding.getString(1)
                val state = System.identityHashCode(record.view) to value
                if (applied[key] == state) continue
                applied[key] = state
                record.manager.setAnimatedProperty(record.view, key.second, value)
            }
        }
    }
    private fun interpolate(node: JSONObject, input: Double, id: Long): Double {
        val ranges = node.getJSONArray("ranges"); val outputs = node.getJSONArray("outputs")
        val first = ranges.getDouble(0); val last = ranges.getDouble(ranges.length() - 1)
        var x = input
        val mode = if (x < first) node.getString("left") else if (x > last) node.getString("right") else "extend"
        if (mode == "identity") return x
        if (mode == "clamp") x = x.coerceIn(first, last)
        var index = 0
        while (index < ranges.length() - 2 && x >= ranges.getDouble(index + 1)) index++
        val span = ranges.getDouble(index + 1) - ranges.getDouble(index)
        val t = if (span == 0.0) 0.0 else (x - ranges.getDouble(index)) / span
        if (node.optBoolean("color")) {
            val from = outputs.getJSONArray(index); val to = outputs.getJSONArray(index + 1)
            val channels = (0..3).map { (from.getDouble(it) + (to.getDouble(it) - from.getDouble(it)) * t.coerceIn(0.0, 1.0)).roundToInt().coerceIn(0, 255) }
            output[id] = "#" + channels.joinToString("") { "%02X".format(it) }
            return 0.0
        }
        return outputs.getDouble(index) + (outputs.getDouble(index + 1) - outputs.getDouble(index)) * t
    }
}
