package com.pythonnative.generated

import org.json.JSONArray
import org.json.JSONObject

/** Presence of a nonrequired nullable record field, including explicit null. */
sealed interface PNPresence<out T> {
    data object Absent : PNPresence<Nothing>
    data class Present<T>(val value: T) : PNPresence<T>
}

/** Only portable native values implement this interface. */
interface PNNativeValue { fun nativeValue(): Any }

data class PNJSONValue(val value: Any) : PNNativeValue {
    init { PNValues.encode(value) }
    override fun nativeValue(): Any = PNValues.encode(value)
}

/** Recursive codecs shared by component props, events, and native methods. */
object PNValues {
    fun withoutNulls(value: JSONObject): JSONObject = JSONObject().also { result ->
        for (key in value.keys()) if (!value.isNull(key)) result.put(key, value.get(key))
    }
    fun encode(value: Any?): Any = when (value) {
        null, JSONObject.NULL -> JSONObject.NULL
        is PNNativeValue -> value.nativeValue()
        is String, is Boolean -> value
        is Number -> {
            require(value.toDouble().isFinite()) { "Native numbers must be finite" }
            value
        }
        is JSONObject -> JSONObject().also { out -> for (key in value.keys()) out.put(key, encode(value.get(key))) }
        is JSONArray -> JSONArray().also { out -> for (index in 0 until value.length()) out.put(encode(value.get(index))) }
        is List<*> -> JSONArray().also { out -> value.forEach { out.put(encode(it)) } }
        is Map<*, *> -> JSONObject().also { out -> value.forEach { (key, item) ->
            require(key is String) { "Native mappings require string keys" }; out.put(key, encode(item))
        } }
        else -> throw IllegalArgumentException("Unsupported native value: ${value.javaClass.name}")
    }

    fun string(value: Any?): String = value as? String ?: throw IllegalArgumentException("Expected string")
    fun boolean(value: Any?): Boolean = value as? Boolean ?: throw IllegalArgumentException("Expected boolean")
    fun number(value: Any?): Double {
        require(value is Number && value.toDouble().isFinite()) { "Expected finite number" }
        return value.toDouble()
    }
    fun integer(value: Any?): Long {
        val number = number(value)
        require(kotlin.math.abs(number) <= 9007199254740991.0 && number == number.toLong().toDouble()) { "Expected portable integer" }
        return number.toLong()
    }
    fun objectValue(value: Any?): JSONObject = value as? JSONObject ?: throw IllegalArgumentException("Expected object")
    fun array(value: Any?): List<Any> {
        require(value is JSONArray) { "Expected array" }
        return (0 until value.length()).map { value.get(it) }
    }
    fun isNull(value: Any?): Boolean = value == null || value == JSONObject.NULL
    fun defaultValue(json: String): Any = JSONArray("[$json]").get(0)
}

sealed class PNViewWidth : PNNativeValue {
    data class Option0(val value: Long) : PNViewWidth() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Double) : PNViewWidth() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: String) : PNViewWidth() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewWidth {
            try { return Option0(PNValues.integer(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.number(value)) } catch (_: Exception) { }
            try { return Option2(PNValues.string(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewWidth")
        }
    }
}

enum class PNViewFlexDirection(val rawValue: String) : PNNativeValue {
    `row`("row"),
    `column`("column"),
    `row_reverse`("row_reverse"),
    `column_reverse`("column_reverse");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewFlexDirection = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewFlexDirection")
    }
}

enum class PNViewFlexWrap(val rawValue: String) : PNNativeValue {
    `nowrap`("nowrap"),
    `wrap`("wrap"),
    `wrap_reverse`("wrap_reverse");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewFlexWrap = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewFlexWrap")
    }
}

enum class PNViewJustifyContent(val rawValue: String) : PNNativeValue {
    `flex_start`("flex_start"),
    `center`("center"),
    `flex_end`("flex_end"),
    `space_between`("space_between"),
    `space_around`("space_around"),
    `space_evenly`("space_evenly"),
    `start`("start"),
    `leading`("leading"),
    `top`("top"),
    `end`("end"),
    `trailing`("trailing"),
    `bottom`("bottom");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewJustifyContent = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewJustifyContent")
    }
}

enum class PNViewAlignItems(val rawValue: String) : PNNativeValue {
    `stretch`("stretch"),
    `flex_start`("flex_start"),
    `center`("center"),
    `flex_end`("flex_end"),
    `baseline`("baseline"),
    `auto`("auto"),
    `start`("start"),
    `leading`("leading"),
    `top`("top"),
    `end`("end"),
    `trailing`("trailing"),
    `bottom`("bottom"),
    `fill`("fill");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewAlignItems = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewAlignItems")
    }
}

enum class PNViewAlignContent(val rawValue: String) : PNNativeValue {
    `flex_start`("flex_start"),
    `center`("center"),
    `flex_end`("flex_end"),
    `stretch`("stretch"),
    `space_between`("space_between"),
    `space_around`("space_around"),
    `space_evenly`("space_evenly");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewAlignContent = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewAlignContent")
    }
}

enum class PNViewDirection(val rawValue: String) : PNNativeValue {
    `ltr`("ltr"),
    `rtl`("rtl");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewDirection = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewDirection")
    }
}

enum class PNViewDisplay(val rawValue: String) : PNNativeValue {
    `flex`("flex"),
    `none`("none");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewDisplay = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewDisplay")
    }
}

enum class PNViewPosition(val rawValue: String) : PNNativeValue {
    `relative`("relative"),
    `absolute`("absolute");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewPosition = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewPosition")
    }
}

data class PNEdgeInsets(
    val `top`: PNViewWidth?,
    val `right`: PNViewWidth?,
    val `bottom`: PNViewWidth?,
    val `left`: PNViewWidth?,
    val `horizontal`: PNViewWidth?,
    val `vertical`: PNViewWidth?,
    val `all`: PNViewWidth?
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        if (`top` != null) result.put("top", PNValues.encode(`top`))
        if (`right` != null) result.put("right", PNValues.encode(`right`))
        if (`bottom` != null) result.put("bottom", PNValues.encode(`bottom`))
        if (`left` != null) result.put("left", PNValues.encode(`left`))
        if (`horizontal` != null) result.put("horizontal", PNValues.encode(`horizontal`))
        if (`vertical` != null) result.put("vertical", PNValues.encode(`vertical`))
        if (`all` != null) result.put("all", PNValues.encode(`all`))
    }
    companion object {
        fun decode(value: Any?): PNEdgeInsets {
            val objectValue = PNValues.objectValue(value)
            return PNEdgeInsets(if (PNValues.isNull(objectValue.opt("top"))) null else PNViewWidth.decode((objectValue.opt("top"))), if (PNValues.isNull(objectValue.opt("right"))) null else PNViewWidth.decode((objectValue.opt("right"))), if (PNValues.isNull(objectValue.opt("bottom"))) null else PNViewWidth.decode((objectValue.opt("bottom"))), if (PNValues.isNull(objectValue.opt("left"))) null else PNViewWidth.decode((objectValue.opt("left"))), if (PNValues.isNull(objectValue.opt("horizontal"))) null else PNViewWidth.decode((objectValue.opt("horizontal"))), if (PNValues.isNull(objectValue.opt("vertical"))) null else PNViewWidth.decode((objectValue.opt("vertical"))), if (PNValues.isNull(objectValue.opt("all"))) null else PNViewWidth.decode((objectValue.opt("all"))))
        }
    }
}

sealed class PNViewPadding : PNNativeValue {
    data class Option0(val value: Long) : PNViewPadding() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Double) : PNViewPadding() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: String) : PNViewPadding() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option3(val value: PNEdgeInsets) : PNViewPadding() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewPadding {
            try { return Option0(PNValues.integer(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.number(value)) } catch (_: Exception) { }
            try { return Option2(PNValues.string(value)) } catch (_: Exception) { }
            try { return Option3(PNEdgeInsets.decode(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewPadding")
        }
    }
}

enum class PNPNViewMargin3(val rawValue: String) : PNNativeValue {
    `auto`("auto");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNPNViewMargin3 = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNPNViewMargin3")
    }
}

sealed class PNViewMargin : PNNativeValue {
    data class Option0(val value: Long) : PNViewMargin() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Double) : PNViewMargin() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: String) : PNViewMargin() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option3(val value: PNPNViewMargin3) : PNViewMargin() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option4(val value: PNEdgeInsets) : PNViewMargin() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewMargin {
            try { return Option0(PNValues.integer(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.number(value)) } catch (_: Exception) { }
            try { return Option2(PNValues.string(value)) } catch (_: Exception) { }
            try { return Option3(PNPNViewMargin3.decode(value)) } catch (_: Exception) { }
            try { return Option4(PNEdgeInsets.decode(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewMargin")
        }
    }
}

sealed class PNViewMarginTop : PNNativeValue {
    data class Option0(val value: Long) : PNViewMarginTop() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Double) : PNViewMarginTop() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: String) : PNViewMarginTop() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option3(val value: PNPNViewMargin3) : PNViewMarginTop() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewMarginTop {
            try { return Option0(PNValues.integer(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.number(value)) } catch (_: Exception) { }
            try { return Option2(PNValues.string(value)) } catch (_: Exception) { }
            try { return Option3(PNPNViewMargin3.decode(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewMarginTop")
        }
    }
}

enum class PNViewOverflow(val rawValue: String) : PNNativeValue {
    `visible`("visible"),
    `hidden`("hidden"),
    `scroll`("scroll");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewOverflow = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewOverflow")
    }
}

enum class PNViewFontWeight(val rawValue: String) : PNNativeValue {
    `normal`("normal"),
    `bold`("bold"),
    `value_100`("100"),
    `value_200`("200"),
    `value_300`("300"),
    `value_400`("400"),
    `value_500`("500"),
    `value_600`("600"),
    `value_700`("700"),
    `value_800`("800"),
    `value_900`("900");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewFontWeight = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewFontWeight")
    }
}

enum class PNViewTextAlign(val rawValue: String) : PNNativeValue {
    `left`("left"),
    `center`("center"),
    `right`("right"),
    `justify`("justify"),
    `start`("start"),
    `end`("end");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewTextAlign = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewTextAlign")
    }
}

