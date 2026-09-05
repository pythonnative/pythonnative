package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.Paint
import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.TextUtils
import android.text.style.AbsoluteSizeSpan
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.StrikethroughSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.text.style.UnderlineSpan
import android.view.Gravity
import android.view.View
import android.widget.TextView
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

    /** Build a spannable from a rich-text span list, applying `transform` per span. */
    fun buildSpannable(spans: JSONArray, transform: String?): SpannableStringBuilder {
        val builder = SpannableStringBuilder()
        for (i in 0 until spans.length()) {
            val span = spans.optJSONObject(i) ?: continue
            val text = transform(span.str("text"), transform)
            if (text.isEmpty()) continue
            val start = builder.length
            builder.append(text)
            val end = builder.length
            fun set(obj: Any) = builder.setSpan(obj, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            try {
                PNColor.parse(span.value("color"))?.let { set(ForegroundColorSpan(it)) }
                PNColor.parse(span.value("background_color"))?.let { set(BackgroundColorSpan(it)) }
                span.num("font_size")?.let { set(AbsoluteSizeSpan(it.toInt(), true)) }
                var bold = JsonUtil.truthy(span.value("bold"))
                val weight = span.value("font_weight")
                if (!bold && weight != null) bold = isBold(weight)
                val italic = JsonUtil.truthy(span.value("italic"))
                if (bold || italic) set(StyleSpan(typefaceStyle(if (bold) "bold" else null, italic)))
                span.str("font_family")?.takeIf { it.isNotEmpty() }?.let { set(TypefaceSpan(it)) }
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

    /** Apply font props (`font_family`, `font_weight`, `bold`, `italic`) from merged props. */
    fun applyTypeface(tv: TextView, merged: JSONObject) {
        val family = merged.str("font_family")
        val weight = merged.value("font_weight") ?: if (JsonUtil.truthy(merged.value("bold"))) "bold" else null
        val italic = JsonUtil.truthy(merged.value("italic"))
        val style = typefaceStyle(weight, italic)
        if (!family.isNullOrEmpty()) {
            tv.setTypeface(Typeface.create(family, style))
        } else {
            tv.setTypeface(tv.typeface, style)
        }
    }
}

/** `Text` element: a `TextView` with rich spans, transforms, shadows, and line limits. */
class TextManager : ComponentManager() {
    private val shadowKeys = listOf("text_shadow_color", "text_shadow_offset", "text_shadow_radius")

    override fun createView(context: Context, tag: Long, props: JSONObject): View = TextView(context)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val tv = view as TextView
        val merged = propsOf(tv)
        if (props.has("spans") || props.has("text") || props.has("text_transform")) {
            val transform = merged.str("text_transform")
            val spans = merged.value("spans") as? JSONArray
            if (spans != null && spans.length() > 0) {
                try {
                    tv.text = TextStyle.buildSpannable(spans, transform)
                } catch (e: Exception) {
                    tv.text = TextStyle.transform(merged.str("text"), transform)
                }
            } else {
                tv.text = TextStyle.transform(merged.str("text"), transform)
            }
        }
        props.num("font_size")?.let { tv.textSize = it.toFloat() }
        PNColor.parse(props.value("color"))?.let { tv.setTextColor(it) }
        if (listOf("font_family", "font_weight", "italic", "bold").any { props.has(it) }) {
            try {
                TextStyle.applyTypeface(tv, merged)
            } catch (e: Exception) {
                PNLog.swallowed("TextManager.typeface", e)
            }
        }
        if (props.has("max_lines") || props.has("number_of_lines")) {
            val lines = merged.num("number_of_lines") ?: merged.num("max_lines")
            if (lines != null && lines > 0) {
                tv.maxLines = lines.toInt()
                tv.ellipsize = ellipsizeMode(merged.str("ellipsize_mode") ?: merged.str("ellipsize"))
            } else {
                tv.maxLines = Int.MAX_VALUE
                tv.ellipsize = null
            }
        }
        if (props.has("ellipsize_mode") || props.has("ellipsize")) {
            if (tv.maxLines != Int.MAX_VALUE) tv.ellipsize = ellipsizeMode(merged.str("ellipsize_mode") ?: merged.str("ellipsize"))
        }
        if (props.has("selectable")) tv.setTextIsSelectable(JsonUtil.truthy(props.value("selectable")))
        if (props.has("text_align")) {
            tv.gravity = when (props.str("text_align")) {
                "center" -> Gravity.CENTER
                "right", "end" -> Gravity.END
                "justify" -> Gravity.START
                else -> Gravity.START
            }
        }
        props.num("letter_spacing")?.let {
            // Android takes letter spacing in ems (a ratio of the font size).
            val size = merged.num("font_size") ?: 16.0
            tv.letterSpacing = (it / max(size, 1.0)).toFloat()
        }
        props.num("line_height")?.let {
            val size = merged.num("font_size") ?: 16.0
            tv.setLineSpacing(0f, (it / max(size, 1.0)).toFloat())
        }
        if (props.has("text_decoration")) {
            var flags = tv.paintFlags and Paint.UNDERLINE_TEXT_FLAG.inv() and Paint.STRIKE_THRU_TEXT_FLAG.inv()
            when (props.str("text_decoration")) {
                "underline" -> flags = flags or Paint.UNDERLINE_TEXT_FLAG
                "line_through" -> flags = flags or Paint.STRIKE_THRU_TEXT_FLAG
            }
            tv.paintFlags = flags
        }
        if (shadowKeys.any { props.has(it) }) applyTextShadow(tv, merged)
        ViewStyler.apply(tv, props)
    }

    private fun ellipsizeMode(mode: String?): TextUtils.TruncateAt = when (mode) {
        "head" -> TextUtils.TruncateAt.START
        "middle" -> TextUtils.TruncateAt.MIDDLE
        "clip" -> TextUtils.TruncateAt.END
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
