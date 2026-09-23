package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.content.Context
import android.graphics.Paint
import android.graphics.Typeface
import android.text.Selection
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.TextPaint
import android.text.TextUtils
import android.text.method.LinkMovementMethod
import android.text.style.AbsoluteSizeSpan
import android.text.style.BackgroundColorSpan
import android.text.style.ClickableSpan
import android.text.style.ForegroundColorSpan
import android.text.style.MetricAffectingSpan
import android.text.style.StrikethroughSpan
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.TextView
import com.pythonnative.runtime.R
import com.pythonnative.runtime.assets.PNAssets
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.max

/** Text helpers shared by `Text`, `Button`, and `TextInput`. */
object TextStyle {
    private val boldWords = setOf("bold", "semibold", "black", "heavy", "extrabold", "extra_bold", "semi_bold")

    /** Whether `weight` (a name or a numeric weight) implies bold. */
    fun isBold(weight: Any?): Boolean {
        return when (weight) {
            is String -> weight.lowercase() in boldWords || (weight.toIntOrNull()?.let { it >= 600 } ?: false)
            is Number -> weight.toDouble() >= 600
            else -> false
        }
    }

    /** `Typeface` style constant for `weight` / `italic`. */
    fun typefaceStyle(weight: Any?, italic: Boolean): Int {
        val bold = isBold(weight)
        return when {
            bold && italic -> Typeface.BOLD_ITALIC
            bold -> Typeface.BOLD
            italic -> Typeface.ITALIC
            else -> Typeface.NORMAL
        }
    }

    /** Apply `text_transform` to `text`; `capitalize` upper-cases each word's first letter. */
    fun transform(text: String?, mode: String?): String {
        val s = text ?: ""
        return when (mode) {
            "uppercase" -> s.uppercase()
            "lowercase" -> s.lowercase()
            "capitalize" -> {
                val sb = StringBuilder(s.length)
                var atWordStart = true
                for (ch in s) {
                    if (ch.isWhitespace()) {
                        atWordStart = true
                        sb.append(ch)
                    } else {
                        sb.append(if (atWordStart) ch.uppercaseChar() else ch)
                        atWordStart = false
                    }
                }
                sb.toString()
            }
            else -> s
        }
    }

    /** Coerce a `shadow_offset` value (`{width, height}` or `[dx, dy]`) to `(dx, dy)`. */
    fun shadowOffset(value: Any?): Pair<Double, Double> {
        return when (value) {
            is JSONObject -> Pair(value.num("width") ?: 0.0, value.num("height") ?: 0.0)
            is JSONArray -> if (value.length() >= 2) Pair(JsonUtil.toDouble(value.opt(0)), JsonUtil.toDouble(value.opt(1))) else Pair(0.0, 0.0)
            else -> Pair(0.0, 0.0)
        }
    }