enum class PNViewTextDecoration(val rawValue: String) : PNNativeValue {
    `none`("none"),
    `underline`("underline"),
    `line_through`("line_through");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewTextDecoration = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewTextDecoration")
    }
}

enum class PNViewTextTransform(val rawValue: String) : PNNativeValue {
    `none`("none"),
    `uppercase`("uppercase"),
    `lowercase`("lowercase"),
    `capitalize`("capitalize");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewTextTransform = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewTextTransform")
    }
}

data class PNShadowOffset(
    val `width`: Double,
    val `height`: Double
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("width", PNValues.encode(`width`))
        result.put("height", PNValues.encode(`height`))
    }
    companion object {
        fun decode(value: Any?): PNShadowOffset {
            val objectValue = PNValues.objectValue(value)
            return PNShadowOffset(PNValues.number((objectValue.get("width"))), PNValues.number((objectValue.get("height"))))
        }
    }
}

data class PNPNViewTextShadowOffset1(
    val `item0`: Double,
    val `item1`: Double
) : PNNativeValue {
    override fun nativeValue(): Any = JSONArray().also { result ->
        result.put(PNValues.encode(`item0`))
        result.put(PNValues.encode(`item1`))
    }
    companion object {
        fun decode(value: Any?): PNPNViewTextShadowOffset1 {
            val items = PNValues.array(value)
            require(items.size == 2) { "Tuple length" }
            return PNPNViewTextShadowOffset1(PNValues.number(items[0]), PNValues.number(items[1]))
        }
    }
}

sealed class PNViewTextShadowOffset : PNNativeValue {
    data class Option0(val value: PNShadowOffset) : PNViewTextShadowOffset() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: PNPNViewTextShadowOffset1) : PNViewTextShadowOffset() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: List<Double>) : PNViewTextShadowOffset() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewTextShadowOffset {
            try { return Option0(PNShadowOffset.decode(value)) } catch (_: Exception) { }
            try { return Option1(PNPNViewTextShadowOffset1.decode(value)) } catch (_: Exception) { }
            try { return Option2(PNValues.array(value).map { item -> PNValues.number(item) }) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewTextShadowOffset")
        }
    }
}

sealed class PNPNTransformRotateRotate : PNNativeValue {
    data class Option0(val value: Double) : PNPNTransformRotateRotate() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: String) : PNPNTransformRotateRotate() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNPNTransformRotateRotate {
            try { return Option0(PNValues.number(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.string(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNPNTransformRotateRotate")
        }
    }
}

data class PNTransformRotate(
    val `rotate`: PNPNTransformRotateRotate
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("rotate", PNValues.encode(`rotate`))
    }
    companion object {
        fun decode(value: Any?): PNTransformRotate {
            val objectValue = PNValues.objectValue(value)
            return PNTransformRotate(PNPNTransformRotateRotate.decode((objectValue.get("rotate"))))
        }
    }
}

data class PNTransformScale(
    val `scale`: Double
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("scale", PNValues.encode(`scale`))
    }
    companion object {
        fun decode(value: Any?): PNTransformScale {
            val objectValue = PNValues.objectValue(value)
            return PNTransformScale(PNValues.number((objectValue.get("scale"))))
        }
    }
}

data class PNTransformScaleX(
    val `scale_x`: Double
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("scale_x", PNValues.encode(`scale_x`))
    }
    companion object {
        fun decode(value: Any?): PNTransformScaleX {
            val objectValue = PNValues.objectValue(value)
            return PNTransformScaleX(PNValues.number((objectValue.get("scale_x"))))
        }
    }
}

data class PNTransformScaleY(
    val `scale_y`: Double
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("scale_y", PNValues.encode(`scale_y`))
    }
    companion object {
        fun decode(value: Any?): PNTransformScaleY {
            val objectValue = PNValues.objectValue(value)
            return PNTransformScaleY(PNValues.number((objectValue.get("scale_y"))))
        }
    }
}

data class PNTransformTranslate(
    val `translate_x`: Double?,
    val `translate_y`: Double?
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        if (`translate_x` != null) result.put("translate_x", PNValues.encode(`translate_x`))
        if (`translate_y` != null) result.put("translate_y", PNValues.encode(`translate_y`))
    }
    companion object {
        fun decode(value: Any?): PNTransformTranslate {
            val objectValue = PNValues.objectValue(value)
            return PNTransformTranslate(if (PNValues.isNull(objectValue.opt("translate_x"))) null else PNValues.number((objectValue.opt("translate_x"))), if (PNValues.isNull(objectValue.opt("translate_y"))) null else PNValues.number((objectValue.opt("translate_y"))))
        }
    }
}

sealed class PNPNViewTransform6Item : PNNativeValue {
    data class Option0(val value: PNTransformRotate) : PNPNViewTransform6Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: PNTransformScale) : PNPNViewTransform6Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: PNTransformScaleX) : PNPNViewTransform6Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option3(val value: PNTransformScaleY) : PNPNViewTransform6Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option4(val value: PNTransformTranslate) : PNPNViewTransform6Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option5(val value: Map<String, PNJSONValue>) : PNPNViewTransform6Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNPNViewTransform6Item {
            try { return Option0(PNTransformRotate.decode(value)) } catch (_: Exception) { }
            try { return Option1(PNTransformScale.decode(value)) } catch (_: Exception) { }
            try { return Option2(PNTransformScaleX.decode(value)) } catch (_: Exception) { }
            try { return Option3(PNTransformScaleY.decode(value)) } catch (_: Exception) { }
            try { return Option4(PNTransformTranslate.decode(value)) } catch (_: Exception) { }
            try { return Option5(PNValues.objectValue(value).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNJSONValue(objectValue.get(key) ?: JSONObject.NULL) } }) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNPNViewTransform6Item")
        }
    }
}

sealed class PNViewTransform : PNNativeValue {
    data class Option0(val value: PNTransformRotate) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: PNTransformScale) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: PNTransformScaleX) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option3(val value: PNTransformScaleY) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option4(val value: PNTransformTranslate) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option5(val value: Map<String, PNJSONValue>) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option6(val value: List<PNPNViewTransform6Item>) : PNViewTransform() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewTransform {
            try { return Option0(PNTransformRotate.decode(value)) } catch (_: Exception) { }
            try { return Option1(PNTransformScale.decode(value)) } catch (_: Exception) { }
            try { return Option2(PNTransformScaleX.decode(value)) } catch (_: Exception) { }
            try { return Option3(PNTransformScaleY.decode(value)) } catch (_: Exception) { }
            try { return Option4(PNTransformTranslate.decode(value)) } catch (_: Exception) { }
            try { return Option5(PNValues.objectValue(value).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNJSONValue(objectValue.get(key) ?: JSONObject.NULL) } }) } catch (_: Exception) { }
            try { return Option6(PNValues.array(value).map { item -> PNPNViewTransform6Item.decode(item) }) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewTransform")
        }
    }
}

enum class PNViewPointerEvents(val rawValue: String) : PNNativeValue {
    `auto`("auto"),
    `none`("none"),
    `box_none`("box_none"),
    `box_only`("box_only");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewPointerEvents = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewPointerEvents")
    }
}

sealed class PNViewHitSlop : PNNativeValue {
    data class Option0(val value: Double) : PNViewHitSlop() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Map<String, Double>) : PNViewHitSlop() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: PNJSONValue) : PNViewHitSlop() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNViewHitSlop {
            try { return Option0(PNValues.number(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.objectValue(value).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNValues.number(objectValue.get(key)) } }) } catch (_: Exception) { }
            try { return Option2(PNJSONValue(value ?: JSONObject.NULL)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNViewHitSlop")
        }
    }
}

enum class PNPNPNAccessibilityStateChecked1(val rawValue: String) : PNNativeValue {
    `mixed`("mixed");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNPNPNAccessibilityStateChecked1 = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNPNPNAccessibilityStateChecked1")
    }
}

sealed class PNPNAccessibilityStateChecked : PNNativeValue {
    data class Option0(val value: Boolean) : PNPNAccessibilityStateChecked() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: PNPNPNAccessibilityStateChecked1) : PNPNAccessibilityStateChecked() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNPNAccessibilityStateChecked {
            try { return Option0(PNValues.boolean(value)) } catch (_: Exception) { }
            try { return Option1(PNPNPNAccessibilityStateChecked1.decode(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNPNAccessibilityStateChecked")
        }
    }
}

data class PNAccessibilityState(
    val `disabled`: Boolean?,
    val `selected`: Boolean?,
    val `checked`: PNPNAccessibilityStateChecked?,
    val `busy`: Boolean?,
    val `expanded`: Boolean?
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        if (`disabled` != null) result.put("disabled", PNValues.encode(`disabled`))
        if (`selected` != null) result.put("selected", PNValues.encode(`selected`))
        if (`checked` != null) result.put("checked", PNValues.encode(`checked`))
        if (`busy` != null) result.put("busy", PNValues.encode(`busy`))
        if (`expanded` != null) result.put("expanded", PNValues.encode(`expanded`))
    }
    companion object {
        fun decode(value: Any?): PNAccessibilityState {
            val objectValue = PNValues.objectValue(value)
            return PNAccessibilityState(if (PNValues.isNull(objectValue.opt("disabled"))) null else PNValues.boolean((objectValue.opt("disabled"))), if (PNValues.isNull(objectValue.opt("selected"))) null else PNValues.boolean((objectValue.opt("selected"))), if (PNValues.isNull(objectValue.opt("checked"))) null else PNPNAccessibilityStateChecked.decode((objectValue.opt("checked"))), if (PNValues.isNull(objectValue.opt("busy"))) null else PNValues.boolean((objectValue.opt("busy"))), if (PNValues.isNull(objectValue.opt("expanded"))) null else PNValues.boolean((objectValue.opt("expanded"))))
        }
    }
}

