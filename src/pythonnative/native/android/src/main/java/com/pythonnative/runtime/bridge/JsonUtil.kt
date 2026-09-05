package com.pythonnative.runtime.bridge

import org.json.JSONArray
import org.json.JSONObject

/**
 * Helpers for the JSON shapes the bridge exchanges with Python.
 *
 * Python normalizes values before encoding: `math.inf` arrives as the
 * string `"inf"`, removed props arrive as JSON `null`, and tuples and
 * frozensets arrive as arrays. These helpers hide those conventions.
 */
object JsonUtil {
    /** Whether `value` is absent or an explicit JSON null. */
    fun isNull(value: Any?): Boolean = value == null || value === JSONObject.NULL

    /** Coerce a JSON value to a double; `"inf"` / `"-inf"` become infinities. */
    fun toDoubleOrNull(value: Any?): Double? {
        return when (value) {
            null, JSONObject.NULL -> null
            is Number -> value.toDouble()
            is Boolean -> if (value) 1.0 else 0.0
            is String -> {
                val s = value.trim()
                when (s.lowercase()) {
                    "inf", "+inf", "infinity", "+infinity" -> Double.POSITIVE_INFINITY
                    "-inf", "-infinity" -> Double.NEGATIVE_INFINITY
                    "nan" -> Double.NaN
                    else -> s.toDoubleOrNull()
                }
            }
            else -> null
        }
    }

    /** Coerce a JSON value to a double with `default` for missing or unparseable input. */
    fun toDouble(value: Any?, default: Double = 0.0): Double = toDoubleOrNull(value) ?: default

    /** Coerce a JSON value to an int (truncating), with `default` for bad input. */
    fun toInt(value: Any?, default: Int = 0): Int {
        val d = toDoubleOrNull(value) ?: return default
        if (d.isNaN() || d.isInfinite()) return default
        return d.toInt()
    }

    /** Coerce a JSON value to a long (truncating), with `default` for bad input. */
    fun toLong(value: Any?, default: Long = 0L): Long {
        return when (value) {
            is Number -> value.toLong()
            else -> {
                val d = toDoubleOrNull(value) ?: return default
                if (d.isNaN() || d.isInfinite()) default else d.toLong()
            }
        }
    }

    /** Python-style truthiness for JSON values. */
    fun truthy(value: Any?): Boolean {
        return when (value) {
            null, JSONObject.NULL -> false
            is Boolean -> value
            is Number -> value.toDouble() != 0.0
            is String -> value.isNotEmpty()
            is JSONArray -> value.length() > 0
            is JSONObject -> value.length() > 0
            else -> true
        }
    }

    /** `value` as a string, or `null` when absent or JSON null. */
    fun stringOrNull(value: Any?): String? = if (isNull(value)) null else value.toString()

    /** Copy `changed` into `target`, keeping explicit nulls as [JSONObject.NULL]. */
    fun merge(target: JSONObject, changed: JSONObject) {
        val keys = changed.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            target.put(key, changed.opt(key) ?: JSONObject.NULL)
        }
    }

    /** Convert a [JSONArray] to a Kotlin list (JSON nulls become `null`). */
    fun toList(array: JSONArray?): List<Any?> {
        if (array == null) return emptyList()
        val out = ArrayList<Any?>(array.length())
        for (i in 0 until array.length()) {
            val v = array.opt(i)
            out.add(if (v === JSONObject.NULL) null else v)
        }
        return out
    }

    /** Convert a [JSONObject] to a Kotlin map (JSON nulls become `null`). */
    fun toMap(obj: JSONObject?): Map<String, Any?> {
        if (obj == null) return emptyMap()
        val out = LinkedHashMap<String, Any?>()
        val keys = obj.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val v = obj.opt(key)
            out[key] = if (v === JSONObject.NULL) null else v
        }
        return out
    }

    /** Wrap a Kotlin value into something `org.json` can hold (maps, lists, nulls). */
    fun wrap(value: Any?): Any {
        return when (value) {
            null -> JSONObject.NULL
            is JSONObject, is JSONArray, is String, is Boolean -> value
            is Float -> if (value.isFinite()) value.toDouble() else JSONObject.NULL
            is Double -> if (value.isFinite()) value else JSONObject.NULL
            is Number -> value
            is Map<*, *> -> {
                val obj = JSONObject()
                for ((k, v) in value) obj.put(k.toString(), wrap(v))
                obj
            }
            is Iterable<*> -> {
                val arr = JSONArray()
                for (v in value) arr.put(wrap(v))
                arr
            }
            is Array<*> -> wrap(value.asList())
            is DoubleArray -> wrap(value.asList())
            is FloatArray -> wrap(value.asList())
            is IntArray -> wrap(value.asList())
            else -> value.toString()
        }
    }

    /** Build a JSON array of positional arguments. */
    fun args(vararg values: Any?): JSONArray {
        val arr = JSONArray()
        for (v in values) arr.put(wrap(v))
        return arr
    }

    /** Encode a command or module result as a JSON string; `null` stays `null`. */
    fun encode(value: Any?): String? {
        if (value == null || value === JSONObject.NULL) return null
        return when (val wrapped = wrap(value)) {
            is JSONObject, is JSONArray -> wrapped.toString()
            is String -> JSONObject.quote(wrapped)
            else -> wrapped.toString()
        }
    }
}

/** The value under `key`, or `null` for missing keys and JSON nulls. */
fun JSONObject.value(key: String): Any? {
    val v = opt(key) ?: return null
    return if (v === JSONObject.NULL) null else v
}

/** String prop or `null`. */
fun JSONObject.str(key: String): String? = JsonUtil.stringOrNull(opt(key))

/** Numeric prop (accepting `"inf"`) or `null`. */
fun JSONObject.num(key: String): Double? = JsonUtil.toDoubleOrNull(opt(key))

/** Boolean prop using Python truthiness, or `null` when absent. */
fun JSONObject.bool(key: String): Boolean? {
    val v = value(key) ?: return null
    return JsonUtil.truthy(v)
}

/** Object prop or `null`. */
fun JSONObject.obj(key: String): JSONObject? = value(key) as? JSONObject

/** Array prop or `null`. */
fun JSONObject.arr(key: String): JSONArray? = value(key) as? JSONArray

/** Whether the prop is present with a non-null value. */
fun JSONObject.present(key: String): Boolean = value(key) != null
