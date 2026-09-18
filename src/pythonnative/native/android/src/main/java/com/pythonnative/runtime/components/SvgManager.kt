package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.view.View
import com.pythonnative.generated.PNSvgShape
import com.pythonnative.generated.PNValues
import com.pythonnative.generated.SvgProps
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.graphics.SvgPath
import com.pythonnative.runtime.graphics.SvgTransform
import com.pythonnative.runtime.layout.NativeLayout
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * `Svg` element: one view that draws a list of flattened `SvgShape`
 * records with `Canvas`. Coordinates are in `view_box` units and are
 * mapped into the view's bounds according to `preserve_aspect_ratio`.
 */
class SvgManager : TypedComponentManager<SvgProps>({ values, partial -> SvgProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = SvgView(context)

    override fun applyTyped(view: View, props: SvgProps, initial: Boolean) {
        val svg = view as SvgView
        if (props.has_shapes) svg.shapes = props.shapes ?: emptyList()
        if (props.has_view_box) {
            svg.viewBox = SvgView.parseViewBox(props.view_box) ?: RectF(0f, 0f, 24f, 24f)
            recordOf(svg)?.let { NativeLayout.invalidate(it.tag) }
        }
        if (props.has_preserve_aspect_ratio) svg.preserveAspectRatio = props.preserve_aspect_ratio?.rawValue ?: "meet"
        val paintKeys = listOf("fill", "stroke", "stroke_width", "stroke_linecap", "stroke_linejoin", "fill_rule", "color")
        if (paintKeys.any { props.values.has(it) }) {
            val merged = propsOf(svg)
            svg.rootPaint = SvgPaint(
                fill = merged.str("fill"),
                stroke = merged.str("stroke"),
                strokeWidth = merged.value("stroke_width")?.let { PNValues.number(it).toFloat() },
                lineCap = merged.str("stroke_linecap"),
                lineJoin = merged.str("stroke_linejoin"),
                fillRule = merged.str("fill_rule"),
            )
            svg.currentColor = PNColor.parse(merged.value("color"))
        }
        svg.invalidate()
        ViewStyler.apply(svg, props.values)
    }

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        val svg = view as SvgView
        var w = svg.viewBox.width()
        var h = svg.viewBox.height()
        if (w <= 0f || h <= 0f) { w = 24f; h = 24f }
        if (maxWidth.isFinite() && maxWidth > 0 && maxWidth < 1e6 && w > maxWidth) {
            h *= (maxWidth / w).toFloat(); w = maxWidth.toFloat()
        }
        if (maxHeight.isFinite() && maxHeight > 0 && maxHeight < 1e6 && h > maxHeight) {
            w *= (maxHeight / h).toFloat(); h = maxHeight.toFloat()
        }
        return floatArrayOf(w, h)
    }
}

/** Root paint defaults applied to shapes that leave an attribute unset. */
data class SvgPaint(
    val fill: String? = null,
    val stroke: String? = null,
    val strokeWidth: Float? = null,
    val lineCap: String? = null,
    val lineJoin: String? = null,
    val fillRule: String? = null,
)

/** The drawing surface behind `Svg` (also used to rasterize tab bar icons). */
class SvgView(context: Context) : View(context) {
    var shapes: List<PNSvgShape> = emptyList()
        set(value) { field = value; invalidate() }
    var viewBox: RectF = RectF(0f, 0f, 24f, 24f)
        set(value) { field = value; invalidate() }
    var preserveAspectRatio: String = "meet"
        set(value) { field = value; invalidate() }
    var rootPaint: SvgPaint = SvgPaint()
        set(value) { field = value; invalidate() }
    /** What `currentColor` resolves to; null falls back to the theme's primary text color. */
    var currentColor: Int? = null
        set(value) { field = value; invalidate() }

    init {
        setWillNotDraw(false)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val bounds = RectF(0f, 0f, width.toFloat(), height.toFloat())
        SvgRenderer.draw(canvas, shapes, viewBox, preserveAspectRatio, rootPaint, currentColor ?: SvgRenderer.defaultColor(context), bounds)
    }

    companion object {
        /** Parse `"minx miny width height"` (commas allowed); null when malformed. */
        fun parseViewBox(text: String?): RectF? {
            if (text == null) return null
            val parts = text.split(' ', ',', '\n', '\t').filter { it.isNotEmpty() }.map { it.toFloatOrNull() ?: return null }
            if (parts.size != 4 || parts[2] <= 0f || parts[3] <= 0f) return null
            return RectF(parts[0], parts[1], parts[0] + parts[2], parts[1] + parts[3])
        }
    }
}