enum class PNViewAccessibilityLiveRegion(val rawValue: String) : PNNativeValue {
    `none`("none"),
    `polite`("polite"),
    `assertive`("assertive");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewAccessibilityLiveRegion = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewAccessibilityLiveRegion")
    }
}

enum class PNViewPnHeaderSlot(val rawValue: String) : PNNativeValue {
    `left`("left"),
    `right`("right");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNViewPnHeaderSlot = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNViewPnHeaderSlot")
    }
}

enum class PNActivityIndicatorSize(val rawValue: String) : PNNativeValue {
    `small`("small"),
    `large`("large");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNActivityIndicatorSize = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNActivityIndicatorSize")
    }
}

enum class PNDatePickerMode(val rawValue: String) : PNNativeValue {
    `date`("date"),
    `time`("time"),
    `datetime`("datetime");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNDatePickerMode = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNDatePickerMode")
    }
}

enum class PNImageScaleType(val rawValue: String) : PNNativeValue {
    `cover`("cover"),
    `contain`("contain"),
    `stretch`("stretch"),
    `center`("center");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNImageScaleType = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNImageScaleType")
    }
}

data class PNImageLoadEvent(
    val `width`: Double,
    val `height`: Double
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("width", PNValues.encode(`width`))
        result.put("height", PNValues.encode(`height`))
    }
    companion object {
        fun decode(value: Any?): PNImageLoadEvent {
            val objectValue = PNValues.objectValue(value)
            return PNImageLoadEvent(PNValues.number((objectValue.get("width"))), PNValues.number((objectValue.get("height"))))
        }
    }
}

enum class PNKeyboardAvoidingViewBehavior(val rawValue: String) : PNNativeValue {
    `padding`("padding"),
    `position`("position"),
    `height`("height");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNKeyboardAvoidingViewBehavior = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNKeyboardAvoidingViewBehavior")
    }
}

enum class PNModalAnimationType(val rawValue: String) : PNNativeValue {
    `slide`("slide"),
    `fade`("fade"),
    `none`("none");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNModalAnimationType = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNModalAnimationType")
    }
}

enum class PNModalPresentationStyle(val rawValue: String) : PNNativeValue {
    `page_sheet`("page_sheet"),
    `form_sheet`("form_sheet"),
    `full_screen`("full_screen"),
    `overlay`("overlay");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNModalPresentationStyle = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNModalPresentationStyle")
    }
}

enum class PNSafeAreaViewEdgesItem(val rawValue: String) : PNNativeValue {
    `top`("top"),
    `left`("left"),
    `bottom`("bottom"),
    `right`("right");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNSafeAreaViewEdgesItem = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNSafeAreaViewEdgesItem")
    }
}

enum class PNScreenPresentation(val rawValue: String) : PNNativeValue {
    `card`("card"),
    `modal`("modal");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNScreenPresentation = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNScreenPresentation")
    }
}

enum class PNScreenAnimation(val rawValue: String) : PNNativeValue {
    `default`("default"),
    `none`("none"),
    `fade`("fade"),
    `slide_from_right`("slide_from_right"),
    `slide_from_bottom`("slide_from_bottom");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNScreenAnimation = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNScreenAnimation")
    }
}

sealed class PNScreenTabBarIcon : PNNativeValue {
    data class Option0(val value: String) : PNScreenTabBarIcon() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Map<String, String>) : PNScreenTabBarIcon() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNScreenTabBarIcon {
            try { return Option0(PNValues.string(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.objectValue(value).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNValues.string(objectValue.get(key)) } }) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNScreenTabBarIcon")
        }
    }
}

