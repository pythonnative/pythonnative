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
        apply(JSONObject(json), applier).toString()
    } catch (error: Exception) {
        JSONObject().put("ok", false).put("failed", false).put("error", error.message).toString()
    }

    /**
     * Validate and mount one commit, returning the acknowledgement.
     *
     * Validation updates the live structural maps in place and records the
     * inverse of every change, so the work is proportional to the commit
     * rather than to the mounted tree. A rejected commit replays the
     * inverses in reverse order.
     */
    fun apply(envelope: JSONObject, applier: TransactionApplier): JSONObject {
        val prepareStarted = System.nanoTime()
        val undo = ArrayList<() -> Unit>()
        fun rollback() {
            for (index in undo.indices.reversed()) undo[index]()
            undo.clear()
        }
        fun setParent(child: Long, parent: Long?) {
            val old = parents[child]
            undo.add { if (old == null) parents.remove(child) else parents[child] = old }
            if (parent == null) parents.remove(child) else parents[child] = parent
        }
        fun adjustCount(tag: Long, delta: Int) {
            val old = childCounts[tag]
            undo.add { if (old == null) childCounts.remove(tag) else childCounts[tag] = old }
            childCounts[tag] = (old ?: 0) + delta
        }
        try {
            val app = envelope.getString("application")
            val target = envelope.getInt("surface")
            val next = envelope.getInt("revision")
            val version = com.pythonnative.generated.PNContracts.protocolVersion
            require(envelope.getInt("version") == version && app.isNotEmpty() && target > 0) { "invalid v$version envelope" }
            val replacing = app != application
            require(next == (if (replacing) 1 else revision + 1)) { "stale revision" }
            require(replacing || (!failed && target == surface)) { "failed or foreign surface" }
            val raw = envelope.getJSONArray("ops")
            val previous = if (replacing) Structure(live, parents, types, childCounts) else null
            if (previous != null) {
                undo.add { restore(previous) }
                restore(Structure(mutableSetOf(), mutableMapOf(), mutableMapOf(), mutableMapOf()))
            }
            val ops = ArrayList<Op>(raw.length())
            val listPatches = HashSet<Long>()
            for (i in 0 until raw.length()) {
                val parts = raw.getJSONArray(i)
                val code = parts.getString(0)
                require(parts.length() == OPERATION_LENGTHS[code]) { "invalid operation" }
                val tag = parts.getLong(1)
                require(tag > 0 && parts.getDouble(1) == tag.toDouble()) { "invalid tag" }
                if (code == "c") {
                    val type = parts.getString(2)
                    require(tag !in live && type.isNotEmpty()) { "duplicate create" }
                    val props = parts.getJSONObject(3)
                    require(PNRegistry.managerFor(type) != null) { "unknown component" }
                    require(com.pythonnative.generated.PNContracts.validate(type, props)) { "invalid typed props" }
                    if (type == "VirtualList") require(com.pythonnative.runtime.components.VirtualListManager.validateDataset(tag, props, true)) { "invalid list dataset" }
                    live.add(tag)
                    types[tag] = type
                    undo.add { live.remove(tag); types.remove(tag) }
                } else {
                    require(tag in live) { "unknown tag" }
                    when (code) {
                        "u" -> {
                            val props = parts.getJSONObject(2)
                            val type = types[tag]
                            if (type == "VirtualList") require(com.pythonnative.runtime.components.VirtualListManager.validateDataset(tag, props, false)) { "invalid list dataset" }
                            val removed = parts.getJSONArray(3).let { list -> (0 until list.length()).map { list.getString(it) } }
                            require(type != null && com.pythonnative.generated.PNContracts.validateRemoval(type, props, removed)) { "invalid removal" }
                            require(com.pythonnative.generated.PNContracts.validate(type, props, true)) { "invalid typed update" }
                        }
                        "i" -> {
                            val child = parts.getLong(2)
                            require(child in live && parts.getInt(3) >= 0) { "invalid insertion" }
                            var ancestor: Long? = tag
                            while (ancestor != null) {
                                require(ancestor != child) { "cycle" }
                                ancestor = parents[ancestor]
                            }
                            require(parts.getInt(3) <= (childCounts[tag] ?: 0) - (if (parents[child] == tag) 1 else 0)) { "insertion index exceeds child count" }
                            parents[child]?.let { adjustCount(it, -1) }
                            adjustCount(tag, 1)
                            setParent(child, tag)
                        }
                        "d" -> {
                            require((childCounts[tag] ?: 0) == 0) { "destroy children first" }
                            val type = types[tag]
                            val count = childCounts[tag]
                            live.remove(tag)
                            types.remove(tag)
                            childCounts.remove(tag)
                            undo.add {
                                live.add(tag)
                                if (type != null) types[tag] = type
                                if (count != null) childCounts[tag] = count
                            }
                            parents[tag]?.let {
                                adjustCount(it, -1)
                                setParent(tag, null)
                            }
                        }
                    }
                }
                if (code in setOf("c", "u") && types[tag] == "VirtualList" && parts.getJSONObject(if (code == "c") 3 else 2).has("dataset")) {
                    require(listPatches.add(tag)) { "Multiple list patches in one commit" }
                }
                ops.add(PNTransaction.decodeOp(parts))
            }
            val layoutRequest = envelope.optJSONObject("layout")
            require(!envelope.has("layout") || layoutRequest != null) { "invalid layout request" }
            if (layoutRequest != null) {
                val roots = layoutRequest.getJSONArray("roots")
                require((0 until roots.length()).all { roots.getLong(it) in live }) { "invalid layout roots" }
                for (dimension in listOf("width", "height")) require(layoutRequest.getDouble(dimension).let { it.isFinite() && it > 0 }) { "invalid layout size" }
            }
            val mutationStarted = System.nanoTime()
            try {
                if (previous != null) {
                    for (tag in previous.live) applier.applyOp(Op.Destroy(tag))
                    com.pythonnative.runtime.layout.NativeLayout.reset()
                }
                stampedAs(app, target, next) {
                    for (op in ops) applier.applyOp(op)
                    com.pythonnative.runtime.layout.NativeLayout.observe(ops)
                }
            } catch (error: Exception) {
                failed = true
                val candidate = live.toSet()
                rollback()
                for (tag in candidate + live) runCatching { applier.applyOp(Op.Destroy(tag)) }
                throw error
            }
            undo.clear()
            application = app
            surface = target
            revision = next
            val reply = JSONObject().put("ok", true).put("application", app)
                .put("surface", target).put("revision", next)
                .put("metrics", JSONObject().put("mutation_ns", System.nanoTime() - mutationStarted).put("prepare_ns", mutationStarted - prepareStarted))
            failed = true
            if (layoutRequest != null) reply.put("layout", layout(com.pythonnative.runtime.layout.NativeLayout.compute(layoutRequest)))
            failed = false
            return reply
        } catch (error: Exception) {
            rollback()
            return JSONObject().put("ok", false).put("error", error.message).put("failed", failed)
        }
    }

    /** The structural maps a replacing commit swaps out as a whole. */
    private class Structure(
        val live: MutableSet<Long>,
        val parents: MutableMap<Long, Long>,
        val types: MutableMap<Long, String>,
        val childCounts: MutableMap<Long, Int>,
    )

    private fun restore(structure: Structure) {
        live = structure.live
        parents = structure.parents
        types = structure.types
        childCounts = structure.childCounts
    }

    private companion object {
        val OPERATION_LENGTHS = mapOf("c" to 4, "u" to 4, "i" to 4, "d" to 2)
    }
}
