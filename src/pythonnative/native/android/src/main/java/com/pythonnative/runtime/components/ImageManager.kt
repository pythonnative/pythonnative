package com.pythonnative.runtime.components

import com.pythonnative.runtime.PNBridge
import com.pythonnative.generated.ImageProps
import com.pythonnative.generated.PNValues
import com.pythonnative.generated.PNComponentEvents
import com.pythonnative.generated.PNImageLoadEvent

import android.content.Context
import android.content.res.ColorStateList
import android.view.View
import android.widget.ImageView
import com.pythonnative.runtime.bridge.PNLog
import org.json.JSONObject

/**
 * `Image` element. Sources: `http(s)` URLs (downloaded and cached by
 * [ImageLoader]), absolute file paths, drawable resource names, and
 * base64 `data:` URIs. Fires `on_load` / `on_error`.
 */
class ImageManager : TypedComponentManager<ImageProps>({ values, partial -> ImageProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = ImageView(context)

    override fun applyTyped(view: View, props: ImageProps, initial: Boolean) {
        val iv = view as ImageView
        if (props.has_tint_color) iv.imageTintList = props.tint_color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        if (props.has_placeholder_color) iv.setBackgroundColor(props.placeholder_color?.let { PNColor.parse(PNValues.encode(it)) } ?: android.graphics.Color.TRANSPARENT)
        if (props.has_source) {
            @Suppress("UNCHECKED_CAST")
            (stateOf(iv).remove("cancel_image") as? (() -> Unit))?.invoke()
            val source = props.source
            if (!source.isNullOrEmpty()) loadSource(iv, source) else {
                stateOf(iv).remove("pending_uri")
                stateOf(iv).remove("image_request")
                iv.setImageDrawable(null)
            }
        }
        if (props.has_scale_type) {
            iv.scaleType = when (props.scale_type?.let { PNValues.encode(it) }) {
                "cover" -> ImageView.ScaleType.CENTER_CROP
                "stretch" -> ImageView.ScaleType.FIT_XY
                "center" -> ImageView.ScaleType.CENTER
                else -> ImageView.ScaleType.FIT_CENTER
            }
        }
        ViewStyler.apply(iv, props.values)
    }

    private fun loadSource(iv: ImageView, source: String) {
        val state = stateOf(iv)
        state["pending_uri"] = source
        val request = Any()
        state["image_request"] = request
        try {
            when {
                source.startsWith("data:") || source.startsWith("content://") -> {
                    val (tw, th) = targetSize(iv)
                    state["cancel_image"] = ImageLoader.loadData(iv.context, source, tw, th) { bitmap, error ->
                        if (stateOf(iv)["image_request"] !== request) return@loadData
                        if (bitmap != null) {
                            iv.setImageBitmap(bitmap)
                            emitLoaded(iv)
                        PNBridge.registry.tagOf(iv)?.let { com.pythonnative.runtime.layout.NativeLayout.invalidate(it) }
                        } else PNComponentEvents.Image.on_error(iv, error ?: "decode failed")
                    }
                }
                source.startsWith("http://") || source.startsWith("https://") -> {
                    val (tw, th) = targetSize(iv)
                    state["cancel_image"] = ImageLoader.loadRemote(iv.context, source, tw, th) { bitmap, error ->
                        if (stateOf(iv)["image_request"] !== request) return@loadRemote
                        if (bitmap != null) {
                            iv.setImageBitmap(bitmap)
                            emitLoaded(iv)
                        PNBridge.registry.tagOf(iv)?.let { com.pythonnative.runtime.layout.NativeLayout.invalidate(it) }
                        } else {
                            PNComponentEvents.Image.on_error(iv, error ?: "load failed")
                        }
                    }
                }
                source.startsWith("/") || source.startsWith("file://") -> {
                    val path = source.removePrefix("file://")
                    val (tw, th) = targetSize(iv)
                    state["cancel_image"] = ImageLoader.loadFile(path, tw, th) { bitmap, error ->
                        if (stateOf(iv)["image_request"] !== request) return@loadFile
                        if (bitmap != null) {
                            iv.setImageBitmap(bitmap)
                            emitLoaded(iv)
                        PNBridge.registry.tagOf(iv)?.let { com.pythonnative.runtime.layout.NativeLayout.invalidate(it) }
                        } else {
                            PNComponentEvents.Image.on_error(iv, error ?: "decode failed")
                        }
                    }
                }
                else -> {
                    val ctx = iv.context
                    val name = source.substringBeforeLast('.', source)
                    val resId = ctx.resources.getIdentifier(name, "drawable", ctx.packageName)
                        .takeIf { it != 0 }
                        ?: ctx.resources.getIdentifier(name, "mipmap", ctx.packageName)
                    if (resId != 0) {
                        iv.setImageResource(resId)
                        emitLoaded(iv)
                        PNBridge.registry.tagOf(iv)?.let { com.pythonnative.runtime.layout.NativeLayout.invalidate(it) }
                    } else {
                        PNComponentEvents.Image.on_error(iv, "drawable '$name' not found")
                    }
                }
            }
        } catch (e: Exception) {
            PNLog.swallowed("ImageManager.loadSource", e)
            PNComponentEvents.Image.on_error(iv, e.message ?: "load failed")
        }
    }

    private fun emitLoaded(view: ImageView) {
        val drawable = view.drawable ?: return
        val density = view.context.resources.displayMetrics.density.toDouble()
        PNComponentEvents.Image.on_load(view, PNImageLoadEvent(drawable.intrinsicWidth / density, drawable.intrinsicHeight / density))
    }

    private fun targetSize(iv: ImageView): Pair<Int, Int> {
        var w = iv.width
        var h = iv.height
        val frame = recordOf(iv)?.frame
        if (w <= 0 && frame != null) {
            w = px(frame[2])
            h = px(frame[3])
        }
        if (w <= 0) {
            val metrics = iv.context.resources.displayMetrics
            w = metrics.widthPixels
            h = metrics.heightPixels
        }
        if (h <= 0) h = w
        return Pair(w, h)
    }

    override fun teardown(view: View) {
        @Suppress("UNCHECKED_CAST")
        (stateOf(view).remove("cancel_image") as? (() -> Unit))?.invoke()
        stateOf(view).remove("image_request")
        stateOf(view).remove("pending_uri")
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        val iv = view as ImageView
        val drawable = iv.drawable ?: return floatArrayOf(0f, 0f)
        val density = view.context.resources.displayMetrics.density
        // Bitmaps decode at device density, so their pixel size is already a dp-ish measure.
        var w = drawable.intrinsicWidth / density
        var h = drawable.intrinsicHeight / density
        if (w <= 0f || h <= 0f) return floatArrayOf(0f, 0f)
        val maxW = if (maxWidth.isFinite() && maxWidth < 1e6) maxWidth.toFloat() else Float.MAX_VALUE
        val maxH = if (maxHeight.isFinite() && maxHeight < 1e6) maxHeight.toFloat() else Float.MAX_VALUE
        if (w > maxW) {
            h *= maxW / w
            w = maxW
        }
        if (h > maxH) {
            w *= maxH / h
            h = maxH
        }
        return floatArrayOf(w, h)
    }
}
