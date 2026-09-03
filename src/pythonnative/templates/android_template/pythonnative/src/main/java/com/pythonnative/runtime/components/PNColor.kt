package com.pythonnative.runtime.components

import org.json.JSONArray
import org.json.JSONObject

/**
 * Color parsing shared by every manager.
 *
 * Accepts `#RGB`, `#RGBA`, `#RRGGBB`, `#AARRGGBB` (the Android/Python
 * convention used by `parse_color_int`), `rgb(r, g, b)`,
 * `rgba(r, g, b, a)` with `a` in `0..1`, CSS named colors, packed
 * integers (`0xRRGGBB` gains full alpha), and `[r, g, b(, a)]` arrays.
 * Results are signed 32-bit ARGB ints suitable for Android APIs.
 */
object PNColor {
    private val named: Map<String, Int> = mapOf(
        "transparent" to 0x00000000,
        "clear" to 0x00000000,
        "black" to 0xFF000000.toInt(),
        "white" to 0xFFFFFFFF.toInt(),
        "red" to 0xFFFF0000.toInt(),
        "green" to 0xFF008000.toInt(),
        "lime" to 0xFF00FF00.toInt(),
        "blue" to 0xFF0000FF.toInt(),
        "yellow" to 0xFFFFFF00.toInt(),
        "cyan" to 0xFF00FFFF.toInt(),
        "aqua" to 0xFF00FFFF.toInt(),
        "magenta" to 0xFFFF00FF.toInt(),
        "fuchsia" to 0xFFFF00FF.toInt(),
        "gray" to 0xFF808080.toInt(),
        "grey" to 0xFF808080.toInt(),
        "darkgray" to 0xFFA9A9A9.toInt(),
        "darkgrey" to 0xFFA9A9A9.toInt(),
        "lightgray" to 0xFFD3D3D3.toInt(),
        "lightgrey" to 0xFFD3D3D3.toInt(),
        "dimgray" to 0xFF696969.toInt(),
        "dimgrey" to 0xFF696969.toInt(),
        "silver" to 0xFFC0C0C0.toInt(),
        "maroon" to 0xFF800000.toInt(),
        "olive" to 0xFF808000.toInt(),
        "navy" to 0xFF000080.toInt(),
        "teal" to 0xFF008080.toInt(),
        "purple" to 0xFF800080.toInt(),
        "orange" to 0xFFFFA500.toInt(),
        "pink" to 0xFFFFC0CB.toInt(),
        "brown" to 0xFFA52A2A.toInt(),
        "gold" to 0xFFFFD700.toInt(),
        "indigo" to 0xFF4B0082.toInt(),
        "violet" to 0xFFEE82EE.toInt(),
        "coral" to 0xFFFF7F50.toInt(),
        "salmon" to 0xFFFA8072.toInt(),
        "tomato" to 0xFFFF6347.toInt(),
        "crimson" to 0xFFDC143C.toInt(),
        "khaki" to 0xFFF0E68C.toInt(),
        "beige" to 0xFFF5F5DC.toInt(),
        "ivory" to 0xFFFFFFF0.toInt(),
        "tan" to 0xFFD2B48C.toInt(),
        "turquoise" to 0xFF40E0D0.toInt(),
        "skyblue" to 0xFF87CEEB.toInt(),
        "steelblue" to 0xFF4682B4.toInt(),
        "royalblue" to 0xFF4169E1.toInt(),
        "dodgerblue" to 0xFF1E90FF.toInt(),
        "slategray" to 0xFF708090.toInt(),
        "slategrey" to 0xFF708090.toInt(),
        "whitesmoke" to 0xFFF5F5F5.toInt(),
        "snow" to 0xFFFFFAFA.toInt(),
        "seagreen" to 0xFF2E8B57.toInt(),
        "forestgreen" to 0xFF228B22.toInt(),
        "darkgreen" to 0xFF006400.toInt(),
        "lightblue" to 0xFFADD8E6.toInt(),
        "lightgreen" to 0xFF90EE90.toInt(),
        "darkblue" to 0xFF00008B.toInt(),
        "darkred" to 0xFF8B0000.toInt(),
        "orangered" to 0xFFFF4500.toInt(),
        "hotpink" to 0xFFFF69B4.toInt(),
        "deeppink" to 0xFFFF1493.toInt(),
        "chocolate" to 0xFFD2691E.toInt(),
        "plum" to 0xFFDDA0DD.toInt(),
        "lavender" to 0xFFE6E6FA.toInt(),
        "mintcream" to 0xFFF5FFFA.toInt(),
        "gainsboro" to 0xFFDCDCDC.toInt(),
    )

