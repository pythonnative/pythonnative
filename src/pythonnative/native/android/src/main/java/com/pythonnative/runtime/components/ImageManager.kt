package com.pythonnative.runtime.components

import com.pythonnative.runtime.PNBridge
import com.pythonnative.generated.ImageProps
import com.pythonnative.generated.PNValues
import com.pythonnative.generated.PNComponentEvents
import com.pythonnative.generated.PNImageLoadEvent

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.view.View
import android.widget.ImageView
import com.pythonnative.runtime.assets.PNAssets
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.layout.NativeLayout
import org.json.JSONObject

/**
 * `Image` element. Sources: `asset://` URIs (bundled files, density
 * variants picked for the screen), `http(s)` URLs (downloaded and cached
 * by [ImageLoader]), absolute file paths, `content://` URIs, and base64
 * `data:` URIs. `default_source` (a local source) shows immediately while
 * a remote `source` loads and stays up if it fails. `blur_radius` blurs
 * the decoded bitmap. Fires `on_load` / `on_error`.
 */
class ImageManager : TypedComponentManager<ImageProps>({ values, partial -> ImageProps(values, partial) }) {
    private val assetViews = java.util.Collections.newSetFromMap(java.util.WeakHashMap<ImageView, Boolean>())
    private var unsubscribe: (() -> Unit)? = null

    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        if (unsubscribe == null) unsubscribe = PNAssets.addListener { reloadAssetImages() }
        return ImageView(context)
    }

    override fun applyTyped(view: View, props: ImageProps, initial: Boolean) {
        val iv = view as ImageView
        if (props.has_tint_color) iv.imageTintList = props.tint_color?.let { PNColor.parse(PNValues.encode(it)) }?.let { ColorStateList.valueOf(it) }
        if (props.has_placeholder_color) iv.setBackgroundColor(props.placeholder_color?.let { PNColor.parse(PNValues.encode(it)) } ?: android.graphics.Color.TRANSPARENT)
        if (props.has_source || props.has_default_source || props.has_blur_radius) {
            load(iv, propsOf(iv))
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

    /** Re-run loads for views showing `asset://` sources after an overlay change. */
    private fun reloadAssetImages() {
        for (iv in assetViews.toList()) {
            if (PNBridge.registry.tagOf(iv) == null) continue
            load(iv, propsOf(iv))
        }
    }

    private fun load(iv: ImageView, merged: JSONObject) {
        val state = stateOf(iv)
        @Suppress("UNCHECKED_CAST")
        (state.remove("cancel_image") as? (() -> Unit))?.invoke()
        val source = merged.str("source")?.takeIf { it.isNotEmpty() }
        val fallback = merged.str("default_source")?.takeIf { it.isNotEmpty() }
        val blur = (merged.opt("blur_radius") as? Number)?.toFloat() ?: 0f
        val request = Any()
        state["image_request"] = request
        state["pending_uri"] = source
        if (PNAssets.isAssetUri(source) || PNAssets.isAssetUri(fallback)) assetViews.add(iv) else assetViews.remove(iv)

        if (source == null && fallback == null) {
            state.remove("pending_uri")
            state.remove("image_request")
            iv.setImageDrawable(null)
            return
        }
        val cancels = ArrayList<() -> Unit>()
        state["cancel_image"] = { for (cancel in cancels) cancel() }
        // Show the local fallback right away when the real source is remote
        // (or missing); a local source replaces it as soon as it decodes.
        if (fallback != null && (source == null || isRemote(source))) {
            cancels.add(start(iv, fallback, blur, request, report = source == null) { bitmap ->
                // Keep the fallback only while nothing better has landed.
                if (stateOf(iv)["shown_source"] == null) iv.setImageBitmap(bitmap)
            })
        }
        if (source != null) {
            cancels.add(start(iv, source, blur, request, report = true) { bitmap ->
                stateOf(iv)["shown_source"] = source
                iv.setImageBitmap(bitmap)
            })
        }
    }

    private fun isRemote(source: String) = source.startsWith("http://") || source.startsWith("https://")

    /** Kick off one decode; `onBitmap` runs on success, events fire when `report` is set. */
    private fun start(iv: ImageView, source: String, blur: Float, request: Any, report: Boolean, onBitmap: (Bitmap) -> Unit): () -> Unit {
        stateOf(iv).remove("shown_source")
        val (tw, th) = targetSize(iv)
        val callback = ImageLoader.Callback { bitmap, error ->
            if (stateOf(iv)["image_request"] !== request) return@Callback
            if (bitmap != null) {
                onBitmap(bitmap)
                if (report) emitLoaded(iv)
                PNBridge.registry.tagOf(iv)?.let { NativeLayout.invalidate(it) }
            } else if (report) {
                PNComponentEvents.Image.on_error(iv, error ?: "load failed")
            }
        }
        return try {
            when {
                PNAssets.isAssetUri(source) -> {
                    val resolved = PNAssets.resolve(source)
                    if (resolved == null) {
                        if (report) PNComponentEvents.Image.on_error(iv, "asset not found: ${PNAssets.pathOf(source)}")
                        return {}
                    }
                    ImageLoader.loadAsset(resolved, tw, th, callback, blur)
                }
                source.startsWith("data:") || source.startsWith("content://") ->
                    ImageLoader.loadData(iv.context, source, tw, th, callback, blur)
                isRemote(source) -> ImageLoader.loadRemote(iv.context, source, tw, th, callback, blur)
                source.startsWith("/") || source.startsWith("file://") ->
                    ImageLoader.loadFile(source.removePrefix("file://"), tw, th, callback, blur)
                else -> {
                    if (report) PNComponentEvents.Image.on_error(iv, "unsupported image source: $source")
                    return {}
                }
            }
        } catch (e: Exception) {
            PNLog.swallowed("ImageManager.start", e)
            if (report) PNComponentEvents.Image.on_error(iv, e.message ?: "load failed")
            return {}
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
        stateOf(view).remove("shown_source")
        (view as? ImageView)?.let { assetViews.remove(it) }
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        val iv = view as ImageView
        val drawable = iv.drawable ?: return floatArrayOf(0f, 0f)
        val density = view.context.resources.displayMetrics.density
        // Decoded bitmaps carry a density so their intrinsic size is the
        // source's logical size (see ImageLoader.decodeStream).
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
