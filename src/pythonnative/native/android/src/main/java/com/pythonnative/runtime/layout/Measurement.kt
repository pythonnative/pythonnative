package com.pythonnative.runtime.layout

import android.content.Context
import android.util.Log
import android.widget.EditText
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.core.PNCore
import com.pythonnative.runtime.mount.MountDecoder
import com.pythonnative.runtime.text.PNTextLayout
import org.json.JSONObject
import java.nio.ByteBuffer
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/**
 * The core's `measure` and `baseline` callbacks. They run on the core's
 * workers, never on the main thread:
 *
 * - `text` builds a [PNTextLayout] on the calling thread.
 * - `intrinsic` hops to the main thread once and measures a prototype
 *   widget built from the props (the core caches the result).
 * - `native` asks the plugin manager's thread-safe
 *   [com.pythonnative.runtime.components.ComponentManager.measureNative],
 *   falling back to `intrinsic`.
 *
 * Sizes are in dp.
 */
object Measurement {
    const val TEXT = 1
    const val INTRINSIC = 2
    const val NATIVE = 3

    private const val UNDEFINED = 0
    private const val UNCONSTRAINED = 1e6

    @Volatile private var defaults: PNTextLayout.TextDefaults? = null
    @Volatile private var context: Context? = null
    private val textLayouts = ConcurrentHashMap<Long, PNTextLayout>()
    private val prototypeTags = AtomicLong(0)

    /** Capture the theme's text defaults; call on the main thread whenever the configuration changes. */
    fun prepare(context: Context) {
        this.context = context.applicationContext ?: context
        defaults = PNTextLayout.TextDefaults.capture(context)
    }

    /** Re-measure every leaf (font scale, density, or locale changed). */
    fun configurationChanged(context: Context) {
        prepare(context)
        textLayouts.clear()
        PNCore.invalidateMeasurements()
    }

    /** Drop the cached layout of a deleted view. */
    fun forget(tag: Long) {
        textLayouts.remove(tag)
    }

    fun measure(
        tag: Long, component: String, mode: Int, encodedProps: ByteBuffer,
        width: Float, widthMode: Int, height: Float, heightMode: Int,
    ): FloatArray {
        // The props buffer is only valid during this call.
        val props = MountDecoder.decodeValue(encodedProps) as? JSONObject ?: JSONObject()
        val maxWidth = if (widthMode == UNDEFINED || !width.isFinite()) UNCONSTRAINED else width.toDouble()
        val maxHeight = if (heightMode == UNDEFINED || !height.isFinite()) UNCONSTRAINED else height.toDouble()
        return try {
            when (mode) {
                TEXT -> text(tag, props, maxWidth)
                NATIVE -> PNRegistry.managerFor(component)?.measureNative(props, maxWidth, maxHeight)
                    ?: intrinsic(tag, component, props, maxWidth, maxHeight)
                else -> intrinsic(tag, component, props, maxWidth, maxHeight)
            }
        } catch (error: Exception) {
            Log.e(PNBridge.TAG, "measuring $component#$tag failed", error)
            floatArrayOf(0f, 0f)
        }
    }

    fun baseline(tag: Long, height: Float): Float = textLayouts[tag]?.baseline ?: height

    private fun text(tag: Long, props: JSONObject, maxWidth: Double): FloatArray {
        val context = PNBridge.activity() ?: context ?: return floatArrayOf(0f, 0f)
        val defaults = defaults ?: MainThread.call { PNTextLayout.TextDefaults.capture(context) }.also { defaults = it }
        val layout = PNTextLayout.build(context, defaults, props, maxWidth)
        textLayouts[tag] = layout
        return floatArrayOf(layout.width, layout.height)
    }

    /** Measure a prototype widget on the main thread. */
    private fun intrinsic(tag: Long, component: String, props: JSONObject, maxWidth: Double, maxHeight: Double): FloatArray =
        MainThread.call { prototype(tag, component, props, maxWidth, maxHeight) }

    private fun prototype(tag: Long, component: String, props: JSONObject, maxWidth: Double, maxHeight: Double): FloatArray {
        val manager = PNRegistry.managerFor(component) ?: return floatArrayOf(0f, 0f)
        val live = PNBridge.registry.get(tag)
        // A text input sizes to what the user typed, which Python may not know yet.
        if (!props.has("value")) (live?.view as? EditText)?.let { props.put("value", it.text.toString()) }
        val context = PNBridge.activity() ?: return floatArrayOf(0f, 0f)
        // Negative tags never reach Python: PNEvents drops them.
        val prototypeTag = -prototypeTags.incrementAndGet()
        val view = manager.createView(context, prototypeTag, props)
        val record = ViewRecord(prototypeTag, component, view, manager)
        com.pythonnative.runtime.bridge.JsonUtil.merge(record.props, props)
        PNBridge.registry.register(record)
        try {
            manager.applyProps(view, props, true)
            record.initialized = true
            return manager.measure(view, maxWidth, maxHeight)
        } finally {
            try { manager.destroy(view) } catch (_: Exception) {}
            PNBridge.registry.unregister(prototypeTag)
        }
    }
}
