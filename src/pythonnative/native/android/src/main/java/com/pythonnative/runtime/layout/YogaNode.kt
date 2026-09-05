package com.pythonnative.runtime.layout

import android.widget.TextView
import com.pythonnative.runtime.PNBridge

/** Explicit ownership of a node in the pinned, shared Yoga core. */
class YogaNode(val tag: Long) : AutoCloseable {
    companion object { init { System.loadLibrary("pn_yoga") } }
    val ptr = create()
    private var closed = false
    private external fun create(): Long
    private external fun free(ptr: Long)
    external fun style(ptr: Long, key: String, value: String)
    external fun resetStyle(ptr: Long)
    external fun measureLeaf(ptr: Long, enabled: Boolean)
    external fun insert(ptr: Long, child: Long, index: Int)
    external fun remove(ptr: Long, child: Long)
    external fun calculate(ptr: Long, width: Float, height: Float)
    external fun frame(ptr: Long): FloatArray
    fun measure(width: Float, height: Float): FloatArray {
        val record = PNBridge.registry.get(tag) ?: return floatArrayOf(0f, 0f)
        return record.manager.measure(record.view, width.toDouble(), height.toDouble())
    }
    fun baseline(height: Float): Float {
        val view = PNBridge.registry.get(tag)?.view as? TextView ?: return height
        return -view.paint.fontMetrics.ascent / PNBridge.density()
    }
    override fun close() { if (!closed) { closed = true; free(ptr) } }
}