/** Stateless `Canvas` renderer for flattened shapes. */
object SvgRenderer {
    /** The transform from view box units to `bounds` for a `preserve_aspect_ratio` mode. */
    fun viewBoxTransform(viewBox: RectF, bounds: RectF, preserveAspectRatio: String): Matrix {
        val matrix = Matrix()
        if (viewBox.width() <= 0f || viewBox.height() <= 0f || bounds.width() <= 0f || bounds.height() <= 0f) return matrix
        val sx = bounds.width() / viewBox.width()
        val sy = bounds.height() / viewBox.height()
        var scaleX = sx
        var scaleY = sy
        when (preserveAspectRatio) {
            "none" -> {}
            "slice" -> { scaleX = max(sx, sy); scaleY = scaleX }
            else -> { scaleX = min(sx, sy); scaleY = scaleX }
        }
        val tx = bounds.left + (bounds.width() - viewBox.width() * scaleX) / 2f - viewBox.left * scaleX
        val ty = bounds.top + (bounds.height() - viewBox.height() * scaleY) / 2f - viewBox.top * scaleY
        matrix.setTranslate(tx, ty)
        matrix.preScale(scaleX, scaleY)
        return matrix
    }

    /** Draw `shapes` into `bounds` on `canvas`. */
    fun draw(canvas: Canvas, shapes: List<PNSvgShape>, viewBox: RectF, preserveAspectRatio: String, root: SvgPaint, currentColor: Int, bounds: RectF) {
        if (shapes.isEmpty()) return
        val save = canvas.save()
        try {
            if (preserveAspectRatio == "slice") canvas.clipRect(bounds)
            canvas.concat(viewBoxTransform(viewBox, bounds, preserveAspectRatio))
            val paint = Paint(Paint.ANTI_ALIAS_FLAG)
            for (shape in shapes) drawShape(canvas, shape, root, currentColor, paint)
        } catch (error: Exception) {
            PNLog.swallowed("SvgRenderer.draw", error)
        } finally {
            canvas.restoreToCount(save)
        }
    }

    private fun drawShape(canvas: Canvas, shape: PNSvgShape, root: SvgPaint, currentColor: Int, paint: Paint) {
        val geometry = geometry(shape) ?: return
        val transform = shape.transform?.let { SvgTransform.parse(it) }
        val path = if (transform != null) Path(geometry).also { it.transform(transform) } else geometry
        val opacity = (shape.opacity ?: 1.0).coerceIn(0.0, 1.0).toFloat()

        val fill = resolve(shape.fill ?: root.fill ?: "none", currentColor)
        if (fill != null) {
            paint.reset()
            paint.isAntiAlias = true
            paint.style = Paint.Style.FILL
            paint.color = withAlpha(fill, ((shape.fill_opacity ?: 1.0).toFloat() * opacity))
            path.fillType = if ((shape.fill_rule?.rawValue ?: root.fillRule) == "evenodd") Path.FillType.EVEN_ODD else Path.FillType.WINDING
            canvas.drawPath(path, paint)
        }
        val stroke = resolve(shape.stroke ?: root.stroke ?: "none", currentColor)
        val width = (shape.stroke_width ?: root.strokeWidth?.toDouble() ?: 1.0).toFloat()
        if (stroke != null && width > 0f) {
            paint.reset()
            paint.isAntiAlias = true
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = width
            paint.color = withAlpha(stroke, ((shape.stroke_opacity ?: 1.0).toFloat() * opacity))
            paint.strokeCap = when (shape.stroke_linecap?.rawValue ?: root.lineCap) {
                "round" -> Paint.Cap.ROUND
                "square" -> Paint.Cap.SQUARE
                else -> Paint.Cap.BUTT
            }
            paint.strokeJoin = when (shape.stroke_linejoin?.rawValue ?: root.lineJoin) {
                "round" -> Paint.Join.ROUND
                "bevel" -> Paint.Join.BEVEL
                else -> Paint.Join.MITER
            }
            val dashes = shape.stroke_dasharray?.map { it.toFloat() }?.filter { it >= 0f }
            if (!dashes.isNullOrEmpty() && dashes.any { it > 0f }) {
                val pattern = if (dashes.size % 2 == 1) dashes + dashes else dashes
                paint.pathEffect = DashPathEffect(pattern.toFloatArray(), 0f)
            }
            canvas.drawPath(path, paint)
        }
    }

