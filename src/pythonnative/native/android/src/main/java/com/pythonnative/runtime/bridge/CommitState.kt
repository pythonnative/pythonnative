package com.pythonnative.runtime.bridge

import org.json.JSONArray
import org.json.JSONObject

/** Revision and structural validation before native mutation. */
class CommitState {
    private var application = ""
    private var surface = 0
    private var revision = 0
    private var live = mutableSetOf<Long>()
    private var parents = mutableMapOf<Long, Long>()
    private var childCounts = mutableMapOf<Long, Int>()
    private var types = mutableMapOf<Long, String>()
    private var failed = false

    /**
     * The identity of the commit being applied, while its operations run.
     * A view that emits during its own creation (an image starting to
     * load, a text input reporting its selection) belongs to that commit's
     * revision; stamping it with the previous one would make Python drop
     * the event as older than the view.
     */
    private var applying: Triple<String, Int, Int>? = null

    /** Run `block` with events stamped as belonging to the commit (`app`, `target`, `next`). */
    internal fun <T> stampedAs(app: String, target: Int, next: Int, block: () -> T): T {
        applying = Triple(app, target, next)
        try {
            return block()
        } finally {
            applying = null
        }
    }

    private var sequence = 0L
    @Synchronized fun event(args: JSONArray, editRevision: Long = 0): String {
        val (app, target, rev) = applying ?: Triple(application, surface, revision)
        return JSONObject()
            .put("application", app).put("surface", target).put("revision", rev)
            .put("sequence", ++sequence).put("args", args).put("edit_revision", editRevision).toString()
    }

    fun layout(frames: JSONArray): JSONObject = JSONObject().put("application", application)
        .put("surface", surface).put("revision", revision).put("frames", frames)
        .put("metrics", JSONObject().put("layout_ns", com.pythonnative.runtime.layout.NativeLayout.layoutNanos)
            .put("visited", com.pythonnative.runtime.layout.NativeLayout.visitedNodes))

    fun apply(json: String, applier: TransactionApplier): String = try {
        apply(JSONObject(json), applier)
    } catch (error: Exception) {
        JSONObject().put("ok", false).put("failed", false).put("error", error.message).toString()
    }

