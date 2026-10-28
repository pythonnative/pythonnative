package com.pythonnative.runtime.text

import android.content.Context
import android.graphics.Typeface
import android.os.Build
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import android.text.TextUtils
import android.util.TypedValue
import android.widget.TextView
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.components.TextStyle
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/**
 * `Text` measurement on any thread: a `StaticLayout` built from a
 * `TextPaint` with the parameters `TextManager` gives its `TextView`.
 *
 * `TextView` still draws the text. It builds its own layout from the same
 * inputs (text, spans, paint, width, line spacing, break strategy,
 * hyphenation, padding, and line limits), so the measured size and the
 * drawn layout agree; [TextDefaults] captures the theme's values once on
 * the main thread so both start from the same defaults.
 */
class PNTextLayout private constructor(
    val layout: StaticLayout,
    private val lines: Int,
    private val density: Float,
    /** The width `TextView` would measure, in dp (a clipped line's layout is wider). */
    val width: Float,
) {
    /** The measured height in dp. */
    val height: Float get() = layout.getLineTop(lines) / density

    /** The first baseline in dp. */
    val baseline: Float get() = layout.getLineBaseline(0) / density

    /** The theme defaults a fresh `TextView` starts with. */
    class TextDefaults(
        val textSizePx: Float,
        val typeface: Typeface?,
        val includeFontPadding: Boolean,
        val breakStrategy: Int,
        val hyphenationFrequency: Int,
        val fallbackLineSpacing: Boolean,
    ) {
        companion object {
            /** Read the defaults from a prototype `TextView`; call on the main thread. */
            fun capture(context: Context): TextDefaults {
                val view = TextView(context)
                return TextDefaults(
                    view.textSize,
                    view.typeface,
                    view.includeFontPadding,
                    view.breakStrategy,
                    view.hyphenationFrequency,
                    if (Build.VERSION.SDK_INT >= 28) view.isFallbackLineSpacing else false,
                )
            }
        }
    }

    companion object {
        /**
         * Lay out `props` within `maxWidth` dp (infinite or `>= 1e6` means
         * unconstrained), the way `TextView.onMeasure` does with `AT_MOST`.
         */
        fun build(context: Context, defaults: TextDefaults, props: JSONObject, maxWidth: Double): PNTextLayout {
            val metrics = context.resources.displayMetrics
            val density = if (metrics.density > 0f) metrics.density else 1f
            val fontScaling = props.value("allow_font_scaling") != false
            val unit = if (fontScaling) TypedValue.COMPLEX_UNIT_SP else TypedValue.COMPLEX_UNIT_DIP
            val size = props.num("font_size")
            val paint = TextPaint(TextPaint.ANTI_ALIAS_FLAG)
            paint.density = density
            paint.textSize = size?.let { TypedValue.applyDimension(unit, it.toFloat(), metrics) } ?: defaults.textSizePx
            val family = props.str("font_family")
            val weight = props.value("font_weight") ?: if (JsonUtil.truthy(props.value("bold"))) "bold" else null
            val italic = JsonUtil.truthy(props.value("italic"))
            paint.typeface = if (family != null || weight != null || italic) TextStyle.typeface(family, weight, italic) else defaults.typeface
            props.num("letter_spacing")?.let { paint.letterSpacing = (it / max(size ?: 16.0, 1.0)).toFloat() }
            val lineSpacing = props.num("line_height")?.let { (it / max(size ?: 17.0, 1.0)).toFloat() } ?: 1f

            val transform = props.str("text_transform")
            val spans = props.value("spans") as? JSONArray
            val text: CharSequence = if (spans != null && spans.length() > 0) {
                try { TextStyle.buildSpannable(spans, transform, fontScaling) } catch (_: Exception) { TextStyle.transform(props.str("text"), transform) }
            } else TextStyle.transform(props.str("text"), transform)

            val maxLines = props.num("max_lines")?.takeIf { it > 0 }?.toInt()
            val mode = props.str("ellipsize_mode")
            val unbounded = maxWidth.isNaN() || maxWidth.isInfinite() || maxWidth >= 1e6
            val limit = if (unbounded) Int.MAX_VALUE else (max(0.0, maxWidth) * density).toInt()
            val desired = ceil(Layout.getDesiredWidth(text, paint)).toInt()
            // A single clipped line scrolls horizontally in TextView, so it never wraps.
            val clipped = mode == "clip" && maxLines == 1
            val width = min(desired, limit).coerceAtLeast(0)
            val layoutWidth = if (clipped) max(desired, width) else width
            val builder = StaticLayout.Builder.obtain(text, 0, text.length, paint, layoutWidth)
                .setAlignment(Layout.Alignment.ALIGN_NORMAL)
                .setTextDirection(TextDirectionHeuristics.FIRSTSTRONG_LTR)
                .setLineSpacing(0f, lineSpacing)
                .setIncludePad(defaults.includeFontPadding)
                .setBreakStrategy(defaults.breakStrategy)
                .setHyphenationFrequency(defaults.hyphenationFrequency)
            if (Build.VERSION.SDK_INT >= 28) builder.setUseLineSpacingFromFallbacks(defaults.fallbackLineSpacing)
            if (maxLines != null) {
                builder.setMaxLines(maxLines)
                ellipsize(mode)?.let { builder.setEllipsize(it).setEllipsizedWidth(layoutWidth) }
            }
            val layout = builder.build()
            val lines = min(layout.lineCount, maxLines ?: Int.MAX_VALUE).coerceAtLeast(1)
            return PNTextLayout(layout, lines, density, width / density)
        }

        private fun ellipsize(mode: String?): TextUtils.TruncateAt? = when (mode) {
            "head" -> TextUtils.TruncateAt.START
            "middle" -> TextUtils.TruncateAt.MIDDLE
            "clip", "marquee" -> null
            else -> TextUtils.TruncateAt.END
        }
    }
}