    /** Parse `value` into a signed ARGB int, or `null` when unparseable. */
    fun parse(value: Any?): Int? {
        return when (value) {
            null, JSONObject.NULL -> null
            is Boolean -> null
            is Int -> if (value ushr 24 == 0) value or 0xFF000000.toInt() else value
            is Long -> parseLong(value)
            is Number -> {
                val d = value.toDouble()
                if (d.isNaN() || d.isInfinite()) null else parseLong(d.toLong())
            }
            is String -> parseString(value)
            is JSONArray -> parseArray((0 until value.length()).map { value.opt(it) })
            is List<*> -> parseArray(value)
            else -> null
        }
    }

    /** Parse `value`, falling back to `default` when unparseable. */
    fun parseOr(value: Any?, default: Int): Int = parse(value) ?: default

    /** Replace the alpha channel of `color` with `alpha` in `0..1`. */
    fun withAlpha(color: Int, alpha: Double): Int {
        val a = (alpha.coerceIn(0.0, 1.0) * 255.0).toInt()
        return (color and 0x00FFFFFF) or (a shl 24)
    }

    private fun parseLong(raw: Long): Int {
        val masked = raw and 0xFFFFFFFFL
        val withAlpha = if (masked ushr 24 == 0L) masked or 0xFF000000L else masked
        return withAlpha.toInt()
    }

    private fun parseArray(items: List<Any?>): Int? {
        if (items.size < 3) return null
        val r = channel(items[0]) ?: return null
        val g = channel(items[1]) ?: return null
        val b = channel(items[2]) ?: return null
        val a = if (items.size >= 4) alphaChannel(items[3]) ?: return null else 255
        return argb(a, r, g, b)
    }

    private fun parseString(raw: String): Int? {
        val s = raw.trim()
        if (s.isEmpty()) return null
        if (s.startsWith("#")) return parseHex(s.substring(1))
        val lower = s.lowercase()
        named[lower]?.let { return it }
        if (lower.startsWith("rgb")) return parseFunctional(lower)
        if (lower.startsWith("0x")) return s.substring(2).toLongOrNull(16)?.let { parseLong(it) }
        return s.toLongOrNull(16)?.takeIf { s.length == 6 || s.length == 8 }?.let {
            parseHexDigits(s)
        }
    }

    private fun parseHex(digits: String): Int? {
        if (digits.isEmpty() || !digits.all { it.isLetterOrDigit() }) return null
        val expanded = when (digits.length) {
            3 -> "FF" + digits.map { "$it$it" }.joinToString("")
            4 -> {
                // CSS #RGBA: alpha is the last digit.
                val rgb = digits.substring(0, 3).map { "$it$it" }.joinToString("")
                val a = "${digits[3]}${digits[3]}"
                a + rgb
            }
            6 -> "FF$digits"
            8 -> digits
            else -> return null
        }
        return expanded.toLongOrNull(16)?.toInt()
    }

    private fun parseHexDigits(digits: String): Int? = parseHex(digits)

    private fun parseFunctional(lower: String): Int? {
        val open = lower.indexOf('(')
        val close = lower.lastIndexOf(')')
        if (open < 0 || close < open) return null
        val parts = lower.substring(open + 1, close).split(',', '/', ' ').map { it.trim() }.filter { it.isNotEmpty() }
        if (parts.size < 3) return null
        val r = channel(parts[0]) ?: return null
        val g = channel(parts[1]) ?: return null
        val b = channel(parts[2]) ?: return null
        val a = if (parts.size >= 4) alphaChannel(parts[3]) ?: return null else 255
        return argb(a, r, g, b)
    }

    private fun channel(value: Any?): Int? {
        val d = when (value) {
            is Number -> value.toDouble()
            is String -> {
                val t = value.trim()
                if (t.endsWith("%")) (t.dropLast(1).toDoubleOrNull() ?: return null) * 2.55
                else t.toDoubleOrNull() ?: return null
            }
            else -> return null
        }
        return d.toInt().coerceIn(0, 255)
    }

    private fun alphaChannel(value: Any?): Int? {
        val d = when (value) {
            is Number -> value.toDouble()
            is String -> {
                val t = value.trim()
                if (t.endsWith("%")) (t.dropLast(1).toDoubleOrNull() ?: return null) / 100.0
                else t.toDoubleOrNull() ?: return null
            }
            else -> return null
        }
        // Values above 1 are taken as 0..255 bytes.
        val a = if (d > 1.0) d / 255.0 else d
        return (a.coerceIn(0.0, 1.0) * 255.0 + 0.5).toInt()
    }

    private fun argb(a: Int, r: Int, g: Int, b: Int): Int =
        (a shl 24) or (r shl 16) or (g shl 8) or b
}