sealed class PNScreenTabBarBadge : PNNativeValue {
    data class Option0(val value: String) : PNScreenTabBarBadge() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Long) : PNScreenTabBarBadge() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNScreenTabBarBadge {
            try { return Option0(PNValues.string(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.integer(value)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNScreenTabBarBadge")
        }
    }
}

data class PNScrollViewRefreshControl(
    val `width`: PNViewWidth?,
    val `height`: PNViewWidth?,
    val `min_width`: PNViewWidth?,
    val `max_width`: PNViewWidth?,
    val `min_height`: PNViewWidth?,
    val `max_height`: PNViewWidth?,
    val `aspect_ratio`: Double?,
    val `flex`: Double?,
    val `flex_grow`: Double?,
    val `flex_shrink`: Double?,
    val `flex_basis`: PNViewWidth?,
    val `flex_direction`: PNViewFlexDirection?,
    val `flex_wrap`: PNViewFlexWrap?,
    val `justify_content`: PNViewJustifyContent?,
    val `align_items`: PNViewAlignItems?,
    val `align_self`: PNViewAlignItems?,
    val `align_content`: PNViewAlignContent?,
    val `direction`: PNViewDirection?,
    val `display`: PNViewDisplay?,
    val `position`: PNViewPosition?,
    val `top`: PNViewWidth?,
    val `right`: PNViewWidth?,
    val `bottom`: PNViewWidth?,
    val `left`: PNViewWidth?,
    val `start`: PNViewWidth?,
    val `end`: PNViewWidth?,
    val `padding`: PNViewPadding?,
    val `padding_top`: PNViewWidth?,
    val `padding_bottom`: PNViewWidth?,
    val `padding_left`: PNViewWidth?,
    val `padding_right`: PNViewWidth?,
    val `padding_start`: PNViewWidth?,
    val `padding_end`: PNViewWidth?,
    val `padding_horizontal`: PNViewWidth?,
    val `padding_vertical`: PNViewWidth?,
    val `margin`: PNViewMargin?,
    val `margin_top`: PNViewMarginTop?,
    val `margin_bottom`: PNViewMarginTop?,
    val `margin_left`: PNViewMarginTop?,
    val `margin_right`: PNViewMarginTop?,
    val `margin_start`: PNViewMarginTop?,
    val `margin_end`: PNViewMarginTop?,
    val `margin_horizontal`: PNViewMarginTop?,
    val `margin_vertical`: PNViewMarginTop?,
    val `spacing`: Double?,
    val `gap`: Double?,
    val `row_gap`: Double?,
    val `column_gap`: Double?,
    val `overflow`: PNViewOverflow?,
    val `background_color`: String?,
    val `color`: String?,
    val `border_color`: String?,
    val `placeholder_color`: String?,
    val `tint_color`: PNPresence<String?>,
    val `border_width`: Double?,
    val `border_radius`: Double?,
    val `border_top_left_radius`: Double?,
    val `border_top_right_radius`: Double?,
    val `border_bottom_left_radius`: Double?,
    val `border_bottom_right_radius`: Double?,
    val `border_top_width`: Double?,
    val `border_right_width`: Double?,
    val `border_bottom_width`: Double?,
    val `border_left_width`: Double?,
    val `border_top_color`: String?,
    val `border_right_color`: String?,
    val `border_bottom_color`: String?,
    val `border_left_color`: String?,
    val `font_size`: Double?,
    val `font_family`: String?,
    val `font_weight`: PNViewFontWeight?,
    val `bold`: Boolean?,
    val `italic`: Boolean?,
    val `text_align`: PNViewTextAlign?,
    val `text_decoration`: PNViewTextDecoration?,
    val `text_transform`: PNViewTextTransform?,
    val `line_height`: Double?,
    val `letter_spacing`: Double?,
    val `max_lines`: Long?,
    val `text_shadow_color`: String?,
    val `text_shadow_offset`: PNViewTextShadowOffset?,
    val `text_shadow_radius`: Double?,
    val `shadow_color`: String?,
    val `shadow_offset`: PNViewTextShadowOffset?,
    val `shadow_opacity`: Double?,
    val `shadow_radius`: Double?,
    val `elevation`: Double?,
    val `opacity`: Double?,
    val `transform`: PNViewTransform?,
    val `z_index`: Long?,
    val `pointer_events`: PNViewPointerEvents?,
    val `refreshing`: Boolean?,
    val `on_refresh`: PNPresence<Boolean?>,
    val `accessibility_role`: String?,
    val `ref`: PNJSONValue?,
    val `on_layout`: Boolean?
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        if (`width` != null) result.put("width", PNValues.encode(`width`))
        if (`height` != null) result.put("height", PNValues.encode(`height`))
        if (`min_width` != null) result.put("min_width", PNValues.encode(`min_width`))
        if (`max_width` != null) result.put("max_width", PNValues.encode(`max_width`))
        if (`min_height` != null) result.put("min_height", PNValues.encode(`min_height`))
        if (`max_height` != null) result.put("max_height", PNValues.encode(`max_height`))
        if (`aspect_ratio` != null) result.put("aspect_ratio", PNValues.encode(`aspect_ratio`))
        if (`flex` != null) result.put("flex", PNValues.encode(`flex`))
        if (`flex_grow` != null) result.put("flex_grow", PNValues.encode(`flex_grow`))
        if (`flex_shrink` != null) result.put("flex_shrink", PNValues.encode(`flex_shrink`))
        if (`flex_basis` != null) result.put("flex_basis", PNValues.encode(`flex_basis`))
        if (`flex_direction` != null) result.put("flex_direction", PNValues.encode(`flex_direction`))
        if (`flex_wrap` != null) result.put("flex_wrap", PNValues.encode(`flex_wrap`))
        if (`justify_content` != null) result.put("justify_content", PNValues.encode(`justify_content`))
        if (`align_items` != null) result.put("align_items", PNValues.encode(`align_items`))
        if (`align_self` != null) result.put("align_self", PNValues.encode(`align_self`))
        if (`align_content` != null) result.put("align_content", PNValues.encode(`align_content`))
        if (`direction` != null) result.put("direction", PNValues.encode(`direction`))
        if (`display` != null) result.put("display", PNValues.encode(`display`))
        if (`position` != null) result.put("position", PNValues.encode(`position`))
        if (`top` != null) result.put("top", PNValues.encode(`top`))
        if (`right` != null) result.put("right", PNValues.encode(`right`))
        if (`bottom` != null) result.put("bottom", PNValues.encode(`bottom`))
        if (`left` != null) result.put("left", PNValues.encode(`left`))
        if (`start` != null) result.put("start", PNValues.encode(`start`))
        if (`end` != null) result.put("end", PNValues.encode(`end`))
        if (`padding` != null) result.put("padding", PNValues.encode(`padding`))
        if (`padding_top` != null) result.put("padding_top", PNValues.encode(`padding_top`))
        if (`padding_bottom` != null) result.put("padding_bottom", PNValues.encode(`padding_bottom`))
        if (`padding_left` != null) result.put("padding_left", PNValues.encode(`padding_left`))
        if (`padding_right` != null) result.put("padding_right", PNValues.encode(`padding_right`))
        if (`padding_start` != null) result.put("padding_start", PNValues.encode(`padding_start`))
        if (`padding_end` != null) result.put("padding_end", PNValues.encode(`padding_end`))
        if (`padding_horizontal` != null) result.put("padding_horizontal", PNValues.encode(`padding_horizontal`))
        if (`padding_vertical` != null) result.put("padding_vertical", PNValues.encode(`padding_vertical`))
        if (`margin` != null) result.put("margin", PNValues.encode(`margin`))
        if (`margin_top` != null) result.put("margin_top", PNValues.encode(`margin_top`))
        if (`margin_bottom` != null) result.put("margin_bottom", PNValues.encode(`margin_bottom`))
        if (`margin_left` != null) result.put("margin_left", PNValues.encode(`margin_left`))
        if (`margin_right` != null) result.put("margin_right", PNValues.encode(`margin_right`))
        if (`margin_start` != null) result.put("margin_start", PNValues.encode(`margin_start`))
        if (`margin_end` != null) result.put("margin_end", PNValues.encode(`margin_end`))
        if (`margin_horizontal` != null) result.put("margin_horizontal", PNValues.encode(`margin_horizontal`))
        if (`margin_vertical` != null) result.put("margin_vertical", PNValues.encode(`margin_vertical`))
        if (`spacing` != null) result.put("spacing", PNValues.encode(`spacing`))
        if (`gap` != null) result.put("gap", PNValues.encode(`gap`))
        if (`row_gap` != null) result.put("row_gap", PNValues.encode(`row_gap`))
        if (`column_gap` != null) result.put("column_gap", PNValues.encode(`column_gap`))
        if (`overflow` != null) result.put("overflow", PNValues.encode(`overflow`))
        if (`background_color` != null) result.put("background_color", PNValues.encode(`background_color`))
        if (`color` != null) result.put("color", PNValues.encode(`color`))
        if (`border_color` != null) result.put("border_color", PNValues.encode(`border_color`))
        if (`placeholder_color` != null) result.put("placeholder_color", PNValues.encode(`placeholder_color`))
        if (`tint_color` is PNPresence.Present) result.put("tint_color", PNValues.encode(`tint_color`.value))
        if (`border_width` != null) result.put("border_width", PNValues.encode(`border_width`))
        if (`border_radius` != null) result.put("border_radius", PNValues.encode(`border_radius`))
        if (`border_top_left_radius` != null) result.put("border_top_left_radius", PNValues.encode(`border_top_left_radius`))
        if (`border_top_right_radius` != null) result.put("border_top_right_radius", PNValues.encode(`border_top_right_radius`))
        if (`border_bottom_left_radius` != null) result.put("border_bottom_left_radius", PNValues.encode(`border_bottom_left_radius`))
        if (`border_bottom_right_radius` != null) result.put("border_bottom_right_radius", PNValues.encode(`border_bottom_right_radius`))
        if (`border_top_width` != null) result.put("border_top_width", PNValues.encode(`border_top_width`))
        if (`border_right_width` != null) result.put("border_right_width", PNValues.encode(`border_right_width`))
        if (`border_bottom_width` != null) result.put("border_bottom_width", PNValues.encode(`border_bottom_width`))
        if (`border_left_width` != null) result.put("border_left_width", PNValues.encode(`border_left_width`))
        if (`border_top_color` != null) result.put("border_top_color", PNValues.encode(`border_top_color`))
        if (`border_right_color` != null) result.put("border_right_color", PNValues.encode(`border_right_color`))
        if (`border_bottom_color` != null) result.put("border_bottom_color", PNValues.encode(`border_bottom_color`))
        if (`border_left_color` != null) result.put("border_left_color", PNValues.encode(`border_left_color`))
        if (`font_size` != null) result.put("font_size", PNValues.encode(`font_size`))
        if (`font_family` != null) result.put("font_family", PNValues.encode(`font_family`))
        if (`font_weight` != null) result.put("font_weight", PNValues.encode(`font_weight`))
        if (`bold` != null) result.put("bold", PNValues.encode(`bold`))
        if (`italic` != null) result.put("italic", PNValues.encode(`italic`))
        if (`text_align` != null) result.put("text_align", PNValues.encode(`text_align`))
        if (`text_decoration` != null) result.put("text_decoration", PNValues.encode(`text_decoration`))
        if (`text_transform` != null) result.put("text_transform", PNValues.encode(`text_transform`))
        if (`line_height` != null) result.put("line_height", PNValues.encode(`line_height`))
        if (`letter_spacing` != null) result.put("letter_spacing", PNValues.encode(`letter_spacing`))
        if (`max_lines` != null) result.put("max_lines", PNValues.encode(`max_lines`))
        if (`text_shadow_color` != null) result.put("text_shadow_color", PNValues.encode(`text_shadow_color`))
        if (`text_shadow_offset` != null) result.put("text_shadow_offset", PNValues.encode(`text_shadow_offset`))
        if (`text_shadow_radius` != null) result.put("text_shadow_radius", PNValues.encode(`text_shadow_radius`))
        if (`shadow_color` != null) result.put("shadow_color", PNValues.encode(`shadow_color`))
        if (`shadow_offset` != null) result.put("shadow_offset", PNValues.encode(`shadow_offset`))
        if (`shadow_opacity` != null) result.put("shadow_opacity", PNValues.encode(`shadow_opacity`))
        if (`shadow_radius` != null) result.put("shadow_radius", PNValues.encode(`shadow_radius`))
        if (`elevation` != null) result.put("elevation", PNValues.encode(`elevation`))
        if (`opacity` != null) result.put("opacity", PNValues.encode(`opacity`))
        if (`transform` != null) result.put("transform", PNValues.encode(`transform`))
        if (`z_index` != null) result.put("z_index", PNValues.encode(`z_index`))
        if (`pointer_events` != null) result.put("pointer_events", PNValues.encode(`pointer_events`))
        if (`refreshing` != null) result.put("refreshing", PNValues.encode(`refreshing`))
        if (`on_refresh` is PNPresence.Present) result.put("on_refresh", PNValues.encode(`on_refresh`.value))
        if (`accessibility_role` != null) result.put("accessibility_role", PNValues.encode(`accessibility_role`))
        if (`ref` != null) result.put("ref", PNValues.encode(`ref`))
        if (`on_layout` != null) result.put("on_layout", PNValues.encode(`on_layout`))
    }
    companion object {
        fun decode(value: Any?): PNScrollViewRefreshControl {
            val objectValue = PNValues.objectValue(value)
            return PNScrollViewRefreshControl(if (PNValues.isNull(objectValue.opt("width"))) null else PNViewWidth.decode((objectValue.opt("width"))), if (PNValues.isNull(objectValue.opt("height"))) null else PNViewWidth.decode((objectValue.opt("height"))), if (PNValues.isNull(objectValue.opt("min_width"))) null else PNViewWidth.decode((objectValue.opt("min_width"))), if (PNValues.isNull(objectValue.opt("max_width"))) null else PNViewWidth.decode((objectValue.opt("max_width"))), if (PNValues.isNull(objectValue.opt("min_height"))) null else PNViewWidth.decode((objectValue.opt("min_height"))), if (PNValues.isNull(objectValue.opt("max_height"))) null else PNViewWidth.decode((objectValue.opt("max_height"))), if (PNValues.isNull(objectValue.opt("aspect_ratio"))) null else PNValues.number((objectValue.opt("aspect_ratio"))), if (PNValues.isNull(objectValue.opt("flex"))) null else PNValues.number((objectValue.opt("flex"))), if (PNValues.isNull(objectValue.opt("flex_grow"))) null else PNValues.number((objectValue.opt("flex_grow"))), if (PNValues.isNull(objectValue.opt("flex_shrink"))) null else PNValues.number((objectValue.opt("flex_shrink"))), if (PNValues.isNull(objectValue.opt("flex_basis"))) null else PNViewWidth.decode((objectValue.opt("flex_basis"))), if (PNValues.isNull(objectValue.opt("flex_direction"))) null else PNViewFlexDirection.decode((objectValue.opt("flex_direction"))), if (PNValues.isNull(objectValue.opt("flex_wrap"))) null else PNViewFlexWrap.decode((objectValue.opt("flex_wrap"))), if (PNValues.isNull(objectValue.opt("justify_content"))) null else PNViewJustifyContent.decode((objectValue.opt("justify_content"))), if (PNValues.isNull(objectValue.opt("align_items"))) null else PNViewAlignItems.decode((objectValue.opt("align_items"))), if (PNValues.isNull(objectValue.opt("align_self"))) null else PNViewAlignItems.decode((objectValue.opt("align_self"))), if (PNValues.isNull(objectValue.opt("align_content"))) null else PNViewAlignContent.decode((objectValue.opt("align_content"))), if (PNValues.isNull(objectValue.opt("direction"))) null else PNViewDirection.decode((objectValue.opt("direction"))), if (PNValues.isNull(objectValue.opt("display"))) null else PNViewDisplay.decode((objectValue.opt("display"))), if (PNValues.isNull(objectValue.opt("position"))) null else PNViewPosition.decode((objectValue.opt("position"))), if (PNValues.isNull(objectValue.opt("top"))) null else PNViewWidth.decode((objectValue.opt("top"))), if (PNValues.isNull(objectValue.opt("right"))) null else PNViewWidth.decode((objectValue.opt("right"))), if (PNValues.isNull(objectValue.opt("bottom"))) null else PNViewWidth.decode((objectValue.opt("bottom"))), if (PNValues.isNull(objectValue.opt("left"))) null else PNViewWidth.decode((objectValue.opt("left"))), if (PNValues.isNull(objectValue.opt("start"))) null else PNViewWidth.decode((objectValue.opt("start"))), if (PNValues.isNull(objectValue.opt("end"))) null else PNViewWidth.decode((objectValue.opt("end"))), if (PNValues.isNull(objectValue.opt("padding"))) null else PNViewPadding.decode((objectValue.opt("padding"))), if (PNValues.isNull(objectValue.opt("padding_top"))) null else PNViewWidth.decode((objectValue.opt("padding_top"))), if (PNValues.isNull(objectValue.opt("padding_bottom"))) null else PNViewWidth.decode((objectValue.opt("padding_bottom"))), if (PNValues.isNull(objectValue.opt("padding_left"))) null else PNViewWidth.decode((objectValue.opt("padding_left"))), if (PNValues.isNull(objectValue.opt("padding_right"))) null else PNViewWidth.decode((objectValue.opt("padding_right"))), if (PNValues.isNull(objectValue.opt("padding_start"))) null else PNViewWidth.decode((objectValue.opt("padding_start"))), if (PNValues.isNull(objectValue.opt("padding_end"))) null else PNViewWidth.decode((objectValue.opt("padding_end"))), if (PNValues.isNull(objectValue.opt("padding_horizontal"))) null else PNViewWidth.decode((objectValue.opt("padding_horizontal"))), if (PNValues.isNull(objectValue.opt("padding_vertical"))) null else PNViewWidth.decode((objectValue.opt("padding_vertical"))), if (PNValues.isNull(objectValue.opt("margin"))) null else PNViewMargin.decode((objectValue.opt("margin"))), if (PNValues.isNull(objectValue.opt("margin_top"))) null else PNViewMarginTop.decode((objectValue.opt("margin_top"))), if (PNValues.isNull(objectValue.opt("margin_bottom"))) null else PNViewMarginTop.decode((objectValue.opt("margin_bottom"))), if (PNValues.isNull(objectValue.opt("margin_left"))) null else PNViewMarginTop.decode((objectValue.opt("margin_left"))), if (PNValues.isNull(objectValue.opt("margin_right"))) null else PNViewMarginTop.decode((objectValue.opt("margin_right"))), if (PNValues.isNull(objectValue.opt("margin_start"))) null else PNViewMarginTop.decode((objectValue.opt("margin_start"))), if (PNValues.isNull(objectValue.opt("margin_end"))) null else PNViewMarginTop.decode((objectValue.opt("margin_end"))), if (PNValues.isNull(objectValue.opt("margin_horizontal"))) null else PNViewMarginTop.decode((objectValue.opt("margin_horizontal"))), if (PNValues.isNull(objectValue.opt("margin_vertical"))) null else PNViewMarginTop.decode((objectValue.opt("margin_vertical"))), if (PNValues.isNull(objectValue.opt("spacing"))) null else PNValues.number((objectValue.opt("spacing"))), if (PNValues.isNull(objectValue.opt("gap"))) null else PNValues.number((objectValue.opt("gap"))), if (PNValues.isNull(objectValue.opt("row_gap"))) null else PNValues.number((objectValue.opt("row_gap"))), if (PNValues.isNull(objectValue.opt("column_gap"))) null else PNValues.number((objectValue.opt("column_gap"))), if (PNValues.isNull(objectValue.opt("overflow"))) null else PNViewOverflow.decode((objectValue.opt("overflow"))), if (PNValues.isNull(objectValue.opt("background_color"))) null else PNValues.string((objectValue.opt("background_color"))), if (PNValues.isNull(objectValue.opt("color"))) null else PNValues.string((objectValue.opt("color"))), if (PNValues.isNull(objectValue.opt("border_color"))) null else PNValues.string((objectValue.opt("border_color"))), if (PNValues.isNull(objectValue.opt("placeholder_color"))) null else PNValues.string((objectValue.opt("placeholder_color"))), if (objectValue.has("tint_color")) PNPresence.Present(if (PNValues.isNull((objectValue.opt("tint_color")))) null else PNValues.string((objectValue.opt("tint_color")))) else PNPresence.Absent, if (PNValues.isNull(objectValue.opt("border_width"))) null else PNValues.number((objectValue.opt("border_width"))), if (PNValues.isNull(objectValue.opt("border_radius"))) null else PNValues.number((objectValue.opt("border_radius"))), if (PNValues.isNull(objectValue.opt("border_top_left_radius"))) null else PNValues.number((objectValue.opt("border_top_left_radius"))), if (PNValues.isNull(objectValue.opt("border_top_right_radius"))) null else PNValues.number((objectValue.opt("border_top_right_radius"))), if (PNValues.isNull(objectValue.opt("border_bottom_left_radius"))) null else PNValues.number((objectValue.opt("border_bottom_left_radius"))), if (PNValues.isNull(objectValue.opt("border_bottom_right_radius"))) null else PNValues.number((objectValue.opt("border_bottom_right_radius"))), if (PNValues.isNull(objectValue.opt("border_top_width"))) null else PNValues.number((objectValue.opt("border_top_width"))), if (PNValues.isNull(objectValue.opt("border_right_width"))) null else PNValues.number((objectValue.opt("border_right_width"))), if (PNValues.isNull(objectValue.opt("border_bottom_width"))) null else PNValues.number((objectValue.opt("border_bottom_width"))), if (PNValues.isNull(objectValue.opt("border_left_width"))) null else PNValues.number((objectValue.opt("border_left_width"))), if (PNValues.isNull(objectValue.opt("border_top_color"))) null else PNValues.string((objectValue.opt("border_top_color"))), if (PNValues.isNull(objectValue.opt("border_right_color"))) null else PNValues.string((objectValue.opt("border_right_color"))), if (PNValues.isNull(objectValue.opt("border_bottom_color"))) null else PNValues.string((objectValue.opt("border_bottom_color"))), if (PNValues.isNull(objectValue.opt("border_left_color"))) null else PNValues.string((objectValue.opt("border_left_color"))), if (PNValues.isNull(objectValue.opt("font_size"))) null else PNValues.number((objectValue.opt("font_size"))), if (PNValues.isNull(objectValue.opt("font_family"))) null else PNValues.string((objectValue.opt("font_family"))), if (PNValues.isNull(objectValue.opt("font_weight"))) null else PNViewFontWeight.decode((objectValue.opt("font_weight"))), if (PNValues.isNull(objectValue.opt("bold"))) null else PNValues.boolean((objectValue.opt("bold"))), if (PNValues.isNull(objectValue.opt("italic"))) null else PNValues.boolean((objectValue.opt("italic"))), if (PNValues.isNull(objectValue.opt("text_align"))) null else PNViewTextAlign.decode((objectValue.opt("text_align"))), if (PNValues.isNull(objectValue.opt("text_decoration"))) null else PNViewTextDecoration.decode((objectValue.opt("text_decoration"))), if (PNValues.isNull(objectValue.opt("text_transform"))) null else PNViewTextTransform.decode((objectValue.opt("text_transform"))), if (PNValues.isNull(objectValue.opt("line_height"))) null else PNValues.number((objectValue.opt("line_height"))), if (PNValues.isNull(objectValue.opt("letter_spacing"))) null else PNValues.number((objectValue.opt("letter_spacing"))), if (PNValues.isNull(objectValue.opt("max_lines"))) null else PNValues.integer((objectValue.opt("max_lines"))), if (PNValues.isNull(objectValue.opt("text_shadow_color"))) null else PNValues.string((objectValue.opt("text_shadow_color"))), if (PNValues.isNull(objectValue.opt("text_shadow_offset"))) null else PNViewTextShadowOffset.decode((objectValue.opt("text_shadow_offset"))), if (PNValues.isNull(objectValue.opt("text_shadow_radius"))) null else PNValues.number((objectValue.opt("text_shadow_radius"))), if (PNValues.isNull(objectValue.opt("shadow_color"))) null else PNValues.string((objectValue.opt("shadow_color"))), if (PNValues.isNull(objectValue.opt("shadow_offset"))) null else PNViewTextShadowOffset.decode((objectValue.opt("shadow_offset"))), if (PNValues.isNull(objectValue.opt("shadow_opacity"))) null else PNValues.number((objectValue.opt("shadow_opacity"))), if (PNValues.isNull(objectValue.opt("shadow_radius"))) null else PNValues.number((objectValue.opt("shadow_radius"))), if (PNValues.isNull(objectValue.opt("elevation"))) null else PNValues.number((objectValue.opt("elevation"))), if (PNValues.isNull(objectValue.opt("opacity"))) null else PNValues.number((objectValue.opt("opacity"))), if (PNValues.isNull(objectValue.opt("transform"))) null else PNViewTransform.decode((objectValue.opt("transform"))), if (PNValues.isNull(objectValue.opt("z_index"))) null else PNValues.integer((objectValue.opt("z_index"))), if (PNValues.isNull(objectValue.opt("pointer_events"))) null else PNViewPointerEvents.decode((objectValue.opt("pointer_events"))), if (PNValues.isNull(objectValue.opt("refreshing"))) null else PNValues.boolean((objectValue.opt("refreshing"))), if (objectValue.has("on_refresh")) PNPresence.Present(if (PNValues.isNull((objectValue.opt("on_refresh")))) null else PNValues.boolean((objectValue.opt("on_refresh")))) else PNPresence.Absent, if (PNValues.isNull(objectValue.opt("accessibility_role"))) null else PNValues.string((objectValue.opt("accessibility_role"))), if (PNValues.isNull(objectValue.opt("ref"))) null else PNJSONValue((objectValue.opt("ref")) ?: JSONObject.NULL), if (PNValues.isNull(objectValue.opt("on_layout"))) null else PNValues.boolean((objectValue.opt("on_layout"))))
        }
    }
}

