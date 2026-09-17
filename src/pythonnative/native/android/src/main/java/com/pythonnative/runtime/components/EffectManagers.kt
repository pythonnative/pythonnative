package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.view.View
import android.view.ViewTreeObserver
import com.pythonnative.generated.BlurViewProps
import com.pythonnative.generated.LinearGradientProps
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.views.PNFrameLayout
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * `LinearGradient`: a flex container that paints a `LinearGradient`
 * shader under its children. `start_point`/`end_point` are unit
 * coordinates in the view's box; the corner radius from the style props
 * clips the gradient.
 */
class LinearGradientManager : TypedComponentManager<LinearGradientProps>({ values, partial -> LinearGradientProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = GradientView(context)

    override fun applyTyped(view: View, props: LinearGradientProps, initial: Boolean) {
        val gradient = view as GradientView
        val merged = propsOf(gradient)
        if (props.has_colors || props.has_locations || props.has_start_point || props.has_end_point) {
            val colors = (merged.value("colors") as? JSONArray)?.let { array ->
                (0 until array.length()).mapNotNull { PNColor.parse(array.opt(it)) }
            } ?: emptyList()
            val locations = (merged.value("locations") as? JSONArray)?.let { array ->
                (0 until array.length()).map { array.optDouble(it, 0.0).toFloat() }
            }
            gradient.configure(
                colors,
                locations?.takeIf { it.size == colors.size },
                point(merged.value("start_point"), 0f, 0f),
                point(merged.value("end_point"), 0f, 1f),
            )
        }
        if (listOf("border_radius", "border_top_left_radius", "border_top_right_radius", "border_bottom_left_radius", "border_bottom_right_radius").any { props.values.has(it) }) {
            gradient.cornerRadius = pxF(merged.num("border_radius") ?: 0.0)
        }
        ViewStyler.apply(gradient, props.values)
    }

    private fun point(value: Any?, dx: Float, dy: Float): FloatArray {
        val array = value as? JSONArray ?: return floatArrayOf(dx, dy)
        if (array.length() != 2) return floatArrayOf(dx, dy)
        return floatArrayOf(array.optDouble(0, dx.toDouble()).toFloat(), array.optDouble(1, dy.toDouble()).toFloat())
    }
}

/** Container that draws a linear gradient before its children. */
class GradientView(context: Context) : PNFrameLayout(context) {
    private var colors: IntArray = intArrayOf()
    private var locations: FloatArray? = null
    private var start = floatArrayOf(0f, 0f)
    private var end = floatArrayOf(0f, 1f)
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val clip = Path()
    var cornerRadius = 0f
        set(value) { field = value; invalidate() }

    init {
        setWillNotDraw(false)
    }

    fun configure(colors: List<Int>, locations: List<Float>?, start: FloatArray, end: FloatArray) {
        this.colors = colors.toIntArray()
        this.locations = locations?.toFloatArray()
        this.start = start
        this.end = end
        paint.shader = null
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        paint.shader = null
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0) return
        if (paint.shader == null) {
            paint.shader = when (colors.size) {
                0 -> return
                1 -> LinearGradient(0f, 0f, width.toFloat(), 0f, colors[0], colors[0], Shader.TileMode.CLAMP)
                else -> LinearGradient(
                    start[0] * width, start[1] * height, end[0] * width, end[1] * height,
                    colors, locations, Shader.TileMode.CLAMP,
                )
            }
        }
        val bounds = RectF(0f, 0f, width.toFloat(), height.toFloat())
        if (cornerRadius > 0f) {
            clip.reset()
            clip.addRoundRect(bounds, cornerRadius, cornerRadius, Path.Direction.CW)
            canvas.drawPath(clip, paint)
        } else {
            canvas.drawRect(bounds, paint)
        }
    }
}

/**
 * `BlurView`: Android has no view-scoped backdrop blur, so this snapshots
 * the window content beneath the view at reduced resolution on every
 * frame the root redraws, box-blurs it in two passes, and draws the result
 * under a tint chosen by `blur_type`. Children go on top.
 */
