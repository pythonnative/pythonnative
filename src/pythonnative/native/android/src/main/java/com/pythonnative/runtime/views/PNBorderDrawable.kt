package com.pythonnative.runtime.views

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable
import kotlin.math.max

/**
 * Background drawable that renders an optional rounded fill plus four
 * independent border strips. Used for PythonNative's
 * `border_<side>_width` / `border_<side>_color` style props, which
 * `GradientDrawable`'s single uniform stroke cannot express.
 *
 * Widths are in pixels; sides are ordered left, top, right, bottom.
 * `borderStyle` is `solid` (default), `dashed`, or `dotted`; the two
 * patterned styles stroke each side with a [DashPathEffect] sized from
 * that side's width (see [dashIntervals]). The fill color is mutable so
 * animated `background_color` frames can update it in place without
 * allocating a new drawable.
 */
class PNBorderDrawable(
    private var hasBackground: Boolean,
    private var backgroundColor: Int,
    private val cornerRadius: Float,
    private val widths: FloatArray,
    private val colors: IntArray,
    private val borderStyle: String = "solid",
) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    /** Replace the fill color (used by animated background frames). */
    fun setFillColor(color: Int) {
        hasBackground = true
        backgroundColor = color
        invalidateSelf()
    }

    override fun draw(canvas: Canvas) {
        val b = RectF(bounds)
        if (hasBackground) {
            paint.style = Paint.Style.FILL
            paint.pathEffect = null
            paint.color = backgroundColor
            if (cornerRadius > 0f) {
                canvas.drawRoundRect(b, cornerRadius, cornerRadius, paint)
            } else {
                canvas.drawRect(b, paint)
            }
        }
        if (borderStyle == "dashed" || borderStyle == "dotted") {
            drawPatterned(canvas, b)
            return
        }
        paint.style = Paint.Style.FILL
        paint.pathEffect = null
        if (widths[0] > 0f) {
            paint.color = colors[0]
            canvas.drawRect(b.left, b.top, b.left + widths[0], b.bottom, paint)
        }
        if (widths[1] > 0f) {
            paint.color = colors[1]
            canvas.drawRect(b.left, b.top, b.right, b.top + widths[1], paint)
        }
        if (widths[2] > 0f) {
            paint.color = colors[2]
            canvas.drawRect(b.right - widths[2], b.top, b.right, b.bottom, paint)
        }
        if (widths[3] > 0f) {
            paint.color = colors[3]
            canvas.drawRect(b.left, b.bottom - widths[3], b.right, b.bottom, paint)
        }
    }

    /** Each side as a stroked line centered on the border strip, with the dash pattern for its width. */
    private fun drawPatterned(canvas: Canvas, b: RectF) {
        paint.style = Paint.Style.STROKE
        paint.strokeCap = if (borderStyle == "dotted") Paint.Cap.ROUND else Paint.Cap.BUTT
        fun side(width: Float, color: Int, x0: Float, y0: Float, x1: Float, y1: Float) {
            if (width <= 0f) return
            paint.strokeWidth = width
            paint.color = color
            val (dash, gap) = dashIntervals(borderStyle, width)
            paint.pathEffect = DashPathEffect(floatArrayOf(dash, gap), 0f)
            canvas.drawLine(x0, y0, x1, y1, paint)
        }
        side(widths[0], colors[0], b.left + widths[0] / 2f, b.top, b.left + widths[0] / 2f, b.bottom)
        side(widths[1], colors[1], b.left, b.top + widths[1] / 2f, b.right, b.top + widths[1] / 2f)
        side(widths[2], colors[2], b.right - widths[2] / 2f, b.top, b.right - widths[2] / 2f, b.bottom)
        side(widths[3], colors[3], b.left, b.bottom - widths[3] / 2f, b.right, b.bottom - widths[3] / 2f)
        paint.pathEffect = null
    }

    override fun setAlpha(alpha: Int) {
        paint.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT

    companion object {
        /**
         * `(dash, gap)` lengths in pixels for a `border_style` and stroke
         * width: dotted borders use square dots one width long with a
         * one-width gap; dashed borders use dashes three widths long with a
         * two-width gap, matching the browser renderer's proportions. `solid`
         * yields no gap.
         */
        fun dashIntervals(style: String, widthPx: Float): Pair<Float, Float> {
            val w = max(1f, widthPx)
            return when (style) {
                "dotted" -> w to w
                "dashed" -> 3f * w to 2f * w
                else -> w to 0f
            }
        }
    }
}
