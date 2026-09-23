package com.pythonnative.runtime.components

import org.json.JSONArray
import org.json.JSONObject

/** Keyed metadata with atomic patch validation and constant-work row updates. */
internal class ListStore {
    data class Row(val key: String, val revision: Long, val extent: Double, val sticky: Boolean)
    data class Edit(val code: String, val from: Int, val to: Int)
    data class Patch(val base: Long, val revision: Long, val order: MutableList<String>?,
                     val changed: Map<String, Row>, val deleted: Set<String>, val reset: Boolean, val edits: List<Edit>)
    var revision = 0L; private set
    var keys: MutableList<String> = ArrayList(); private set
    val rows = HashMap<String, Row>()
    val indices = HashMap<String, Int>()
    var stickyIndices = emptyList<Int>(); private set

    fun prepare(packet: JSONObject): Patch {
        fun integer(value: Any): Long {
            require(value is Number && value.toDouble().isFinite() && kotlin.math.abs(value.toDouble()) <= 9007199254740991.0 && value.toDouble() == value.toLong().toDouble()) { "Invalid list integer" }
            return value.toLong()
        }
        fun row(value: Any): Row {
            require(value is JSONArray && value.length() == 4) { "Invalid list row" }
            val key = value.get(0); val version = integer(value.get(1)); val extent = value.get(2); val sticky = value.get(3)
            require(key is String && key.isNotEmpty() && version > 0 && extent is Number && extent.toDouble().isFinite() && extent.toDouble() > 0 && sticky is Boolean) { "Invalid list metadata" }
            return Row(key, version, extent.toDouble(), sticky)
        }
        require(packet.keys().asSequence().toSet() == setOf("base", "revision", "changes")) { "Invalid list packet" }
        require(integer(packet.get("base")) == revision && integer(packet.get("revision")) == revision + 1) { "Stale list revision" }
        val changes = packet.getJSONArray("changes")
        var order: MutableList<String>? = null
        val changed = HashMap<String, Row>(); val deleted = HashSet<String>(); val edits = ArrayList<Edit>()
        var reset = false
        fun exists(key: String) = key !in deleted && (key in changed || !reset && key in rows)
        fun editable(): MutableList<String> { if (order == null) order = keys.toMutableList(); return order!! }
        for (i in 0 until changes.length()) {
            val change = changes.getJSONArray(i)
            when (val code = change.getString(0)) {
                "reset" -> {
                    require(change.length() == 2 && edits.isEmpty() && changed.isEmpty() && !reset)
                    reset = true; order = ArrayList()
                    val values = change.getJSONArray(1)
                    for (j in 0 until values.length()) {
                        val item = row(values.get(j)); require(item.key !in changed) { "Duplicate list key" }
                        changed[item.key] = item; order!!.add(item.key)
                    }
                    edits.add(Edit(code, 0, 0))
                }
                "i" -> {
                    require(change.length() == 3)
                    val index = integer(change.get(1)); val item = row(change.get(2))
                    require(index >= 0 && index <= (order?.size ?: keys.size) && !exists(item.key)) { "Invalid list insertion" }
                    editable().add(index.toInt(), item.key); changed[item.key] = item; deleted.remove(item.key)
                    edits.add(Edit(code, index.toInt(), index.toInt()))
                }
                "u" -> {
                    require(change.length() == 2)
                    val item = row(change.get(1)); require(exists(item.key)) { "Unknown list update key" }
                    changed[item.key] = item
                }
                "d", "m" -> {
                    require(change.length() == if (code == "d") 2 else 3)
                    require(change.get(1) is String)
                    val key = change.getString(1); require(exists(key)) { "Unknown list key" }
                    val values = editable(); val old = values.indexOf(key); require(old >= 0)
                    if (code == "d") {
                        values.removeAt(old); changed.remove(key); deleted.add(key); edits.add(Edit(code, old, old))
                    } else {
                        val index = integer(change.get(2)); require(index >= 0 && index < values.size)
                        values.removeAt(old); values.add(index.toInt(), key); edits.add(Edit(code, old, index.toInt()))
                    }
                }
                else -> error("Unknown list change")
            }
        }
        return Patch(revision, revision + 1, order, changed, deleted, reset, edits)
    }
    fun publish(patch: Patch) {
        check(patch.base == revision)
        val stickyChanged = patch.changed.any { (key, row) -> rows[key]?.sticky != row.sticky }
        if (patch.reset) rows.clear()
        patch.deleted.forEach { rows.remove(it) }
        rows.putAll(patch.changed)
        patch.order?.let { order -> keys = order; indices.clear(); keys.forEachIndexed { index, key -> indices[key] = index } }
        if (patch.order != null || stickyChanged) stickyIndices = keys.indices.filter { rows[keys[it]]!!.sticky }
        revision = patch.revision
    }
    fun sticky(index: Int): Int {
        var low = 0; var high = stickyIndices.size
        while (low < high) {
            val mid = (low + high) / 2
            if (stickyIndices[mid] <= index) low = mid + 1 else high = mid
        }
        return if (low > 0) stickyIndices[low - 1] else -1
    }
}
