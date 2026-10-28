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

    private val decodeFailure = ThreadLocal<String?>()

    /**
     * Decode one prop for a generated getter. A failure reads as null and is
     * recorded on the current thread, so a value that passed validation but
     * doesn't decode rejects the commit being applied ([takeDecodeFailure])
     * instead of crashing the app.
     */
    inline fun <T> decodeOrRecord(field: String, decode: () -> T): T? = try {
        decode()
    } catch (error: Exception) {
        recordDecodeFailure(field, error)
        null
    }

    fun recordDecodeFailure(field: String, error: Exception) {
        if (decodeFailure.get() == null) decodeFailure.set("field $field didn't decode (${error.message ?: error.javaClass.simpleName})")
    }

    /** The first decoding failure recorded on this thread since the last call, clearing it. */
    fun takeDecodeFailure(): String? = decodeFailure.get()?.also { decodeFailure.remove() }
}
