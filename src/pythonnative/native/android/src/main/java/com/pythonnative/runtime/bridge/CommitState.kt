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
    private var types = mutableMapOf<Long, String>()
    private var failed = false

    private var sequence = 0L
    @Synchronized fun event(args: JSONArray, editRevision: Long = 0): String = JSONObject()
        .put("application", application).put("surface", surface).put("revision", revision)
        .put("sequence", ++sequence).put("args", args).put("edit_revision", editRevision).toString()

    fun apply(json: String, applier: TransactionApplier): String {
        try {
            val envelope = JSONObject(json)
            val app = envelope.getString("application")
            val target = envelope.getInt("surface")
            val next = envelope.getInt("revision")
            require(envelope.getInt("version") == 2 && app.isNotEmpty() && target > 0) { "invalid v2 envelope" }
            val replacing = app != application
            require(next == (if (replacing) 1 else revision + 1)) { "stale revision" }
            require(replacing || (!failed && target == surface)) { "failed or foreign surface" }
            val tags = if (replacing) mutableSetOf() else live.toMutableSet()
            val links = if (replacing) mutableMapOf() else parents.toMutableMap()
            val names = if (replacing) mutableMapOf() else types.toMutableMap()
            val raw = envelope.getJSONArray("ops")
            val ops = ArrayList<Op>()
            for (i in 0 until raw.length()) {
                val parts = raw.getJSONArray(i)
                val code = parts.getString(0)
                require(parts.length() == mapOf("c" to 4, "u" to 3, "i" to 4, "d" to 2, "f" to 6)[code]) { "invalid operation" }
                val tag = parts.getLong(1)
                require(tag > 0 && parts.getDouble(1) == tag.toDouble()) { "invalid tag" }
                if (code == "c") {
                    require(tags.add(tag) && parts.getString(2).isNotEmpty()) { "duplicate create" }
                    parts.getJSONObject(3)
                    require(PNRegistry.managerFor(parts.getString(2)) != null) { "unknown component" }
                    require(com.pythonnative.generated.PNContracts.validate(parts.getString(2), parts.getJSONObject(3))) { "invalid typed props" }
                    names[tag] = parts.getString(2)
                } else {
                    require(tag in tags) { "unknown tag" }
                    when (code) {
                        "u" -> {
                            val props = parts.getJSONObject(2)
                            val type = names[tag]
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
                            require(parts.getInt(3) <= links.count { (key, value) -> value == tag && key != child }) { "insertion index exceeds child count" }
                            links[child] = tag
                        }
                        "d" -> {
                            require(tag !in links.values) { "destroy children first" }
                            tags.remove(tag)
                            names.remove(tag)
                            links.remove(tag)
                        }
                        "f" -> {
                            for (j in 2..5) require(parts.getDouble(j).isFinite()) { "invalid frame" }
                            require(parts.getDouble(4) >= 0 && parts.getDouble(5) >= 0) { "negative size" }
                        }
                    }
                }
                ops.add(PNTransaction.decodeOp(parts))
            }
            try {
                if (replacing) {
                    for (tag in live) applier.applyOp(Op.Destroy(tag))
                    com.pythonnative.runtime.layout.NativeLayout.reset()
                }
                for (op in ops) applier.applyOp(op)
                com.pythonnative.runtime.layout.NativeLayout.observe(ops)
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
            failed = false
            return JSONObject().put("ok", true).put("application", app)
                .put("surface", target).put("revision", next).toString()
        } catch (error: Exception) {
            return JSONObject().put("ok", false).put("error", error.message).toString()
        }
    }
}