    /** Parse a paint value; `"none"` and unparseable colors yield null. */
    /**
     * Resolve a paint value: a color string (`none` clears, `currentColor`
     * inherits), a `{"light","dark"}` dynamic color, or a typed contract
     * value wrapping either.
     */
    fun resolve(value: Any?, currentColor: Int): Int? {
        val raw = when (value) {
            null -> return null
            is com.pythonnative.generated.PNNativeValue -> value.nativeValue()
            else -> value
        }
        if (raw !is String) return PNColor.parse(raw)
        val trimmed = raw.trim()
        if (trimmed.isEmpty() || trimmed.equals("none", ignoreCase = true)) return null
        if (trimmed.equals("currentColor", ignoreCase = true)) return currentColor
        return PNColor.parse(trimmed)
    }

    private fun withAlpha(color: Int, multiplier: Float): Int {
        val alpha = (Color.alpha(color) * multiplier.coerceIn(0f, 1f)).roundToInt().coerceIn(0, 255)
        return Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color))
    }

    /** The untransformed path for a shape, or null for degenerate geometry. */
    fun geometry(shape: PNSvgShape): Path? {
        return when (shape.kind.rawValue) {
            "path" -> shape.d?.let { SvgPath.parse(it) }
            "circle" -> {
                val r = (shape.r ?: 0.0).toFloat()
                if (r <= 0f) null else Path().apply {
                    addCircle((shape.cx ?: 0.0).toFloat(), (shape.cy ?: 0.0).toFloat(), r, Path.Direction.CW)
                }
            }
            "ellipse" -> {
                val rx = (shape.rx ?: 0.0).toFloat(); val ry = (shape.ry ?: 0.0).toFloat()
                if (rx <= 0f || ry <= 0f) null else Path().apply {
                    val cx = (shape.cx ?: 0.0).toFloat(); val cy = (shape.cy ?: 0.0).toFloat()
                    addOval(RectF(cx - rx, cy - ry, cx + rx, cy + ry), Path.Direction.CW)
                }
            }
            "rect" -> {
                val w = (shape.width ?: 0.0).toFloat(); val h = (shape.height ?: 0.0).toFloat()
                if (w <= 0f || h <= 0f) null else Path().apply {
                    val x = (shape.x ?: 0.0).toFloat(); val y = (shape.y ?: 0.0).toFloat()
                    val rx = (shape.rx ?: shape.ry ?: 0.0).toFloat(); val ry = (shape.ry ?: shape.rx ?: 0.0).toFloat()
                    val rect = RectF(x, y, x + w, y + h)
                    if (rx > 0f || ry > 0f) addRoundRect(rect, rx, ry, Path.Direction.CW) else addRect(rect, Path.Direction.CW)
                }
            }
            "line" -> Path().apply {
                moveTo((shape.x1 ?: 0.0).toFloat(), (shape.y1 ?: 0.0).toFloat())
                lineTo((shape.x2 ?: 0.0).toFloat(), (shape.y2 ?: 0.0).toFloat())
            }
            "polyline", "polygon" -> {
                val values = (shape.points ?: "").split(' ', ',', '\n', '\t').filter { it.isNotEmpty() }.mapNotNull { it.toFloatOrNull() }
                if (values.size < 4) null else Path().apply {
                    moveTo(values[0], values[1])
                    var i = 2
                    while (i + 1 < values.size) { lineTo(values[i], values[i + 1]); i += 2 }
                    if (shape.kind.rawValue == "polygon") close()
                }
            }
            else -> null
        }
    }

    /** Rasterize `shapes` to a bitmap of `size` dp (used for tab bar icons). */
    fun bitmap(shapes: List<PNSvgShape>, viewBox: RectF, sizeDp: Float, root: SvgPaint, color: Int, density: Float): Bitmap {
        val px = max(1, (sizeDp * density).roundToInt())
        val bitmap = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888)
        bitmap.density = (density * 160).roundToInt()
        val canvas = Canvas(bitmap)
        draw(canvas, shapes, viewBox, "meet", root, color, RectF(0f, 0f, px.toFloat(), px.toFloat()))
        return bitmap
    }

    /** The theme's primary text color (what `currentColor` means by default). */
    fun defaultColor(context: Context): Int {
        val value = android.util.TypedValue()
        return try {
            context.theme.resolveAttribute(android.R.attr.textColorPrimary, value, true)
            if (value.resourceId != 0) context.getColor(value.resourceId) else if (value.data != 0) value.data else Color.BLACK
        } catch (_: Exception) {
            Color.BLACK
        }
    }
}
