package com.pythonnative.runtime.views

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.drawable.Drawable

/**
 * Background drawable that renders an optional rounded fill plus four
 * independent border strips. Used for PythonNative's
 * `border_<side>_width` / `border_<side>_color` style props, which
 * `GradientDrawable`'s single uniform stroke cannot express.
 *
 * Widths are in pixels; sides are ordered left, top, right, bottom.
 * The fill color is mutable so animated `background_color` frames can
 * update it in place without allocating a new drawable.
 */
class PNBorderDrawable(
    private var hasBackground: Boolean,
    private var backgroundColor: Int,
    private val cornerRadius: Float,
    private val widths: FloatArray,
    private val colors: IntArray,
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
            paint.color = backgroundColor
            if (cornerRadius > 0f) {
                canvas.drawRoundRect(b, cornerRadius, cornerRadius, paint)
            } else {
                canvas.drawRect(b, paint)
            }
        }
        paint.style = Paint.Style.FILL
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

    override fun setAlpha(alpha: Int) {
        paint.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
}