    fun apply(envelope: JSONObject, applier: TransactionApplier): String {
        val prepareStarted = System.nanoTime()
        try {
            val app = envelope.getString("application")
            val target = envelope.getInt("surface")
            val next = envelope.getInt("revision")
            require(envelope.getInt("version") == 4 && app.isNotEmpty() && target > 0) { "invalid v4 envelope" }
            val replacing = app != application
            require(next == (if (replacing) 1 else revision + 1)) { "stale revision" }
            require(replacing || (!failed && target == surface)) { "failed or foreign surface" }
            val raw = envelope.getJSONArray("ops")
            val structural = replacing || (0 until raw.length()).any { raw.getJSONArray(it).getString(0) in setOf("c", "i", "d") }
            val tags = if (replacing) mutableSetOf() else if (structural) live.toMutableSet() else live
            val links = if (replacing) mutableMapOf() else if (structural) parents.toMutableMap() else parents
            val names = if (replacing) mutableMapOf() else if (structural) types.toMutableMap() else types
            val counts = if (replacing) mutableMapOf() else if (structural) childCounts.toMutableMap() else childCounts
            val ops = ArrayList<Op>()
            val listPatches = HashSet<Long>()
            for (i in 0 until raw.length()) {
                val parts = raw.getJSONArray(i)
                val code = parts.getString(0)
                require(parts.length() == mapOf("c" to 4, "u" to 4, "i" to 4, "d" to 2, "f" to 6)[code]) { "invalid operation" }
                val tag = parts.getLong(1)
                require(tag > 0 && parts.getDouble(1) == tag.toDouble()) { "invalid tag" }
                if (code == "c") {
                    require(tags.add(tag) && parts.getString(2).isNotEmpty()) { "duplicate create" }
                    parts.getJSONObject(3)
                    require(PNRegistry.managerFor(parts.getString(2)) != null) { "unknown component" }
                    require(com.pythonnative.generated.PNContracts.validate(parts.getString(2), parts.getJSONObject(3))) { "invalid typed props" }
                    if (parts.getString(2) == "VirtualList") require(com.pythonnative.runtime.components.VirtualListManager.validateDataset(tag, parts.getJSONObject(3), true)) { "invalid list dataset" }
                    names[tag] = parts.getString(2)
                } else {
                    require(tag in tags) { "unknown tag" }
                    when (code) {
                        "u" -> {
                            val props = parts.getJSONObject(2)
                            val type = names[tag]
                            if (type == "VirtualList") require(com.pythonnative.runtime.components.VirtualListManager.validateDataset(tag, props, false)) { "invalid list dataset" }
                            val removed = parts.getJSONArray(3).let { list -> (0 until list.length()).map { list.getString(it) } }
                            require(type != null && com.pythonnative.generated.PNContracts.validateRemoval(type, props, removed)) { "invalid removal" }
                            require(type == null || com.pythonnative.generated.PNContracts.validate(type, props, true)) { "invalid typed update" }
                        }
                        "i" -> {
                            val child = parts.getLong(2)
                            require(child in tags && parts.getInt(3) >= 0) { "invalid insertion" }
                            var ancestor: Long? = tag
                            while (ancestor != null) {
                                require(ancestor != child) { "cycle" }
                                ancestor = links[ancestor]
                            }
                            require(parts.getInt(3) <= (counts[tag] ?: 0) - (if (links[child] == tag) 1 else 0)) { "insertion index exceeds child count" }
                            links[child]?.let { counts[it] = (counts[it] ?: 1) - 1 }
                            counts[tag] = (counts[tag] ?: 0) + 1
                            links[child] = tag
                        }
                        "d" -> {
                            require((counts[tag] ?: 0) == 0) { "destroy children first" }
                            tags.remove(tag)
                            names.remove(tag)
                            links.remove(tag)?.let { counts[it] = (counts[it] ?: 1) - 1 }
                            counts.remove(tag)
                        }
                        "f" -> {
                            for (j in 2..5) require(parts.getDouble(j).isFinite()) { "invalid frame" }
                            require(parts.getDouble(4) >= 0 && parts.getDouble(5) >= 0) { "negative size" }
                        }
                    }
                }
                if (code in setOf("c", "u") && names[tag] == "VirtualList" && parts.getJSONObject(if (code == "c") 3 else 2).has("dataset")) {
                    require(listPatches.add(tag)) { "Multiple list patches in one commit" }
                }
                ops.add(PNTransaction.decodeOp(parts))
            }
            val layoutRequest = envelope.optJSONObject("layout")
            require(!envelope.has("layout") || layoutRequest != null) { "invalid layout request" }
            if (layoutRequest != null) {
                val roots = layoutRequest.getJSONArray("roots")
                require((0 until roots.length()).all { roots.getLong(it) in tags }) { "invalid layout roots" }
                for (dimension in listOf("width", "height")) require(layoutRequest.getDouble(dimension).let { it.isFinite() && it > 0 }) { "invalid layout size" }
            }
            val mutationStarted = System.nanoTime()
            try {
                if (replacing) {
                    for (tag in live) applier.applyOp(Op.Destroy(tag))
                    com.pythonnative.runtime.layout.NativeLayout.reset()
                }
                stampedAs(app, target, next) {
                    for (op in ops) applier.applyOp(op)
                    com.pythonnative.runtime.layout.NativeLayout.observe(ops)
                }
            } catch (error: Exception) {
                failed = true
                for (tag in tags) runCatching { applier.applyOp(Op.Destroy(tag)) }
                throw error
            }
            application = app
            surface = target
            revision = next
            live = tags
            parents = links
            types = names
            childCounts = counts
            val reply = JSONObject().put("ok", true).put("application", app)
                .put("surface", target).put("revision", next)
                .put("metrics", JSONObject().put("mutation_ns", System.nanoTime() - mutationStarted).put("prepare_ns", mutationStarted - prepareStarted))
            failed = true
            if (layoutRequest != null) reply.put("layout", layout(com.pythonnative.runtime.layout.NativeLayout.compute(layoutRequest)))
            failed = false
            return reply.toString()
        } catch (error: Exception) {
            return JSONObject().put("ok", false).put("error", error.message).put("failed", failed).toString()
        }
    }
}
