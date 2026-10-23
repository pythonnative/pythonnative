package com.pythonnative.runtime.mount

import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import com.pythonnative.generated.PNValues
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.bridge.ViewRegistry
import com.pythonnative.runtime.components.VirtualListManager
import com.pythonnative.runtime.core.PNCore
import com.pythonnative.runtime.gestures.TouchForwarder
import com.pythonnative.runtime.layout.Measurement
import org.json.JSONObject
import java.nio.ByteBuffer

/**
 * Applies the core's mount transactions to platform views, on the main
 * thread. The core has already validated, diffed, flattened, and laid out
 * the tree; an op that still fails here fails the surface.
 */
class Mounter(private val registry: ViewRegistry) {
    /** Apply one transaction from the core and acknowledge it. */
    fun mount(buffer: ByteBuffer) {
        val id = MountDecoder.idOf(buffer)
        val error = try {
            apply(MountDecoder.decode(buffer))
            null
        } catch (failure: Exception) {
            Log.e(PNBridge.TAG, "mount transaction $id failed", failure)
            failure.message ?: failure.toString()
        }
        PNCore.mountFinished(id, error)
        PNCore.applyWrites()
    }

    /** Apply every op of `transaction` in order; the first failure stops it. */
    fun apply(transaction: MountTransaction) {
        for (op in transaction.ops) applyOp(op)
    }

    /**
     * Apply a single op. A generated prop getter that can't decode its value
     * records the failure ([PNValues.decodeOrRecord]) and reads as null; the
     * op that read it then fails the transaction.
     */
    fun applyOp(op: MountOp) {
        PNValues.takeDecodeFailure()
        when (op) {
            MountOp.Reset -> reset()
            is MountOp.Create -> create(op.tag, op.typeName, op.props)
            is MountOp.Update -> update(op)
            is MountOp.Insert -> insert(op)
            is MountOp.Delete -> registry.get(op.tag)?.let { delete(it) }
            is MountOp.Frame -> frame(op)
            is MountOp.Command -> command(op)
        }
        PNValues.takeDecodeFailure()?.let { failure ->
            val tag = when (op) {
                is MountOp.Create -> op.tag
                is MountOp.Update -> op.tag
                is MountOp.Insert -> op.parent
                is MountOp.Command -> op.tag
                else -> 0L
            }
            val type = (op as? MountOp.Create)?.typeName ?: registry.get(tag)?.typeName ?: "view"
            throw IllegalStateException("props for $type tag $tag: $failure")
        }
    }

    private fun reset() {
        for (record in registry.all()) {
            TouchForwarder.unbind(record)
            (record.view.parent as? ViewGroup)?.removeView(record.view)
            try { record.manager.destroy(record.view) } catch (error: Exception) { Log.d(PNBridge.TAG, "destroy failed", error) }
            registry.unregister(record.tag)
        }
    }

    private fun create(tag: Long, typeName: String, props: JSONObject): ViewRecord {
        check(registry.get(tag) == null) { "duplicate create: $tag" }
        val manager = checkNotNull(PNRegistry.managerFor(typeName)) { "unknown component: $typeName" }
        val view = manager.createView(PNBridge.context(), tag, props)
        val record = ViewRecord(tag, typeName, view, manager)
        JsonUtil.merge(record.props, props)
        registry.register(record)
        try {
            manager.applyProps(view, props, true)
        } finally {
            record.initialized = true
        }
        TouchForwarder.bind(record)
        return record
    }

    private fun update(op: MountOp.Update) {
        val record = registry.get(op.tag) ?: throw IllegalStateException("update: unknown tag ${op.tag}")
        if (op.recreate) {
            recreate(record, op.changed, op.removed)
            return
        }
        JsonUtil.merge(record.props, op.changed)
        for (key in op.removed) record.props.remove(key)
        record.manager.update(record.view, op.changed)
        if (op.changed.has("gestures")) TouchForwarder.bind(record)
    }