enum class PNScrollViewScrollAxis(val rawValue: String) : PNNativeValue {
    `vertical`("vertical"),
    `horizontal`("horizontal");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNScrollViewScrollAxis = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNScrollViewScrollAxis")
    }
}

data class PNStyle(
    val `width`: PNViewWidth?,
    val `height`: PNViewWidth?,
    val `min_width`: PNViewWidth?,
    val `max_width`: PNViewWidth?,
    val `min_height`: PNViewWidth?,
    val `max_height`: PNViewWidth?,
    val `aspect_ratio`: Double?,
    val `flex`: Double?,
    val `flex_grow`: Double?,
    val `flex_shrink`: Double?,
    val `flex_basis`: PNViewWidth?,
    val `flex_direction`: PNViewFlexDirection?,
    val `flex_wrap`: PNViewFlexWrap?,
    val `justify_content`: PNViewJustifyContent?,
    val `align_items`: PNViewAlignItems?,
    val `align_self`: PNViewAlignItems?,
    val `align_content`: PNViewAlignContent?,
    val `direction`: PNViewDirection?,
    val `display`: PNViewDisplay?,
    val `position`: PNViewPosition?,
    val `top`: PNViewWidth?,
    val `right`: PNViewWidth?,
    val `bottom`: PNViewWidth?,
    val `left`: PNViewWidth?,
    val `start`: PNViewWidth?,
    val `end`: PNViewWidth?,
    val `padding`: PNViewPadding?,
    val `padding_top`: PNViewWidth?,
    val `padding_bottom`: PNViewWidth?,
    val `padding_left`: PNViewWidth?,
    val `padding_right`: PNViewWidth?,
    val `padding_start`: PNViewWidth?,
    val `padding_end`: PNViewWidth?,
    val `padding_horizontal`: PNViewWidth?,
    val `padding_vertical`: PNViewWidth?,
    val `margin`: PNViewMargin?,
    val `margin_top`: PNViewMarginTop?,
    val `margin_bottom`: PNViewMarginTop?,
    val `margin_left`: PNViewMarginTop?,
    val `margin_right`: PNViewMarginTop?,
    val `margin_start`: PNViewMarginTop?,
    val `margin_end`: PNViewMarginTop?,
    val `margin_horizontal`: PNViewMarginTop?,
    val `margin_vertical`: PNViewMarginTop?,
    val `spacing`: Double?,
    val `gap`: Double?,
    val `row_gap`: Double?,
    val `column_gap`: Double?,
    val `overflow`: PNViewOverflow?,
    val `background_color`: String?,
    val `color`: String?,
    val `border_color`: String?,
    val `placeholder_color`: String?,
    val `tint_color`: String?,
    val `border_width`: Double?,
    val `border_radius`: Double?,
    val `border_top_left_radius`: Double?,
    val `border_top_right_radius`: Double?,
    val `border_bottom_left_radius`: Double?,
    val `border_bottom_right_radius`: Double?,
    val `border_top_width`: Double?,
    val `border_right_width`: Double?,
    val `border_bottom_width`: Double?,
    val `border_left_width`: Double?,
    val `border_top_color`: String?,
    val `border_right_color`: String?,
    val `border_bottom_color`: String?,
    val `border_left_color`: String?,
    val `font_size`: Double?,
    val `font_family`: String?,
    val `font_weight`: PNViewFontWeight?,
    val `bold`: Boolean?,
    val `italic`: Boolean?,
    val `text_align`: PNViewTextAlign?,
    val `text_decoration`: PNViewTextDecoration?,
    val `text_transform`: PNViewTextTransform?,
    val `line_height`: Double?,
    val `letter_spacing`: Double?,
    val `max_lines`: Long?,
    val `text_shadow_color`: String?,
    val `text_shadow_offset`: PNViewTextShadowOffset?,
    val `text_shadow_radius`: Double?,
    val `shadow_color`: String?,
    val `shadow_offset`: PNViewTextShadowOffset?,
    val `shadow_opacity`: Double?,
    val `shadow_radius`: Double?,
    val `elevation`: Double?,
    val `opacity`: Double?,
    val `transform`: PNViewTransform?,
    val `z_index`: Long?,
    val `pointer_events`: PNViewPointerEvents?
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        if (`width` != null) result.put("width", PNValues.encode(`width`))
        if (`height` != null) result.put("height", PNValues.encode(`height`))
        if (`min_width` != null) result.put("min_width", PNValues.encode(`min_width`))
        if (`max_width` != null) result.put("max_width", PNValues.encode(`max_width`))
        if (`min_height` != null) result.put("min_height", PNValues.encode(`min_height`))
        if (`max_height` != null) result.put("max_height", PNValues.encode(`max_height`))
        if (`aspect_ratio` != null) result.put("aspect_ratio", PNValues.encode(`aspect_ratio`))
        if (`flex` != null) result.put("flex", PNValues.encode(`flex`))
        if (`flex_grow` != null) result.put("flex_grow", PNValues.encode(`flex_grow`))
        if (`flex_shrink` != null) result.put("flex_shrink", PNValues.encode(`flex_shrink`))
        if (`flex_basis` != null) result.put("flex_basis", PNValues.encode(`flex_basis`))
        if (`flex_direction` != null) result.put("flex_direction", PNValues.encode(`flex_direction`))
        if (`flex_wrap` != null) result.put("flex_wrap", PNValues.encode(`flex_wrap`))
        if (`justify_content` != null) result.put("justify_content", PNValues.encode(`justify_content`))
        if (`align_items` != null) result.put("align_items", PNValues.encode(`align_items`))
        if (`align_self` != null) result.put("align_self", PNValues.encode(`align_self`))
        if (`align_content` != null) result.put("align_content", PNValues.encode(`align_content`))
        if (`direction` != null) result.put("direction", PNValues.encode(`direction`))
        if (`display` != null) result.put("display", PNValues.encode(`display`))
        if (`position` != null) result.put("position", PNValues.encode(`position`))
        if (`top` != null) result.put("top", PNValues.encode(`top`))
        if (`right` != null) result.put("right", PNValues.encode(`right`))
        if (`bottom` != null) result.put("bottom", PNValues.encode(`bottom`))
        if (`left` != null) result.put("left", PNValues.encode(`left`))
        if (`start` != null) result.put("start", PNValues.encode(`start`))
        if (`end` != null) result.put("end", PNValues.encode(`end`))
        if (`padding` != null) result.put("padding", PNValues.encode(`padding`))
        if (`padding_top` != null) result.put("padding_top", PNValues.encode(`padding_top`))
        if (`padding_bottom` != null) result.put("padding_bottom", PNValues.encode(`padding_bottom`))
        if (`padding_left` != null) result.put("padding_left", PNValues.encode(`padding_left`))
        if (`padding_right` != null) result.put("padding_right", PNValues.encode(`padding_right`))
        if (`padding_start` != null) result.put("padding_start", PNValues.encode(`padding_start`))
        if (`padding_end` != null) result.put("padding_end", PNValues.encode(`padding_end`))
        if (`padding_horizontal` != null) result.put("padding_horizontal", PNValues.encode(`padding_horizontal`))
        if (`padding_vertical` != null) result.put("padding_vertical", PNValues.encode(`padding_vertical`))
        if (`margin` != null) result.put("margin", PNValues.encode(`margin`))
        if (`margin_top` != null) result.put("margin_top", PNValues.encode(`margin_top`))
        if (`margin_bottom` != null) result.put("margin_bottom", PNValues.encode(`margin_bottom`))
        if (`margin_left` != null) result.put("margin_left", PNValues.encode(`margin_left`))
        if (`margin_right` != null) result.put("margin_right", PNValues.encode(`margin_right`))
        if (`margin_start` != null) result.put("margin_start", PNValues.encode(`margin_start`))
        if (`margin_end` != null) result.put("margin_end", PNValues.encode(`margin_end`))
        if (`margin_horizontal` != null) result.put("margin_horizontal", PNValues.encode(`margin_horizontal`))
        if (`margin_vertical` != null) result.put("margin_vertical", PNValues.encode(`margin_vertical`))
        if (`spacing` != null) result.put("spacing", PNValues.encode(`spacing`))
        if (`gap` != null) result.put("gap", PNValues.encode(`gap`))
        if (`row_gap` != null) result.put("row_gap", PNValues.encode(`row_gap`))
        if (`column_gap` != null) result.put("column_gap", PNValues.encode(`column_gap`))
        if (`overflow` != null) result.put("overflow", PNValues.encode(`overflow`))
        if (`background_color` != null) result.put("background_color", PNValues.encode(`background_color`))
        if (`color` != null) result.put("color", PNValues.encode(`color`))
        if (`border_color` != null) result.put("border_color", PNValues.encode(`border_color`))
        if (`placeholder_color` != null) result.put("placeholder_color", PNValues.encode(`placeholder_color`))
        if (`tint_color` != null) result.put("tint_color", PNValues.encode(`tint_color`))
        if (`border_width` != null) result.put("border_width", PNValues.encode(`border_width`))
        if (`border_radius` != null) result.put("border_radius", PNValues.encode(`border_radius`))
        if (`border_top_left_radius` != null) result.put("border_top_left_radius", PNValues.encode(`border_top_left_radius`))
        if (`border_top_right_radius` != null) result.put("border_top_right_radius", PNValues.encode(`border_top_right_radius`))
        if (`border_bottom_left_radius` != null) result.put("border_bottom_left_radius", PNValues.encode(`border_bottom_left_radius`))
        if (`border_bottom_right_radius` != null) result.put("border_bottom_right_radius", PNValues.encode(`border_bottom_right_radius`))
        if (`border_top_width` != null) result.put("border_top_width", PNValues.encode(`border_top_width`))
        if (`border_right_width` != null) result.put("border_right_width", PNValues.encode(`border_right_width`))
        if (`border_bottom_width` != null) result.put("border_bottom_width", PNValues.encode(`border_bottom_width`))
        if (`border_left_width` != null) result.put("border_left_width", PNValues.encode(`border_left_width`))
        if (`border_top_color` != null) result.put("border_top_color", PNValues.encode(`border_top_color`))
        if (`border_right_color` != null) result.put("border_right_color", PNValues.encode(`border_right_color`))
        if (`border_bottom_color` != null) result.put("border_bottom_color", PNValues.encode(`border_bottom_color`))
        if (`border_left_color` != null) result.put("border_left_color", PNValues.encode(`border_left_color`))
        if (`font_size` != null) result.put("font_size", PNValues.encode(`font_size`))
        if (`font_family` != null) result.put("font_family", PNValues.encode(`font_family`))
        if (`font_weight` != null) result.put("font_weight", PNValues.encode(`font_weight`))
        if (`bold` != null) result.put("bold", PNValues.encode(`bold`))
        if (`italic` != null) result.put("italic", PNValues.encode(`italic`))
        if (`text_align` != null) result.put("text_align", PNValues.encode(`text_align`))
        if (`text_decoration` != null) result.put("text_decoration", PNValues.encode(`text_decoration`))
        if (`text_transform` != null) result.put("text_transform", PNValues.encode(`text_transform`))
        if (`line_height` != null) result.put("line_height", PNValues.encode(`line_height`))
        if (`letter_spacing` != null) result.put("letter_spacing", PNValues.encode(`letter_spacing`))
        if (`max_lines` != null) result.put("max_lines", PNValues.encode(`max_lines`))
        if (`text_shadow_color` != null) result.put("text_shadow_color", PNValues.encode(`text_shadow_color`))
        if (`text_shadow_offset` != null) result.put("text_shadow_offset", PNValues.encode(`text_shadow_offset`))
        if (`text_shadow_radius` != null) result.put("text_shadow_radius", PNValues.encode(`text_shadow_radius`))
        if (`shadow_color` != null) result.put("shadow_color", PNValues.encode(`shadow_color`))
        if (`shadow_offset` != null) result.put("shadow_offset", PNValues.encode(`shadow_offset`))
        if (`shadow_opacity` != null) result.put("shadow_opacity", PNValues.encode(`shadow_opacity`))
        if (`shadow_radius` != null) result.put("shadow_radius", PNValues.encode(`shadow_radius`))
        if (`elevation` != null) result.put("elevation", PNValues.encode(`elevation`))
        if (`opacity` != null) result.put("opacity", PNValues.encode(`opacity`))
        if (`transform` != null) result.put("transform", PNValues.encode(`transform`))
        if (`z_index` != null) result.put("z_index", PNValues.encode(`z_index`))
        if (`pointer_events` != null) result.put("pointer_events", PNValues.encode(`pointer_events`))
    }
    companion object {
        fun decode(value: Any?): PNStyle {
            val objectValue = PNValues.objectValue(value)
            return PNStyle(if (PNValues.isNull(objectValue.opt("width"))) null else PNViewWidth.decode((objectValue.opt("width"))), if (PNValues.isNull(objectValue.opt("height"))) null else PNViewWidth.decode((objectValue.opt("height"))), if (PNValues.isNull(objectValue.opt("min_width"))) null else PNViewWidth.decode((objectValue.opt("min_width"))), if (PNValues.isNull(objectValue.opt("max_width"))) null else PNViewWidth.decode((objectValue.opt("max_width"))), if (PNValues.isNull(objectValue.opt("min_height"))) null else PNViewWidth.decode((objectValue.opt("min_height"))), if (PNValues.isNull(objectValue.opt("max_height"))) null else PNViewWidth.decode((objectValue.opt("max_height"))), if (PNValues.isNull(objectValue.opt("aspect_ratio"))) null else PNValues.number((objectValue.opt("aspect_ratio"))), if (PNValues.isNull(objectValue.opt("flex"))) null else PNValues.number((objectValue.opt("flex"))), if (PNValues.isNull(objectValue.opt("flex_grow"))) null else PNValues.number((objectValue.opt("flex_grow"))), if (PNValues.isNull(objectValue.opt("flex_shrink"))) null else PNValues.number((objectValue.opt("flex_shrink"))), if (PNValues.isNull(objectValue.opt("flex_basis"))) null else PNViewWidth.decode((objectValue.opt("flex_basis"))), if (PNValues.isNull(objectValue.opt("flex_direction"))) null else PNViewFlexDirection.decode((objectValue.opt("flex_direction"))), if (PNValues.isNull(objectValue.opt("flex_wrap"))) null else PNViewFlexWrap.decode((objectValue.opt("flex_wrap"))), if (PNValues.isNull(objectValue.opt("justify_content"))) null else PNViewJustifyContent.decode((objectValue.opt("justify_content"))), if (PNValues.isNull(objectValue.opt("align_items"))) null else PNViewAlignItems.decode((objectValue.opt("align_items"))), if (PNValues.isNull(objectValue.opt("align_self"))) null else PNViewAlignItems.decode((objectValue.opt("align_self"))), if (PNValues.isNull(objectValue.opt("align_content"))) null else PNViewAlignContent.decode((objectValue.opt("align_content"))), if (PNValues.isNull(objectValue.opt("direction"))) null else PNViewDirection.decode((objectValue.opt("direction"))), if (PNValues.isNull(objectValue.opt("display"))) null else PNViewDisplay.decode((objectValue.opt("display"))), if (PNValues.isNull(objectValue.opt("position"))) null else PNViewPosition.decode((objectValue.opt("position"))), if (PNValues.isNull(objectValue.opt("top"))) null else PNViewWidth.decode((objectValue.opt("top"))), if (PNValues.isNull(objectValue.opt("right"))) null else PNViewWidth.decode((objectValue.opt("right"))), if (PNValues.isNull(objectValue.opt("bottom"))) null else PNViewWidth.decode((objectValue.opt("bottom"))), if (PNValues.isNull(objectValue.opt("left"))) null else PNViewWidth.decode((objectValue.opt("left"))), if (PNValues.isNull(objectValue.opt("start"))) null else PNViewWidth.decode((objectValue.opt("start"))), if (PNValues.isNull(objectValue.opt("end"))) null else PNViewWidth.decode((objectValue.opt("end"))), if (PNValues.isNull(objectValue.opt("padding"))) null else PNViewPadding.decode((objectValue.opt("padding"))), if (PNValues.isNull(objectValue.opt("padding_top"))) null else PNViewWidth.decode((objectValue.opt("padding_top"))), if (PNValues.isNull(objectValue.opt("padding_bottom"))) null else PNViewWidth.decode((objectValue.opt("padding_bottom"))), if (PNValues.isNull(objectValue.opt("padding_left"))) null else PNViewWidth.decode((objectValue.opt("padding_left"))), if (PNValues.isNull(objectValue.opt("padding_right"))) null else PNViewWidth.decode((objectValue.opt("padding_right"))), if (PNValues.isNull(objectValue.opt("padding_start"))) null else PNViewWidth.decode((objectValue.opt("padding_start"))), if (PNValues.isNull(objectValue.opt("padding_end"))) null else PNViewWidth.decode((objectValue.opt("padding_end"))), if (PNValues.isNull(objectValue.opt("padding_horizontal"))) null else PNViewWidth.decode((objectValue.opt("padding_horizontal"))), if (PNValues.isNull(objectValue.opt("padding_vertical"))) null else PNViewWidth.decode((objectValue.opt("padding_vertical"))), if (PNValues.isNull(objectValue.opt("margin"))) null else PNViewMargin.decode((objectValue.opt("margin"))), if (PNValues.isNull(objectValue.opt("margin_top"))) null else PNViewMarginTop.decode((objectValue.opt("margin_top"))), if (PNValues.isNull(objectValue.opt("margin_bottom"))) null else PNViewMarginTop.decode((objectValue.opt("margin_bottom"))), if (PNValues.isNull(objectValue.opt("margin_left"))) null else PNViewMarginTop.decode((objectValue.opt("margin_left"))), if (PNValues.isNull(objectValue.opt("margin_right"))) null else PNViewMarginTop.decode((objectValue.opt("margin_right"))), if (PNValues.isNull(objectValue.opt("margin_start"))) null else PNViewMarginTop.decode((objectValue.opt("margin_start"))), if (PNValues.isNull(objectValue.opt("margin_end"))) null else PNViewMarginTop.decode((objectValue.opt("margin_end"))), if (PNValues.isNull(objectValue.opt("margin_horizontal"))) null else PNViewMarginTop.decode((objectValue.opt("margin_horizontal"))), if (PNValues.isNull(objectValue.opt("margin_vertical"))) null else PNViewMarginTop.decode((objectValue.opt("margin_vertical"))), if (PNValues.isNull(objectValue.opt("spacing"))) null else PNValues.number((objectValue.opt("spacing"))), if (PNValues.isNull(objectValue.opt("gap"))) null else PNValues.number((objectValue.opt("gap"))), if (PNValues.isNull(objectValue.opt("row_gap"))) null else PNValues.number((objectValue.opt("row_gap"))), if (PNValues.isNull(objectValue.opt("column_gap"))) null else PNValues.number((objectValue.opt("column_gap"))), if (PNValues.isNull(objectValue.opt("overflow"))) null else PNViewOverflow.decode((objectValue.opt("overflow"))), if (PNValues.isNull(objectValue.opt("background_color"))) null else PNValues.string((objectValue.opt("background_color"))), if (PNValues.isNull(objectValue.opt("color"))) null else PNValues.string((objectValue.opt("color"))), if (PNValues.isNull(objectValue.opt("border_color"))) null else PNValues.string((objectValue.opt("border_color"))), if (PNValues.isNull(objectValue.opt("placeholder_color"))) null else PNValues.string((objectValue.opt("placeholder_color"))), if (PNValues.isNull(objectValue.opt("tint_color"))) null else PNValues.string((objectValue.opt("tint_color"))), if (PNValues.isNull(objectValue.opt("border_width"))) null else PNValues.number((objectValue.opt("border_width"))), if (PNValues.isNull(objectValue.opt("border_radius"))) null else PNValues.number((objectValue.opt("border_radius"))), if (PNValues.isNull(objectValue.opt("border_top_left_radius"))) null else PNValues.number((objectValue.opt("border_top_left_radius"))), if (PNValues.isNull(objectValue.opt("border_top_right_radius"))) null else PNValues.number((objectValue.opt("border_top_right_radius"))), if (PNValues.isNull(objectValue.opt("border_bottom_left_radius"))) null else PNValues.number((objectValue.opt("border_bottom_left_radius"))), if (PNValues.isNull(objectValue.opt("border_bottom_right_radius"))) null else PNValues.number((objectValue.opt("border_bottom_right_radius"))), if (PNValues.isNull(objectValue.opt("border_top_width"))) null else PNValues.number((objectValue.opt("border_top_width"))), if (PNValues.isNull(objectValue.opt("border_right_width"))) null else PNValues.number((objectValue.opt("border_right_width"))), if (PNValues.isNull(objectValue.opt("border_bottom_width"))) null else PNValues.number((objectValue.opt("border_bottom_width"))), if (PNValues.isNull(objectValue.opt("border_left_width"))) null else PNValues.number((objectValue.opt("border_left_width"))), if (PNValues.isNull(objectValue.opt("border_top_color"))) null else PNValues.string((objectValue.opt("border_top_color"))), if (PNValues.isNull(objectValue.opt("border_right_color"))) null else PNValues.string((objectValue.opt("border_right_color"))), if (PNValues.isNull(objectValue.opt("border_bottom_color"))) null else PNValues.string((objectValue.opt("border_bottom_color"))), if (PNValues.isNull(objectValue.opt("border_left_color"))) null else PNValues.string((objectValue.opt("border_left_color"))), if (PNValues.isNull(objectValue.opt("font_size"))) null else PNValues.number((objectValue.opt("font_size"))), if (PNValues.isNull(objectValue.opt("font_family"))) null else PNValues.string((objectValue.opt("font_family"))), if (PNValues.isNull(objectValue.opt("font_weight"))) null else PNViewFontWeight.decode((objectValue.opt("font_weight"))), if (PNValues.isNull(objectValue.opt("bold"))) null else PNValues.boolean((objectValue.opt("bold"))), if (PNValues.isNull(objectValue.opt("italic"))) null else PNValues.boolean((objectValue.opt("italic"))), if (PNValues.isNull(objectValue.opt("text_align"))) null else PNViewTextAlign.decode((objectValue.opt("text_align"))), if (PNValues.isNull(objectValue.opt("text_decoration"))) null else PNViewTextDecoration.decode((objectValue.opt("text_decoration"))), if (PNValues.isNull(objectValue.opt("text_transform"))) null else PNViewTextTransform.decode((objectValue.opt("text_transform"))), if (PNValues.isNull(objectValue.opt("line_height"))) null else PNValues.number((objectValue.opt("line_height"))), if (PNValues.isNull(objectValue.opt("letter_spacing"))) null else PNValues.number((objectValue.opt("letter_spacing"))), if (PNValues.isNull(objectValue.opt("max_lines"))) null else PNValues.integer((objectValue.opt("max_lines"))), if (PNValues.isNull(objectValue.opt("text_shadow_color"))) null else PNValues.string((objectValue.opt("text_shadow_color"))), if (PNValues.isNull(objectValue.opt("text_shadow_offset"))) null else PNViewTextShadowOffset.decode((objectValue.opt("text_shadow_offset"))), if (PNValues.isNull(objectValue.opt("text_shadow_radius"))) null else PNValues.number((objectValue.opt("text_shadow_radius"))), if (PNValues.isNull(objectValue.opt("shadow_color"))) null else PNValues.string((objectValue.opt("shadow_color"))), if (PNValues.isNull(objectValue.opt("shadow_offset"))) null else PNViewTextShadowOffset.decode((objectValue.opt("shadow_offset"))), if (PNValues.isNull(objectValue.opt("shadow_opacity"))) null else PNValues.number((objectValue.opt("shadow_opacity"))), if (PNValues.isNull(objectValue.opt("shadow_radius"))) null else PNValues.number((objectValue.opt("shadow_radius"))), if (PNValues.isNull(objectValue.opt("elevation"))) null else PNValues.number((objectValue.opt("elevation"))), if (PNValues.isNull(objectValue.opt("opacity"))) null else PNValues.number((objectValue.opt("opacity"))), if (PNValues.isNull(objectValue.opt("transform"))) null else PNViewTransform.decode((objectValue.opt("transform"))), if (PNValues.isNull(objectValue.opt("z_index"))) null else PNValues.integer((objectValue.opt("z_index"))), if (PNValues.isNull(objectValue.opt("pointer_events"))) null else PNViewPointerEvents.decode((objectValue.opt("pointer_events"))))
        }
    }
}