    /**
     * Build a spannable from a rich-text span list, applying `transform` per
     * span. Span font sizes are `sp` unless `fontScaling` is `false`
     * (`allow_font_scaling=False`), in which case they are `dp`.
     */
    fun buildSpannable(spans: JSONArray, transform: String?, fontScaling: Boolean = true, onSpanPress: ((Int) -> Unit)? = null): SpannableStringBuilder {
        val builder = SpannableStringBuilder()
        for (i in 0 until spans.length()) {
            val span = spans.optJSONObject(i) ?: continue
            val text = transform(span.str("text"), transform)
            if (text.isEmpty()) continue
            val start = builder.length
            builder.append(text)
            val end = builder.length
            fun set(obj: Any) = builder.setSpan(obj, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            if (onSpanPress != null && JsonUtil.truthy(span.value("pressable"))) set(PNPressableSpan(i, onSpanPress))
            try {
                PNColor.parse(span.value("color"))?.let { set(ForegroundColorSpan(it)) }
                PNColor.parse(span.value("background_color"))?.let { set(BackgroundColorSpan(it)) }
                span.num("font_size")?.let {
                    val unit = if (fontScaling) android.util.TypedValue.COMPLEX_UNIT_SP else android.util.TypedValue.COMPLEX_UNIT_DIP
                    set(AbsoluteSizeSpan(android.util.TypedValue.applyDimension(unit, it.toFloat(), com.pythonnative.runtime.PNBridge.context().resources.displayMetrics).toInt(), false))
                }
                var bold = JsonUtil.truthy(span.value("bold"))
                val weight = span.value("font_weight")
                if (!bold && weight != null) bold = isBold(weight)
                val italic = JsonUtil.truthy(span.value("italic"))
                val family = span.str("font_family")?.takeIf { it.isNotEmpty() }
                if (family != null) {
                    set(PNTypefaceSpan(typeface(family, weight ?: if (bold) "bold" else null, italic)))
                } else if (bold || italic) {
                    set(StyleSpan(typefaceStyle(if (bold) "bold" else null, italic)))
                }
                when (span.str("text_decoration")) {
                    "underline" -> set(UnderlineSpan())
                    "line_through" -> set(StrikethroughSpan())
                }
            } catch (e: Exception) {
                PNLog.swallowed("TextStyle.buildSpannable", e)
            }
        }
        return builder
    }

    /** `weight` (a name or number) as a 100-900 numeric weight. */
    fun numericWeight(weight: Any?): Int = when (weight) {
        is Number -> weight.toInt().coerceIn(100, 900)
        is String -> weight.toIntOrNull()?.coerceIn(100, 900) ?: when (weight.lowercase()) {
            "thin", "ultralight", "ultra_light" -> 100
            "extralight", "extra_light" -> 200
            "light" -> 300
            "medium" -> 500
            "semibold", "semi_bold" -> 600
            "bold" -> 700
            "extrabold", "extra_bold", "heavy" -> 800
            "black" -> 900
            else -> 400
        }
        else -> 400
    }

    /**
     * The typeface for `family`/`weight`/`italic`: a bundled face from
     * `app/assets/` when the family is bundled, otherwise a system family.
     */
    fun typeface(family: String?, weight: Any?, italic: Boolean): Typeface {
        val style = typefaceStyle(weight, italic)
        if (family.isNullOrEmpty()) return Typeface.defaultFromStyle(style)
        val bundled = PNAssets.typeface(family, numericWeight(weight), italic)
        if (bundled != null) {
            // Synthesize bold/italic only when the closest face lacks them.
            val face = PNAssets.fontFace(family, numericWeight(weight), italic)
            val needBold = isBold(weight) && (face == null || face.weight < 600)
            val needItalic = italic && (face == null || !face.italic)
            val synth = when {
                needBold && needItalic -> Typeface.BOLD_ITALIC
                needBold -> Typeface.BOLD
                needItalic -> Typeface.ITALIC
                else -> Typeface.NORMAL
            }
            return if (synth == Typeface.NORMAL) bundled else Typeface.create(bundled, synth)
        }
        return Typeface.create(family, style)
    }

    /** Apply font props (`font_family`, `font_weight`, `bold`, `italic`) from merged props. */
    fun applyTypeface(tv: TextView, merged: JSONObject) {
        val family = merged.str("font_family")
        val weight = merged.value("font_weight") ?: if (JsonUtil.truthy(merged.value("bold"))) "bold" else null
        val italic = JsonUtil.truthy(merged.value("italic"))
        tv.typeface = typeface(family, weight, italic)
    }
}

/**
 * A pressable rich-text span (`Text` child with `on_press`). Reports the
 * span index and leaves the text's own styling alone: no link color or
 * underline, unlike `URLSpan`.
 */
class PNPressableSpan(val index: Int, private val onPress: (Int) -> Unit) : ClickableSpan() {
    override fun onClick(widget: View) = onPress(index)
    override fun updateDrawState(ds: TextPaint) {}
}

/**
 * Link movement bounded by the glyphs, matching iOS and React Native: a
 * tap activates a [PNPressableSpan] only when it lands inside the line's
 * laid-out text. Stock `LinkMovementMethod` also fires the last span for
 * taps past the end of a line. A tap that activates a span is recorded on
 * the view so the label's own `on_press` listener skips it; a tap that
 * misses every span falls through to that listener.
 */
object PNSpanMovementMethod : LinkMovementMethod() {
    private val spanTapKey = R.id.pn_span_tap

    override fun onTouchEvent(widget: TextView, buffer: Spannable, event: MotionEvent): Boolean {
        val action = event.actionMasked
        if (action == MotionEvent.ACTION_DOWN) widget.setTag(spanTapKey, null)
        if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_DOWN) {
            val span = spanAt(widget, buffer, event.x, event.y)
            if (span == null) {
                Selection.removeSelection(buffer)
                return false
            }
            if (action == MotionEvent.ACTION_UP) {
                widget.setTag(spanTapKey, true)
                span.onClick(widget)
            }
            return true
        }
        return super.onTouchEvent(widget, buffer, event)
    }

    /** The pressable span under (`x`, `y`) in view coordinates, or `null` off the glyphs. */
    fun spanAt(widget: TextView, buffer: Spanned, x: Float, y: Float): PNPressableSpan? {
        val layout = widget.layout ?: return null
        val localX = x - widget.totalPaddingLeft + widget.scrollX
        val localY = y - widget.totalPaddingTop + widget.scrollY
        if (localY < 0f || localY > layout.height) return null
        val line = layout.getLineForVertical(localY.toInt())
        if (localX < layout.getLineLeft(line) || localX > layout.getLineRight(line)) return null
        return spanAtOffset(buffer, layout.getOffsetForHorizontal(line, localX))
    }

