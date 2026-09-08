package com.pythonnative.runtime.bridge

import android.view.View
import com.pythonnative.runtime.components.ComponentManager
import org.json.JSONArray
import org.json.JSONObject
import java.util.IdentityHashMap

/**
 * Per-view bookkeeping: the reconciler tag, the element type, the
 * manager that owns it, the merged props, and free-form manager state.
 */
class ViewRecord(
    val tag: Long,
    val typeName: String,
    val view: View,
    val manager: ComponentManager,
) {
    /** Every prop applied so far (removed props stay as JSON null). */
    val props = JSONObject()

    /** Manager-private state (suppress flags, wrapped widgets, etc.). */
    val state = HashMap<String, Any?>()

    /** Last frame applied by `setFrame`, in dp (`x, y, w, h`). */
    var frame: DoubleArray? = null

    /** Whether the initial props have been applied. */
    var initialized = false

    /** Whether the element wired a callback named `name` this render. */
    fun hasEvent(name: String): Boolean {
        val events = props.opt("_pn_events") as? JSONArray ?: return false
        for (i in 0 until events.length()) {
            if (events.optString(i) == name) return true
        }
        return false
    }
}

/** Tag to [ViewRecord] map with a reverse index by view identity. */
class ViewRegistry {
    private val byTag = HashMap<Long, ViewRecord>()
    private val byView = IdentityHashMap<View, ViewRecord>()

    /** Number of live records. */
    val size: Int get() = byTag.size

    /** Register `record`; replaces any earlier record with the same tag. */
    fun register(record: ViewRecord) {
        byTag.remove(record.tag)?.let { byView.remove(it.view) }
        byTag[record.tag] = record
        byView[record.view] = record
    }

    /** Remove and return the record for `tag`. */
    fun unregister(tag: Long): ViewRecord? {
        val record = byTag.remove(tag) ?: return null
        byView.remove(record.view)
        return record
    }

    /** The record for `tag`, or `null`. */
    fun get(tag: Long): ViewRecord? = byTag[tag]

    /** The record whose view is `view`, or `null`. */
    fun recordFor(view: View): ViewRecord? = byView[view]

    /** The tag of `view`, or `null` when it is not a PythonNative view. */
    fun tagOf(view: View): Long? = byView[view]?.tag

    /** Snapshot of all records. */
    fun all(): List<ViewRecord> = ArrayList(byTag.values)
}