sealed class PNPNScrollViewContentContainerStyle2Item : PNNativeValue {
    data class Option0(val value: PNStyle) : PNPNScrollViewContentContainerStyle2Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Map<String, PNJSONValue>) : PNPNScrollViewContentContainerStyle2Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: PNJSONValue) : PNPNScrollViewContentContainerStyle2Item() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNPNScrollViewContentContainerStyle2Item {
            try { return Option0(PNStyle.decode(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.objectValue(value).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNJSONValue(objectValue.get(key) ?: JSONObject.NULL) } }) } catch (_: Exception) { }
            try { return Option2(PNJSONValue(value ?: JSONObject.NULL)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNPNScrollViewContentContainerStyle2Item")
        }
    }
}

sealed class PNScrollViewContentContainerStyle : PNNativeValue {
    data class Option0(val value: PNStyle) : PNScrollViewContentContainerStyle() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option1(val value: Map<String, PNJSONValue>) : PNScrollViewContentContainerStyle() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option2(val value: List<PNPNScrollViewContentContainerStyle2Item>) : PNScrollViewContentContainerStyle() { override fun nativeValue(): Any = PNValues.encode(value) }
    data class Option3(val value: PNJSONValue) : PNScrollViewContentContainerStyle() { override fun nativeValue(): Any = PNValues.encode(value) }
    companion object {
        fun decode(value: Any?): PNScrollViewContentContainerStyle {
            try { return Option0(PNStyle.decode(value)) } catch (_: Exception) { }
            try { return Option1(PNValues.objectValue(value).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNJSONValue(objectValue.get(key) ?: JSONObject.NULL) } }) } catch (_: Exception) { }
            try { return Option2(PNValues.array(value).map { item -> PNPNScrollViewContentContainerStyle2Item.decode(item) }) } catch (_: Exception) { }
            try { return Option3(PNJSONValue(value ?: JSONObject.NULL)) } catch (_: Exception) { }
            throw IllegalArgumentException("Invalid PNScrollViewContentContainerStyle")
        }
    }
}