    /**
     * The pressable span covering character `offset`. A tap on the right
     * half of a span's last glyph resolves to the offset just past it, so a
     * span ending exactly at `offset` counts when no span starts there.
     */
    fun spanAtOffset(buffer: Spanned, offset: Int): PNPressableSpan? {
        // A zero-length query returns every span containing or touching `offset`.
        val candidates = buffer.getSpans(offset, offset, PNPressableSpan::class.java)
        return candidates.firstOrNull { buffer.getSpanStart(it) <= offset && offset < buffer.getSpanEnd(it) }
            ?: candidates.firstOrNull { buffer.getSpanEnd(it) == offset && offset > buffer.getSpanStart(it) }
    }

    /** Whether the gesture that just ended activated a span; clears the mark. */
    fun consumeSpanTap(widget: View): Boolean {
        val consumed = widget.getTag(spanTapKey) == true
        widget.setTag(spanTapKey, null)
        return consumed
    }
}

/** Span applying a concrete `Typeface` (API 24 compatible; `TypefaceSpan(Typeface)` needs 28). */
class PNTypefaceSpan(private val typeface: Typeface) : MetricAffectingSpan() {
    override fun updateDrawState(paint: TextPaint) = apply(paint)
    override fun updateMeasureState(paint: TextPaint) = apply(paint)

    private fun apply(paint: TextPaint) {
        val old = paint.typeface
        val oldStyle = old?.style ?: 0
        val fake = oldStyle and typeface.style.inv()
        if (fake and Typeface.BOLD != 0) paint.isFakeBoldText = true
        if (fake and Typeface.ITALIC != 0) paint.textSkewX = -0.25f
        paint.typeface = typeface
    }
}

/**
 * `Text` element: a `TextView` with rich spans, transforms, shadows, and
 * line limits.
 *
 * `ellipsize_mode` maps `head`/`middle`/`tail` onto `TextUtils.TruncateAt`;
 * `clip` disables ellipsizing and, for a single line, turns off wrapping
 * so the text is clipped horizontally. `allow_font_scaling=false` sizes
 * text in `dp` instead of `sp`, opting out of the user's font scale.
 * `on_press` makes the whole label clickable; spans flagged `pressable`
 * become [PNPressableSpan]s driven by a `LinkMovementMethod` and report
 * `on_span_press(index)`. `selectable` enables the platform selection
 * handles (a label with pressable spans keeps the click movement method).
 */
class TextManager : ComponentManager() {
    private val shadowKeys = listOf("text_shadow_color", "text_shadow_offset", "text_shadow_radius")

    override fun createView(context: Context, tag: Long, props: JSONObject): View = TextView(context)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = TextProps(props, validated = true)

