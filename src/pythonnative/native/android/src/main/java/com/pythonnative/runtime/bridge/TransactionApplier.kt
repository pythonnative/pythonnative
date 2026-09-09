package com.pythonnative.runtime.bridge

import android.view.View
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.gestures.GestureCoordinator
import org.json.JSONObject

/** Applies validated batches. Runtime inconsistencies fail the entire surface. */
class TransactionApplier(private val registry: ViewRegistry) {
    /** Apply a single op. */
    fun applyOp(op: Op) {
        when (op) {
            is Op.Create -> create(op)
            is Op.Update -> update(op)
            is Op.Insert -> insert(op)
            is Op.Destroy -> destroy(op)
            is Op.Frame -> frame(op)
        }
    }

    private fun create(op: Op.Create) {
        check(registry.get(op.tag) == null) { "duplicate create: ${op.tag}" }
        val manager = checkNotNull(PNRegistry.managerFor(op.typeName)) { "unknown component: ${op.typeName}" }
        val view = manager.createView(PNBridge.context(), op.tag, op.props)
        val record = ViewRecord(op.tag, op.typeName, view, manager)
        JsonUtil.merge(record.props, op.props)
        registry.register(record)
        try {
            manager.applyProps(view, op.props, true)
        } finally {
            record.initialized = true
        }
        if (op.props.has("gestures")) {
            GestureCoordinator.bind(record, op.props.opt("gestures"))
        }
    }

    private fun update(op: Op.Update) {
        val record = registry.get(op.tag) ?: throw IllegalStateException("update: unknown tag ${op.tag}")
        val changed = com.pythonnative.generated.PNContracts.normalize(record.typeName, op.changed)
        if (com.pythonnative.generated.PNContracts.requiresRecreation(record.typeName, op.changed)) {
            recreate(record, changed)
            return
        }
        JsonUtil.merge(record.props, changed)
        record.manager.update(record.view, changed)
        if (op.changed.has("gestures")) {
            GestureCoordinator.bind(record, op.changed.opt("gestures"))
        }
    }

    private fun recreate(record: ViewRecord, changed: JSONObject) {
        val old = record.view
        val props = JSONObject(record.props.toString())
        JsonUtil.merge(props, changed)
        val parent = record.parent?.let { registry.get(it) }
        val index = parent?.children?.indexOf(record.tag) ?: 0
        val children = record.children.mapNotNull { registry.get(it) }
        val physicalParent = old.parent as? android.view.ViewGroup
        val physicalIndex = physicalParent?.indexOfChild(old) ?: 0
        val focused = old.hasFocus()
        val input = old as? android.widget.EditText
        val selection = input?.let { it.selectionStart to it.selectionEnd }
        val edited = (record.state["edit_revision"] as? Number)?.toLong() ?: 0
        if (input != null && (!changed.has("value") || changed.optLong("_pn_edit_revision", 0) < edited)) props.put("value", input.text.toString())
        for (child in children) record.manager.removeChild(old, child.view)
        if (parent != null) parent.manager.removeChild(parent.view, old)
        else physicalParent?.removeView(old)
        GestureCoordinator.unbind(record)
        record.manager.destroy(old)
        registry.unregister(record.tag)
        create(Op.Create(record.tag, record.typeName, props))
        val replacement = registry.get(record.tag)!!
        replacement.parent = record.parent
        replacement.children.addAll(record.children)
        if (input != null) replacement.state["edit_revision"] = edited
        record.frame?.let { frame(Op.Frame(record.tag, it[0], it[1], it[2], it[3])) }
        for ((position, child) in children.withIndex()) record.manager.insertChild(replacement.view, child.view, position)
        if (parent != null) parent.manager.insertChild(parent.view, replacement.view, index.coerceAtLeast(0))
        else physicalParent?.addView(replacement.view, physicalIndex, old.layoutParams)
        if (focused) replacement.view.requestFocus()
        if (selection != null && replacement.view is android.widget.EditText) {
            val edit = replacement.view
            edit.setSelection(selection.first.coerceIn(0, edit.length()), selection.second.coerceIn(0, edit.length()))
        }
    }

    private fun insert(op: Op.Insert) {
        val parent = registry.get(op.parent) ?: throw IllegalStateException("insert: unknown parent ${op.parent}")
        val child = registry.get(op.child) ?: throw IllegalStateException("insert: unknown child ${op.child}")
        child.parent?.let { registry.get(it)?.children?.remove(op.child) }
        parent.children.add(op.index.coerceIn(0, parent.children.size), op.child)
        child.parent = op.parent
        parent.manager.insertChild(parent.view, child.view, op.index)
    }

    private fun destroy(op: Op.Destroy) {
        val record = registry.get(op.tag) ?: return
        destroyRecord(record)
    }

    private fun destroyRecord(record: ViewRecord) {
        com.pythonnative.runtime.animation.AnimationGraph.forget(record.tag)
        GestureCoordinator.unbind(record)
        try {
            val parentRecord = record.parent?.let { registry.get(it) }
                ?: (record.view.parent as? View)?.let { registry.recordFor(it) }
            if (parentRecord != null) {
                parentRecord.children.remove(record.tag)
                parentRecord.manager.removeChild(parentRecord.view, record.view)
            }
            record.manager.destroy(record.view)
        } finally {
            registry.unregister(record.tag)
        }
    }

    private fun frame(op: Op.Frame) {
        val record = registry.get(op.tag) ?: throw IllegalStateException("frame: unknown tag ${op.tag}")
        record.frame = doubleArrayOf(op.x, op.y, op.width, op.height)
        record.manager.setFrame(record.view, op.x, op.y, op.width, op.height)
    }

    /** The props recorded for `tag`, mainly for diagnostics. */
    fun propsOf(tag: Long): JSONObject? = registry.get(tag)?.props
}