enum class PNScrollViewKeyboardDismissMode(val rawValue: String) : PNNativeValue {
    `none`("none"),
    `on_drag`("on_drag"),
    `interactive`("interactive");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNScrollViewKeyboardDismissMode = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNScrollViewKeyboardDismissMode")
    }
}

enum class PNStatusBarBarStyle(val rawValue: String) : PNNativeValue {
    `light`("light"),
    `dark`("dark"),
    `default`("default");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNStatusBarBarStyle = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNStatusBarBarStyle")
    }
}

data class PNTabBarItemsItem(
    val `name`: String,
    val `title`: String,
    val `icon`: String?,
    val `badge`: String?
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("name", PNValues.encode(`name`))
        result.put("title", PNValues.encode(`title`))
        if (`icon` != null) result.put("icon", PNValues.encode(`icon`))
        if (`badge` != null) result.put("badge", PNValues.encode(`badge`))
    }
    companion object {
        fun decode(value: Any?): PNTabBarItemsItem {
            val objectValue = PNValues.objectValue(value)
            return PNTabBarItemsItem(PNValues.string((objectValue.get("name"))), PNValues.string((objectValue.get("title"))), if (PNValues.isNull(objectValue.opt("icon"))) null else PNValues.string((objectValue.opt("icon"))), if (PNValues.isNull(objectValue.opt("badge"))) null else PNValues.string((objectValue.opt("badge"))))
        }
    }
}