        val tv = view as TextView
        val merged = propsOf(tv)
        val mergedTyped = TextProps(merged, validated = true)
        val fontScaling = mergedTyped.allow_font_scaling != false
        if (typed.has_spans || typed.has_text || typed.has_text_transform || typed.has_allow_font_scaling || typed.has_selectable) {
            val transform = merged.str("text_transform")
            val spans = merged.value("spans") as? JSONArray
            var pressableSpans = false
            if (spans != null && spans.length() > 0) {
                try {
                    tv.text = TextStyle.buildSpannable(spans, transform, fontScaling) { index -> PNComponentEvents.Text.on_span_press(tv, index.toLong()) }
                    pressableSpans = (0 until spans.length()).any { JsonUtil.truthy(spans.optJSONObject(it)?.value("pressable")) }
                } catch (e: Exception) {
                    tv.text = TextStyle.transform(merged.str("text"), transform)
                }
            } else {
                tv.text = TextStyle.transform(merged.str("text"), transform)
            }
            val selectable = mergedTyped.selectable == true
            if (pressableSpans) {
                tv.setTextIsSelectable(false)
                tv.movementMethod = PNSpanMovementMethod
                tv.highlightColor = android.graphics.Color.TRANSPARENT
            } else if (selectable) {
                tv.setTextIsSelectable(true)
            } else {
                tv.setTextIsSelectable(false)
                tv.movementMethod = null
            }
        }
        // Events travel in `_pn_events`, not as props: re-check the label's
        // own press whenever the wired event list changes.
        if (initial || props.has("_pn_events")) {
            if (hasEvent(tv, "on_press")) {
                tv.setOnClickListener { if (!PNSpanMovementMethod.consumeSpanTap(tv)) PNComponentEvents.Text.on_press(tv) }
            }
            else {
                tv.setOnClickListener(null)
                tv.isClickable = false
            }
        }
        if (typed.has_font_size || typed.has_allow_font_scaling) {
            val unit = if (fontScaling) android.util.TypedValue.COMPLEX_UNIT_SP else android.util.TypedValue.COMPLEX_UNIT_DIP
            tv.setTextSize(unit, (merged.num("font_size") ?: 17.0).toFloat())
        }
        if (typed.has_color) tv.setTextColor(PNColor.parse(props.value("color")) ?: defaultTextColor(tv))
        if (listOf("font_family", "font_weight", "italic", "bold").any { props.has(it) }) {
            try {
                TextStyle.applyTypeface(tv, merged)
            } catch (e: Exception) {
                PNLog.swallowed("TextManager.typeface", e)
            }
        }
        if (typed.has_max_lines || typed.has_ellipsize_mode) applyLines(tv, merged.num("max_lines"), mergedTyped.ellipsize_mode?.rawValue)
        if (typed.has_text_align) {
            tv.gravity = when (typed.text_align?.rawValue) {
                "center" -> Gravity.CENTER
                "right", "end" -> Gravity.END
                "justify" -> Gravity.START
                else -> Gravity.START
            }
        }
        if (typed.has_letter_spacing) {
            val spacing = typed.letter_spacing ?: 0.0
            // Android takes letter spacing in ems (a ratio of the font size).
            val size = merged.num("font_size") ?: 16.0
            tv.letterSpacing = (spacing / max(size, 1.0)).toFloat()
        }
        if (typed.has_line_height) {
            val size = merged.num("font_size") ?: 17.0
            tv.setLineSpacing(0f, ((typed.line_height ?: size) / max(size, 1.0)).toFloat())
        }
        if (typed.has_text_decoration) {
            var flags = tv.paintFlags and Paint.UNDERLINE_TEXT_FLAG.inv() and Paint.STRIKE_THRU_TEXT_FLAG.inv()
            when (typed.text_decoration?.rawValue) {
                "underline" -> flags = flags or Paint.UNDERLINE_TEXT_FLAG
                "line_through" -> flags = flags or Paint.STRIKE_THRU_TEXT_FLAG
            }
            tv.paintFlags = flags
        }
        if (shadowKeys.any { props.has(it) }) applyTextShadow(tv, merged)
        ViewStyler.apply(tv, props)
    }

    private fun defaultTextColor(view: TextView): Int {
        val value = android.util.TypedValue()
        view.context.theme.resolveAttribute(android.R.attr.textColorPrimary, value, true)
        return if (value.resourceId != 0) view.context.getColor(value.resourceId) else value.data
    }

    /**
     * Apply `max_lines` and `ellipsize_mode`. `clip` ellipsizes nothing; with
     * one line it also disables wrapping so overflow is clipped instead of
     * wrapped onto hidden lines.
     */
    private fun applyLines(tv: TextView, maxLines: Double?, mode: String?) {
        val lines = maxLines?.takeIf { it > 0 }?.toInt()
        if (lines == null) {
            tv.maxLines = Int.MAX_VALUE
            tv.ellipsize = null
            tv.setHorizontallyScrolling(false)
            return
        }
        tv.maxLines = lines
        tv.ellipsize = ellipsizeMode(mode)
        tv.setHorizontallyScrolling(mode == "clip" && lines == 1)
    }

    /** `TruncateAt` for an `ellipsize_mode`; `clip` yields `null` (no ellipsis). */
    fun ellipsizeMode(mode: String?): TextUtils.TruncateAt? = when (mode) {
        "head" -> TextUtils.TruncateAt.START
        "middle" -> TextUtils.TruncateAt.MIDDLE
        "clip" -> null
        "marquee" -> TextUtils.TruncateAt.MARQUEE
        else -> TextUtils.TruncateAt.END
    }

    private fun applyTextShadow(tv: TextView, merged: JSONObject) {
        if (shadowKeys.none { merged.value(it) != null }) {
            tv.setShadowLayer(0f, 0f, 0f, 0)
            return
        }
        val argb = PNColor.parseOr(merged.value("text_shadow_color") ?: "#000000", 0xFF000000.toInt())
        val (dx, dy) = TextStyle.shadowOffset(merged.value("text_shadow_offset"))
        var radiusPx = merged.num("text_shadow_radius")?.let { pxF(it) } ?: 0f
        // A zero radius with an offset hides the shadow on some renderers; use a hairline blur.
        if (radiusPx <= 0f && (dx != 0.0 || dy != 0.0)) radiusPx = 0.01f
        tv.setShadowLayer(radiusPx, pxF(dx), pxF(dy), argb)
    }

    override fun setAnimatedProperty(view: View, prop: String, value: Any?) {
        if (prop == "color" && view is TextView) {
            PNColor.parse(value)?.let { view.setTextColor(it) }
            return
        }
        super.setAnimatedProperty(view, prop, value)
    }
}
