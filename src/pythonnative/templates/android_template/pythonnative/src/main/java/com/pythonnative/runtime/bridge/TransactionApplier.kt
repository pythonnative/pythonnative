package com.pythonnative.runtime.bridge

import android.view.View
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.components.ComponentManager
import com.pythonnative.runtime.components.PlaceholderManager
import com.pythonnative.runtime.gestures.GestureCoordinator
import org.json.JSONObject

/**
 * Applies decoded transactions to the view tree, in order, with per-op
 * error isolation. Unknown element types create a placeholder view and
 * log once.
 */
class TransactionApplier(private val registry: ViewRegistry) {
    private val placeholder = PlaceholderManager()

    /** Decode and apply `transactionJson`. */
    fun apply(transactionJson: String) {
        val ops = try {
            PNTransaction.decode(transactionJson) { index, error ->
                PNLog.rateLimited("decode", "transaction op $index could not be decoded", error)
            }
        } catch (e: Exception) {
            PNLog.rateLimited("decode-top", "transaction is not a JSON array", e)
            return
        }
        for (op in ops) {
            try {
                applyOp(op)
            } catch (e: Exception) {
                PNLog.rateLimited("op:" + op.javaClass.simpleName, "failed to apply $op", e)
            }
        }
    }

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
        registry.get(op.tag)?.let {
            PNLog.rateLimited("dup-create", "tag ${op.tag} already exists (${it.typeName}); replacing")
            destroyRecord(it)
        }
        val manager = PNRegistry.managerFor(op.typeName) ?: run {
            PNLog.once("unknown-type:" + op.typeName, "unknown element type '${op.typeName}'; using a placeholder view")
            placeholder
        }
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
        JsonUtil.merge(record.props, op.changed)
        record.manager.update(record.view, op.changed)
        if (op.changed.has("gestures")) {
            GestureCoordinator.bind(record, op.changed.opt("gestures"))
        }
    }

    private fun insert(op: Op.Insert) {
        val parent = registry.get(op.parent) ?: throw IllegalStateException("insert: unknown parent ${op.parent}")
        val child = registry.get(op.child) ?: throw IllegalStateException("insert: unknown child ${op.child}")
        parent.manager.insertChild(parent.view, child.view, op.index)
    }

    private fun destroy(op: Op.Destroy) {
        val record = registry.get(op.tag) ?: return
        destroyRecord(record)
    }

    private fun destroyRecord(record: ViewRecord) {
        GestureCoordinator.unbind(record)
        try {
            val parentRecord = (record.view.parent as? View)?.let { registry.recordFor(it) }
            if (parentRecord != null) {
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

    /** Whether `manager` is the fallback placeholder manager. */
    fun isPlaceholder(manager: ComponentManager): Boolean = manager === placeholder

    /** The props recorded for `tag`, mainly for diagnostics. */
    fun propsOf(tag: Long): JSONObject? = registry.get(tag)?.props
}