    /** Rebuild a widget in place, keeping its children, position, focus, and text selection. */
    private fun recreate(record: ViewRecord, changed: JSONObject, removed: List<String>) {
        val old = record.view
        val props = JSONObject(record.props.toString())
        JsonUtil.merge(props, changed)
        for (key in removed) props.remove(key)
        val parent = record.parent?.let { registry.get(it) }
        val index = parent?.children?.indexOf(record.tag) ?: 0
        val children = record.children.mapNotNull { registry.get(it) }
        val physicalParent = old.parent as? ViewGroup
        val physicalIndex = physicalParent?.indexOfChild(old) ?: 0
        val focused = old.hasFocus()
        val input = old as? EditText
        val selection = input?.let { it.selectionStart to it.selectionEnd }
        val edited = (record.state["edit_revision"] as? Number)?.toLong() ?: 0
        if (input != null && (!changed.has("value") || changed.optLong("_pn_edit_revision", 0) < edited)) props.put("value", input.text.toString())
        for (child in children) record.manager.removeChild(old, child.view)
        if (parent != null) parent.manager.removeChild(parent.view, old) else physicalParent?.removeView(old)
        TouchForwarder.unbind(record)
        record.manager.destroy(old)
        registry.unregister(record.tag)
        val replacement = create(record.tag, record.typeName, props)
        replacement.parent = record.parent
        replacement.children.addAll(record.children)
        if (input != null) replacement.state["edit_revision"] = edited
        record.frame?.let { frame ->
            replacement.frame = frame
            replacement.manager.setFrame(replacement.view, frame[0], frame[1], frame[2], frame[3])
        }
        for ((position, child) in children.withIndex()) replacement.manager.insertChild(replacement.view, child.view, position)
        if (parent != null) parent.manager.insertChild(parent.view, replacement.view, index.coerceAtLeast(0))
        else physicalParent?.addView(replacement.view, physicalIndex, old.layoutParams)
        if (focused) replacement.view.requestFocus()
        val edit = replacement.view as? EditText
        if (selection != null && edit != null) {
            edit.setSelection(selection.first.coerceIn(0, edit.length()), selection.second.coerceIn(0, edit.length()))
        }
    }

    /** Move-aware: a child under another parent leaves it first. */
    private fun insert(op: MountOp.Insert) {
        val parent = registry.get(op.parent) ?: throw IllegalStateException("insert: unknown parent ${op.parent}")
        val child = registry.get(op.child) ?: throw IllegalStateException("insert: unknown child ${op.child}")
        val previous = child.parent?.let { registry.get(it) }
        if (previous != null && previous !== parent) {
            previous.children.remove(child.tag)
            previous.manager.removeChild(previous.view, child.view)
        } else if (previous === parent) {
            parent.children.remove(child.tag)
        }
        parent.children.add(op.index.coerceIn(0, parent.children.size), child.tag)
        child.parent = parent.tag
        parent.manager.insertChild(parent.view, child.view, op.index)
    }

    private fun delete(record: ViewRecord) {
        TouchForwarder.unbind(record)
        Measurement.forget(record.tag)
        try {
            // Children that outlive this view (moved by a later insert) leave it now.
            for (tag in record.children.toList()) registry.get(tag)?.let { child ->
                record.manager.removeChild(record.view, child.view)
                child.parent = null
            }
            record.children.clear()
            val parent = record.parent?.let { registry.get(it) }
                ?: (record.view.parent as? View)?.let { registry.recordFor(it) }
            if (parent != null) {
                parent.children.remove(record.tag)
                parent.manager.removeChild(parent.view, record.view)
            }
            record.manager.destroy(record.view)
        } finally {
            registry.unregister(record.tag)
        }
    }

    private fun frame(op: MountOp.Frame) {
        val record = registry.get(op.tag) ?: throw IllegalStateException("frame: unknown tag ${op.tag}")
        record.frame = doubleArrayOf(op.x, op.y, op.width, op.height)
        record.manager.setFrame(record.view, op.x, op.y, op.width, op.height)
        VirtualListManager.measured(op.tag, op.width, op.height)
    }

    private fun command(op: MountOp.Command) {
        val reply = JSONObject().put("call_id", op.callId)
        val record = registry.get(op.tag)
        if (record == null) {
            reply.put("ok", false).put("error", "unknown view ${op.tag}")
        } else try {
            reply.put("ok", true).put("value", JsonUtil.wrap(record.manager.command(record.view, op.name, op.args)))
        } catch (error: Exception) {
            Log.e(PNBridge.TAG, "command '${op.name}' failed for ${record.typeName}#${op.tag}", error)
            reply.put("ok", false).put("error", error.message ?: error.toString())
        }
        PNBridge.callPython("command", 0, "", reply.toString())
    }

    /** The props recorded for `tag`, mainly for diagnostics. */
    fun propsOf(tag: Long): JSONObject? = registry.get(tag)?.props
}