enum class PNTextInputKeyboardType(val rawValue: String) : PNNativeValue {
    `default`("default"),
    `email_address`("email_address"),
    `number_pad`("number_pad"),
    `decimal_pad`("decimal_pad"),
    `phone_pad`("phone_pad"),
    `url`("url");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNTextInputKeyboardType = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNTextInputKeyboardType")
    }
}

enum class PNTextInputAutoCapitalize(val rawValue: String) : PNNativeValue {
    `none`("none"),
    `sentences`("sentences"),
    `words`("words"),
    `characters`("characters");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNTextInputAutoCapitalize = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNTextInputAutoCapitalize")
    }
}

enum class PNTextInputReturnKeyType(val rawValue: String) : PNNativeValue {
    `default`("default"),
    `done`("done"),
    `go`("go"),
    `next`("next"),
    `send`("send"),
    `search`("search");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNTextInputReturnKeyType = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNTextInputReturnKeyType")
    }
}

data class PNWebNavigationEvent(
    val `url`: String,
    val `loading`: Boolean,
    val `can_go_back`: Boolean,
    val `can_go_forward`: Boolean,
    val `title`: String
) : PNNativeValue {
    override fun nativeValue(): Any = JSONObject().also { result ->
        result.put("url", PNValues.encode(`url`))
        result.put("loading", PNValues.encode(`loading`))
        result.put("can_go_back", PNValues.encode(`can_go_back`))
        result.put("can_go_forward", PNValues.encode(`can_go_forward`))
        result.put("title", PNValues.encode(`title`))
    }
    companion object {
        fun decode(value: Any?): PNWebNavigationEvent {
            val objectValue = PNValues.objectValue(value)
            return PNWebNavigationEvent(PNValues.string((objectValue.get("url"))), PNValues.boolean((objectValue.get("loading"))), PNValues.boolean((objectValue.get("can_go_back"))), PNValues.boolean((objectValue.get("can_go_forward"))), PNValues.string((if (objectValue.has("title")) objectValue.get("title") else PNValues.defaultValue("\"\""))))
        }
    }
}

enum class PNLocationGetCurrentAccuracy(val rawValue: String) : PNNativeValue {
    `balanced`("balanced"),
    `high`("high");
    override fun nativeValue(): Any = rawValue
    companion object {
        fun decode(value: Any?): PNLocationGetCurrentAccuracy = entries.firstOrNull { it.rawValue == value }
            ?: throw IllegalArgumentException("Invalid PNLocationGetCurrentAccuracy")
    }
}
