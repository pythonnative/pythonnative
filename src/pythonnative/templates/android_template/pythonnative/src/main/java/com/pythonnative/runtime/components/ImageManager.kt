package com.pythonnative.runtime.components

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.BitmapFactory
import android.util.Base64
import android.view.View
import android.widget.ImageView
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject

/**
 * `Image` element. Sources: `http(s)` URLs (downloaded and cached by
 * [ImageLoader]), absolute file paths, drawable resource names, and
 * base64 `data:` URIs. Fires `on_load` / `on_error`.
 */
class ImageManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = ImageView(context)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val iv = view as ImageView
        PNColor.parse(props.value("tint_color"))?.let { iv.imageTintList = ColorStateList.valueOf(it) }
        if (props.has("tint_color") && props.value("tint_color") == null) iv.imageTintList = null
        PNColor.parse(props.value("placeholder_color"))?.let { iv.setBackgroundColor(it) }
        if (props.has("source")) {
            val source = sourceString(props.value("source"))
            if (source != null) loadSource(iv, source) else iv.setImageDrawable(null)
        }
        val mode = props.str("resize_mode") ?: props.str("scale_type")
        if (mode != null) {
            iv.scaleType = when (mode) {
                "cover" -> ImageView.ScaleType.CENTER_CROP
                "contain" -> ImageView.ScaleType.FIT_CENTER
                "stretch" -> ImageView.ScaleType.FIT_XY
                "center", "repeat" -> ImageView.ScaleType.CENTER
                else -> iv.scaleType
            }
        }
        ViewStyler.apply(iv, props)
    }

    private fun sourceString(value: Any?): String? {
        return when (value) {
            null -> null
            is JSONObject -> value.str("uri") ?: value.str("url") ?: value.str("path")
            else -> value.toString().takeIf { it.isNotEmpty() }
        }
    }

    private fun loadSource(iv: ImageView, source: String) {
        val state = stateOf(iv)
        state["pending_uri"] = source
        try {
            when {
                source.startsWith("data:") -> loadDataUri(iv, source)
                source.startsWith("http://") || source.startsWith("https://") -> {
                    val (tw, th) = targetSize(iv)
                    ImageLoader.loadRemote(iv.context, source, tw, th) { bitmap, error ->
                        if (stateOf(iv)["pending_uri"] != source) return@loadRemote
                        if (bitmap != null) {
                            iv.setImageBitmap(bitmap)
                            fire(iv, "on_load")
                        } else {
                            fire(iv, "on_error", error ?: "load failed")
                        }
                    }
                }
                source.startsWith("/") || source.startsWith("file://") -> {
                    val path = source.removePrefix("file://")
                    val (tw, th) = targetSize(iv)
                    ImageLoader.loadFile(path, tw, th) { bitmap, error ->
                        if (stateOf(iv)["pending_uri"] != source) return@loadFile
                        if (bitmap != null) {
                            iv.setImageBitmap(bitmap)
                            fire(iv, "on_load")
                        } else {
                            fire(iv, "on_error", error ?: "decode failed")
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
                        fire(iv, "on_load")
                    } else {
                        fire(iv, "on_error", "drawable '$name' not found")
                    }
                }
            }
        } catch (e: Exception) {
            PNLog.swallowed("ImageManager.loadSource", e)
            fire(iv, "on_error", e.message ?: "load failed")
        }
    }

    private fun loadDataUri(iv: ImageView, source: String) {
        try {
            val payload = source.substringAfter(',', "")
            val raw = Base64.decode(payload, Base64.DEFAULT)
            val bitmap = BitmapFactory.decodeByteArray(raw, 0, raw.size)
            if (bitmap != null) {
                iv.setImageBitmap(bitmap)
                fire(iv, "on_load")
            } else {
                fire(iv, "on_error", "data URI decode failed")
            }
        } catch (e: Exception) {
            fire(iv, "on_error", "data URI decode failed")
        }
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