class BlurViewManager : TypedComponentManager<BlurViewProps>({ values, partial -> BlurViewProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = BlurView(context)

    override fun applyTyped(view: View, props: BlurViewProps, initial: Boolean) {
        val blur = view as BlurView
        if (props.has_blur_type || props.has_intensity || initial) {
            val merged = propsOf(blur)
            blur.configure(
                (merged.value("blur_type") as? String) ?: "regular",
                (merged.num("intensity") ?: 100.0).coerceIn(0.0, 100.0).toFloat() / 100f,
            )
        }
        if (props.values.has("border_radius")) blur.cornerRadius = pxF(propsOf(blur).num("border_radius") ?: 0.0)
        // A background color would hide the blur, so it is dropped.
        ViewStyler.apply(blur, JSONObject(props.values.toString()).apply { remove("background_color") })
    }
}

/** The blurring surface behind `BlurView`. */
class BlurView(context: Context) : PNFrameLayout(context) {
    /** Snapshot downscale factor; blur radii below are in snapshot pixels. */
    private val downscale = 6
    private var intensity = 1f
    private var tint = 0
    private var snapshot: Bitmap? = null
    private var snapshotCanvas: Canvas? = null
    private var drawing = false
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val tintPaint = Paint()
    private val clip = Path()
    var cornerRadius = 0f
        set(value) { field = value; invalidate() }

    private val preDraw = ViewTreeObserver.OnPreDrawListener {
        if (intensity > 0f && isShown && width > 0 && height > 0) capture()
        true
    }

    init {
        setWillNotDraw(false)
    }

    fun configure(type: String, intensity: Float) {
        this.intensity = intensity
        tint = tintFor(type)
        invalidate()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        viewTreeObserver.addOnPreDrawListener(preDraw)
    }

    override fun onDetachedFromWindow() {
        viewTreeObserver.removeOnPreDrawListener(preDraw)
        snapshot?.recycle()
        snapshot = null
        snapshotCanvas = null
        super.onDetachedFromWindow()
    }

    /** Render what sits behind this view into the downscaled snapshot and blur it. */
    private fun capture() {
        if (drawing) return
        val root = rootView ?: return
        if (root === this) return
        val w = max(1, width / downscale)
        val h = max(1, height / downscale)
        var bitmap = snapshot
        if (bitmap == null || bitmap.width != w || bitmap.height != h) {
            bitmap?.recycle()
            bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
            snapshot = bitmap
            snapshotCanvas = Canvas(bitmap)
        }
        val canvas = snapshotCanvas ?: return
        bitmap.eraseColor(Color.TRANSPARENT)
        val location = IntArray(2)
        val rootLocation = IntArray(2)
        getLocationInWindow(location)
        root.getLocationInWindow(rootLocation)
        canvas.save()
        canvas.scale(1f / downscale, 1f / downscale)
        canvas.translate(-(location[0] - rootLocation[0]).toFloat(), -(location[1] - rootLocation[1]).toFloat())
        drawing = true
        try {
            root.draw(canvas)
        } catch (error: Exception) {
            PNLog.swallowed("BlurView.capture", error)
        } finally {
            drawing = false
            canvas.restore()
        }
        val radius = max(1, (intensity * 4f).roundToInt())
        val checksum = BoxBlur.apply(bitmap, radius)
        // Only schedule a redraw when the backdrop actually changed, so a
        // static screen settles instead of redrawing forever.
        if (checksum != lastChecksum) {
            lastChecksum = checksum
            invalidate()
        }
    }

    private var lastChecksum = 0L

    override fun draw(canvas: Canvas) {
        // While the root is being captured, skip ourselves so the snapshot
        // holds only what's underneath.
        if (drawing) return
        super.draw(canvas)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val bounds = RectF(0f, 0f, width.toFloat(), height.toFloat())
        val save = canvas.save()
        if (cornerRadius > 0f) {
            clip.reset()
            clip.addRoundRect(bounds, cornerRadius, cornerRadius, Path.Direction.CW)
            canvas.clipPath(clip)
        }
        val bitmap = snapshot
        if (bitmap != null && intensity > 0f) {
            paint.alpha = (intensity * 255).roundToInt().coerceIn(0, 255)
            canvas.drawBitmap(bitmap, null, bounds, paint)
        }
        if (tint != 0) {
            tintPaint.color = tint
            tintPaint.alpha = (Color.alpha(tint) * intensity).roundToInt().coerceIn(0, 255)
            canvas.drawRect(bounds, tintPaint)
        }
        canvas.restoreToCount(save)
    }

    private fun tintFor(type: String): Int = when (type) {
        "light", "extra_light", "system_thin_material" -> Color.argb(150, 255, 255, 255)
        "dark", "system_thick_material" -> Color.argb(150, 0, 0, 0)
        "prominent", "system_chrome_material" -> Color.argb(200, 250, 250, 250)
        else -> Color.argb(110, 240, 240, 240)
    }
}

/** Two-pass box blur over an ARGB bitmap, in place. */
object BoxBlur {
    /** Blur `bitmap` by `radius` pixels and return a checksum of the result. */
    fun apply(bitmap: Bitmap, radius: Int): Long {
        val w = bitmap.width
        val h = bitmap.height
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
        if (radius > 0) {
            val buffer = IntArray(w * h)
            horizontal(pixels, buffer, w, h, radius)
            vertical(buffer, pixels, w, h, radius)
            bitmap.setPixels(pixels, 0, w, 0, 0, w, h)
        }
        var checksum = 1469598103934665603L
        for (pixel in pixels) checksum = (checksum xor pixel.toLong()) * 1099511628211L
        return checksum
    }

    private fun horizontal(src: IntArray, dst: IntArray, w: Int, h: Int, r: Int) {
        val window = r * 2 + 1
        for (y in 0 until h) {
            val row = y * w
            var a = 0; var red = 0; var g = 0; var b = 0
            for (i in -r..r) {
                val p = src[row + i.coerceIn(0, w - 1)]
                a += p ushr 24; red += (p shr 16) and 0xFF; g += (p shr 8) and 0xFF; b += p and 0xFF
            }
            for (x in 0 until w) {
                dst[row + x] = ((a / window) shl 24) or ((red / window) shl 16) or ((g / window) shl 8) or (b / window)
                val out = src[row + (x - r).coerceIn(0, w - 1)]
                val inc = src[row + (x + r + 1).coerceIn(0, w - 1)]
                a += (inc ushr 24) - (out ushr 24)
                red += ((inc shr 16) and 0xFF) - ((out shr 16) and 0xFF)
                g += ((inc shr 8) and 0xFF) - ((out shr 8) and 0xFF)
                b += (inc and 0xFF) - (out and 0xFF)
            }
        }
    }

    private fun vertical(src: IntArray, dst: IntArray, w: Int, h: Int, r: Int) {
        val window = r * 2 + 1
        for (x in 0 until w) {
            var a = 0; var red = 0; var g = 0; var b = 0
            for (i in -r..r) {
                val p = src[i.coerceIn(0, h - 1) * w + x]
                a += p ushr 24; red += (p shr 16) and 0xFF; g += (p shr 8) and 0xFF; b += p and 0xFF
            }
            for (y in 0 until h) {
                dst[y * w + x] = ((a / window) shl 24) or ((red / window) shl 16) or ((g / window) shl 8) or (b / window)
                val out = src[(y - r).coerceIn(0, h - 1) * w + x]
                val inc = src[(y + r + 1).coerceIn(0, h - 1) * w + x]
                a += (inc ushr 24) - (out ushr 24)
                red += ((inc shr 16) and 0xFF) - ((out shr 16) and 0xFF)
                g += ((inc shr 8) and 0xFF) - ((out shr 8) and 0xFF)
                b += (inc and 0xFF) - (out and 0xFF)
            }
        }
    }
}
